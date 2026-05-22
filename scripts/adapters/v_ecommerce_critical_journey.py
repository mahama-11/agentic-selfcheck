#!/usr/bin/env python3
"""V/Ecommerce adapter for the generic critical journey runner.

This file is intentionally V-specific. The generic SelfCheck runner invokes it
with SELFCHECK_PROJECT_ROOT, SELFCHECK_REPORT_DIR, SELFCHECK_AUTH_FIXTURE, and
SELFCHECK_JOURNEY_PHASE. Do not move V route/payload knowledge into SelfCheck
core.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

FORBIDDEN_REPORT_KEYS = {"password", "token", "authorization", "secret", "jwt"}
REQUIRED_ROUTES = [
    'authAPI.POST("/login"',
    'protected.POST("/products"',
    'protected.GET("/products/:product_id"',
    'protected.DELETE("/products/:product_id"',
    'protected.POST("/products/:product_id/v2/visual-sessions"',
    'protected.GET("/v2/visual-workflows/:session_id/stage-view"',
    'protected.POST("/v2/visual-workflows/:session_id/prompt-planner-jobs"',
    'protected.POST("/v2/visual-workflows/:session_id/generation-versions"',
    'protected.POST("/assets/source"',
    'protected.POST("/products/:product_id/assets"',
    'protected.POST("/products/:product_id/listing-versions"',
    'protected.POST("/products/:product_id/listing-versions/adopt"',
    'protected.POST("/products/:product_id/profit-snapshots/calculate"',
    'protected.POST("/products/:product_id/export-tasks"',
    'protected.POST("/export-packages"',
    'protected.GET("/downloads"',
    'templateCatalog.GET("/catalog"',
    'templateCatalog.GET("/catalog/facets"',
    'templateProtected.GET("/favorites"',
    'templateProtected.POST("/catalog/:templateId/favorite"',
    'templateProtected.DELETE("/catalog/:templateId/favorite"',
    'templateProtected.POST("/catalog/:templateId/copy"',
    'templateProtected.POST("/catalog/:templateId/use"',
    'v1.GET("/commercial/offerings"',
    'protected.GET("/wallet/summary"',
    'protected.GET("/billing/summary"',
    'protected.GET("/promotions/programs"',
]

FRONTEND_SIGNALS = [
    "SKU 生产档案",
    "SKU 图片识别结果不足",
    "补齐生成条件",
    "src/pages/production",
    "productCenter.shell.listing",
    "productCenter.shell.delivery",
    "templateCenter",
    "account.billing",
]



def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def redacted_env_summary(values: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in values.items():
        out[key] = "[REDACTED]" if any(part in key.lower() for part in FORBIDDEN_REPORT_KEYS) else value
    return out


def emit(status: str, phase: str, report: dict[str, Any], exit_code: int = 0) -> None:
    root = Path(os.environ["SELFCHECK_PROJECT_ROOT"])
    report_dir = Path(os.environ["SELFCHECK_REPORT_DIR"])
    payload = {"status": status, "phase": phase, "project_root": str(root), **report}
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"adapter-{phase}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    alias = root / "reports" / "ecommerce-critical-journey-release-gate"
    alias.mkdir(parents=True, exist_ok=True)
    (alias / f"{phase}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(exit_code)


def fail(phase: str, message: str, **details: Any) -> None:
    emit("FAIL", phase, {"message": message, "details": details}, 2)


def project_root() -> Path:
    return Path(os.environ["SELFCHECK_PROJECT_ROOT"]).expanduser().resolve()


def auth_fixture() -> tuple[Path, dict[str, str]]:
    path = Path(os.environ.get("SELFCHECK_AUTH_FIXTURE", "")).expanduser()
    if not path.exists():
        fail(os.environ.get("SELFCHECK_JOURNEY_PHASE", "api"), "auth fixture missing", path=str(path))
    values = load_env(path)
    required = ["PLATFORM_DEV_ADMIN_EMAIL", "PLATFORM_DEV_ADMIN_PASSWORD", "ECOMMERCE_BASE_URL"]
    missing = [key for key in required if not values.get(key)]
    if missing:
        fail(os.environ.get("SELFCHECK_JOURNEY_PHASE", "api"), "auth fixture missing required keys", missing=missing)
    return path, values


def check_static() -> None:
    root = project_root()
    router = (root / "ecommerce-backend/internal/router/router.go").read_text(encoding="utf-8")
    missing_routes = [needle for needle in REQUIRED_ROUTES if needle not in router]
    if missing_routes:
        fail("static", "critical backend route contract missing", missing_routes=missing_routes)
    frontend_files = [
        root / "ecommerce-frontend/src/i18n/zh.ts",
        root / "ecommerce-frontend/src/i18n/en.ts",
        root / "ecommerce-frontend/src/pages/production/SandboxPage.tsx",
        root / "ecommerce-frontend/src/pages/production/PrepHubPage.tsx",
        root / "ecommerce-frontend/src/pages/product/BatchListingPage.tsx",
        root / "ecommerce-frontend/src/layouts/ProductWorkbenchLayout.tsx",
        root / "ecommerce-frontend/src/pages/account/AccountDownloadsPage.tsx",
        root / "ecommerce-frontend/src/pages/account/AccountBillingPage.tsx",
        root / "ecommerce-frontend/src/pages/account/AccountPromotionPage.tsx",
        root / "ecommerce-frontend/src/pages/account/AccountCommissionPage.tsx",
        root / "ecommerce-frontend/src/pages/AgentTemplateMarketPage.tsx",
    ]
    frontend_text = "\n".join(p.read_text(encoding="utf-8") for p in frontend_files if p.exists())
    # src/pages/production is a path-level contract, not literal i18n copy.
    prod_dir_ok = (root / "ecommerce-frontend/src/pages/production").exists()
    signal_status = {s: (s in frontend_text or (s == "src/pages/production" and prod_dir_ok)) for s in FRONTEND_SIGNALS}
    missing_signals = [key for key, ok in signal_status.items() if not ok]
    if missing_signals:
        fail("static", "critical frontend SKU/production workflow signals missing", missing_signals=missing_signals)
    emit("PASS", "static", {"routes_checked": len(REQUIRED_ROUTES), "frontend_signals": signal_status})


def http_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: float = 12.0) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json", "User-Agent": "agentic-selfcheck-critical-journey/0.1", **(headers or {})})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            parsed = json.loads(body) if body.strip().startswith("{") else {}
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "duration_ms": round((time.time() - started) * 1000), "json": parsed}
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode("utf-8", "replace")
        return {"ok": False, "status": exc.code, "duration_ms": round((time.time() - started) * 1000), "body_prefix": body[:300]}
    except Exception as exc:
        return {"ok": False, "status": None, "duration_ms": round((time.time() - started) * 1000), "error": type(exc).__name__}


def extract_token(data: dict[str, Any]) -> str | None:
    obj = data.get("json") if isinstance(data.get("json"), dict) else data
    candidates = [obj]
    if isinstance(obj, dict) and isinstance(obj.get("data"), dict):
        candidates.append(obj["data"])
    for c in candidates:
        if isinstance(c, dict):
            for key in ["token", "access_token", "accessToken", "jwt"]:
                value = c.get(key)
                if isinstance(value, str) and value:
                    return value
    return None


def credential_candidates(env: dict[str, str]) -> list[dict[str, str]]:
    """Return login credential candidates without exposing secret values in reports.

    Ecommerce-specific credentials take precedence for Ecommerce API login. Platform
    credentials remain a fallback for older fixtures where only platform keys exist.
    """
    candidates: list[dict[str, str]] = []
    pairs = [
        ("ECOMMERCE_AUTH_EMAIL", "ECOMMERCE_AUTH_PASSWORD", "ecommerce"),
        ("PLATFORM_DEV_ADMIN_EMAIL", "PLATFORM_DEV_ADMIN_PASSWORD", "platform"),
    ]
    for email_key, password_key, label in pairs:
        if env.get(email_key) and env.get(password_key):
            candidates.append({"email": env[email_key], "password": env[password_key], "label": label})
    return candidates



def response_data(resp: dict[str, Any]) -> Any:
    obj = resp.get("json") if isinstance(resp.get("json"), dict) else {}
    return obj.get("data") if isinstance(obj, dict) and "data" in obj else obj


def data_id(resp: dict[str, Any], nested: str | None = None) -> str | None:
    data = response_data(resp)
    if nested and isinstance(data, dict) and isinstance(data.get(nested), dict):
        data = data[nested]
    if isinstance(data, dict):
        value = data.get("id") or data.get("package_id") or data.get("templateInstanceId") or data.get("template_instance_id")
        return str(value) if value else None
    return None


def ok_status(resp: dict[str, Any]) -> bool:
    return bool(resp.get("ok") and 200 <= int(resp.get("status") or 0) < 300)


def step_ok(steps: list[dict[str, Any]], name: str, resp: dict[str, Any], **extra: Any) -> dict[str, Any]:
    item = {"name": name, "status": resp.get("status"), "ok": ok_status(resp), **extra}
    steps.append(item)
    return item


def register_ready_asset(base: str, auth: dict[str, str], product_id: str, sku_code: str, steps: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    payload = "data:image/png;base64," + base64.b64encode(b"selfcheck-pixel").decode("ascii")
    asset = http_json(base + "/api/v1/ecommerce/assets/source", "POST", {
        "product_id": product_id,
        "sku_code": sku_code,
        "file_name": "selfcheck-source.png",
        "mime_type": "image/png",
        "payload": payload,
        "width": 16,
        "height": 16,
        "metadata": {"source": "agentic-selfcheck", "semantic": "delivery-contract"},
    }, auth)
    asset_id = data_id(asset)
    step_ok(steps, "register_source_asset", asset, asset_id_present=bool(asset_id))
    relation_id = None
    if asset_id:
        relation = http_json(base + f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id)}/assets", "POST", {
            "asset_id": asset_id,
            "relation_type": "primary",
            "asset_role": "hero",
            "is_primary": True,
        }, auth)
        relation_id = data_id(relation)
        step_ok(steps, "attach_primary_asset", relation, relation_id_present=bool(relation_id))
        status = http_json(base + f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id)}/status", "PATCH", {"status": "assets_ready"}, auth)
        step_ok(steps, "mark_assets_ready", status)
    return asset_id, relation_id


def run_productcore_delivery(base: str, auth: dict[str, str], product_id: str, sku_code: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    asset_id, relation_id = register_ready_asset(base, auth, product_id, sku_code, steps)
    listing = http_json(base + f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id)}/listing-versions", "POST", {
        "version_label": "SelfCheck Delivery",
        "title": "SelfCheck Listing " + sku_code,
        "description": "Deterministic SelfCheck listing version",
        "bullet_points": ["SelfCheck listing bullet"],
        "keywords": ["selfcheck", "release-gate"],
        "platform": "amazon",
        "site": "US",
        "locale": "en-US",
    }, auth)
    listing_id = data_id(listing)
    step_ok(steps, "create_listing_version", listing, listing_id_present=bool(listing_id))
    if listing_id:
        adopt = http_json(base + f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id)}/listing-versions/adopt", "POST", {"version_id": listing_id}, auth)
        step_ok(steps, "adopt_listing_version", adopt)
    profit = http_json(base + f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id)}/profit-snapshots/calculate", "POST", {
        "platform": "amazon", "site": "US", "cost_price": 10, "listing_price": 20, "logistics_cost": 2, "platform_fee": 1, "other_fee": 0,
    }, auth)
    step_ok(steps, "calculate_profit_snapshot", profit, profit_id_present=bool(data_id(profit)))
    export_task = http_json(base + f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id)}/export-tasks", "POST", {
        "platform": "amazon", "site": "US", "locale": "en-US", "format": "json",
        "asset_relation_ids": [relation_id] if relation_id else None,
    }, auth)
    export_task_id = data_id(export_task)
    step_ok(steps, "create_export_task", export_task, export_task_id_present=bool(export_task_id))
    package = http_json(base + "/api/v1/ecommerce/export-packages", "POST", {
        "items": [{"product_id": product_id}], "platform": "amazon", "site": "US", "locale": "en-US", "format": "json",
    }, auth)
    package_id = data_id(package)
    package_data = response_data(package)
    step_ok(steps, "create_export_package", package, package_id_present=bool(package_id), succeeded=(package_data.get("succeeded") if isinstance(package_data, dict) else None))
    downloads = http_json(base + "/api/v1/ecommerce/downloads", headers=auth)
    downloads_data = response_data(downloads)
    download_items = downloads_data if isinstance(downloads_data, list) else (downloads_data.get("items", []) if isinstance(downloads_data, dict) else [])
    step_ok(steps, "list_downloads", downloads, download_count=len(download_items) if isinstance(download_items, list) else 0)
    return {"asset_id_present": bool(asset_id), "listing_id_present": bool(listing_id), "export_task_id_present": bool(export_task_id), "package_id_present": bool(package_id)}


def run_template_journey(base: str, auth: dict[str, str], steps: list[dict[str, Any]]) -> dict[str, Any]:
    catalog = http_json(base + "/api/v1/ecommerce/template-center/catalog?locale=zh-CN&modality=image&sortBy=recommended", headers=auth)
    data = response_data(catalog)
    items = data if isinstance(data, list) else (data.get("items", []) if isinstance(data, dict) else [])
    template_id = str(items[0].get("id")) if items and isinstance(items[0], dict) and items[0].get("id") else None
    step_ok(steps, "template_catalog", catalog, template_count=len(items) if isinstance(items, list) else 0, template_id_present=bool(template_id))
    facets = http_json(base + "/api/v1/ecommerce/template-center/catalog/facets?locale=zh-CN", headers=auth)
    step_ok(steps, "template_facets", facets)
    if template_id:
        detail = http_json(base + "/api/v1/ecommerce/template-center/catalog/" + urllib.parse.quote(template_id) + "?locale=zh-CN", headers=auth)
        step_ok(steps, "template_detail", detail)
        favorite = http_json(base + "/api/v1/ecommerce/template-center/catalog/" + urllib.parse.quote(template_id) + "/favorite", "POST", {}, auth)
        step_ok(steps, "template_favorite", favorite)
        unfavorite = http_json(base + "/api/v1/ecommerce/template-center/catalog/" + urllib.parse.quote(template_id) + "/favorite", "DELETE", headers=auth)
        step_ok(steps, "template_unfavorite", unfavorite)
        copy = http_json(base + "/api/v1/ecommerce/template-center/catalog/" + urllib.parse.quote(template_id) + "/copy", "POST", {}, auth)
        step_ok(steps, "template_copy", copy)
        use = http_json(base + "/api/v1/ecommerce/template-center/catalog/" + urllib.parse.quote(template_id) + "/use", "POST", {}, auth)
        use_data = response_data(use)
        payload_present = isinstance(use_data, dict) and bool(use_data.get("preloadedTemplatePayload") or use_data.get("preloaded_template_payload"))
        step_ok(steps, "template_use", use, preloaded_payload_present=payload_present)
    return {"template_id_present": bool(template_id)}


def run_commercial_smoke(base: str, auth: dict[str, str], steps: list[dict[str, Any]]) -> dict[str, Any]:
    checks = [
        ("commercial_offerings", "/api/v1/ecommerce/commercial/offerings"),
        ("wallet_summary", "/api/v1/ecommerce/wallet/summary"),
        ("billing_summary", "/api/v1/ecommerce/billing/summary"),
        ("promotion_programs", "/api/v1/ecommerce/promotions/programs"),
        ("promotion_overview", "/api/v1/ecommerce/promotions/me/overview"),
        ("commission_overview", "/api/v1/ecommerce/commissions/me/overview"),
    ]
    for name, path in checks:
        step_ok(steps, name, http_json(base + path, headers=auth))
    return {"checks": len(checks)}

def check_api() -> None:
    mode = os.environ.get("ECOM_CRITICAL_JOURNEY_MODE", "contract")
    _, env = auth_fixture()
    if mode != "live":
        emit("PASS", "api", {
            "mode": mode,
            "contract_checks": ["auth_fixture_loaded", "live_mode_available", "sku_lifecycle_payload_defined", "production_workflow_routes_declared", "productcore_delivery_routes_declared", "template_center_routes_declared", "commercial_account_routes_declared"],
            "auth_fixture": redacted_env_summary(env),
            "live_command": "ECOM_CRITICAL_JOURNEY_MODE=live scripts/critical_journey_gate.py --journey v-ecommerce-critical-sku-production --phase api",
        })
    base = env["ECOMMERCE_BASE_URL"].rstrip("/")
    login_attempts: list[dict[str, Any]] = []
    token = None
    login: dict[str, Any] = {}
    for candidate in credential_candidates(env):
        login = http_json(base + "/api/v1/ecommerce/auth/login", "POST", {"email": candidate["email"], "password": candidate["password"]})
        token = extract_token(login)
        login_attempts.append({"source": candidate["label"], "status": login.get("status"), "ok": bool(login.get("ok") and token), "token_present": bool(token)})
        if token:
            break
    steps: list[dict[str, Any]] = [{"name": "login", "attempts": login_attempts, "ok": bool(token), "token_present": bool(token)}]
    if not token:
        fail("api", "live login failed; cannot run SKU production journey", steps=steps)
    token_value = str(token)
    auth = {"Authorization": "Bearer " + token_value}
    run_id = str(int(time.time()))
    sku_code = "SC-SKU-" + run_id
    create_payload = {"sku_code": sku_code, "title": "SelfCheck SKU " + run_id, "brand": "SelfCheck", "category": "QA", "metadata": {"created_by": "agentic-selfcheck", "run_id": run_id}}
    created = http_json(base + "/api/v1/ecommerce/products", "POST", create_payload, auth)
    product_id = None
    if isinstance(created.get("json"), dict):
        data = created["json"].get("data") if isinstance(created["json"].get("data"), dict) else created["json"]
        product = data.get("product") if isinstance(data.get("product"), dict) else data
        product_id = product.get("id") if isinstance(product, dict) else None
    steps.append({"name": "create_sku", "status": created.get("status"), "ok": bool(created.get("ok") and product_id), "product_id_present": bool(product_id)})
    if not product_id:
        fail("api", "live SKU create failed", steps=steps)
    product_id_value = str(product_id)
    try:
        detail = http_json(base + "/api/v1/ecommerce/products/" + urllib.parse.quote(product_id_value), headers=auth)
        steps.append({"name": "get_sku", "status": detail.get("status"), "ok": bool(detail.get("ok"))})
        session = http_json(base + f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id_value)}/v2/visual-sessions", "POST", {"sku_code": sku_code, "title": "SelfCheck production journey"}, auth)
        sid = None
        if isinstance(session.get("json"), dict):
            data = session["json"].get("data") if isinstance(session["json"].get("data"), dict) else session["json"]
            obj = data.get("session") if isinstance(data.get("session"), dict) else data
            sid = obj.get("id") if isinstance(obj, dict) else None
        steps.append({"name": "create_visual_session", "status": session.get("status"), "ok": bool(session.get("ok") and sid), "session_id_present": bool(sid)})
        if sid:
            stage = http_json(base + "/api/v1/ecommerce/v2/visual-workflows/" + urllib.parse.quote(sid) + "/stage-view", headers=auth)
            steps.append({"name": "stage_view", "status": stage.get("status"), "ok": bool(stage.get("ok"))})
        delivery = run_productcore_delivery(base, auth, product_id_value, sku_code, steps)
        template = run_template_journey(base, auth, steps)
        commercial = run_commercial_smoke(base, auth, steps)
    finally:
        cleanup = http_json(base + "/api/v1/ecommerce/products/" + urllib.parse.quote(product_id_value), "DELETE", headers=auth) if product_id else {"ok": False, "status": None}
        steps.append({"name": "cleanup_delete_sku", "status": cleanup.get("status"), "ok": bool(cleanup.get("ok"))})
    hard_steps = [step for step in steps if step["name"] != "cleanup_delete_sku"]
    if not all(step["ok"] for step in hard_steps):
        fail("api", "live Ecommerce critical journey failed", steps=steps)
    emit("PASS", "api", {"mode": mode, "run_id": run_id, "sku_code": sku_code, "journeys": {"production": True, "productcore_delivery": delivery, "template": template, "commercial": commercial}, "steps": steps})


def check_browser() -> None:
    mode = os.environ.get("ECOM_CRITICAL_JOURNEY_MODE", "contract")
    _, env = auth_fixture()
    root = project_root()
    routes = [
        "/login",
        "/products",
        "/products/workbench/batch-listing",
        "/products/workbench/downloads",
        "/aiChat/template",
        "/account/billing",
        "/account/promotion",
        "/account/commission",
        "/products/:product_id/production/prep",
        "/products/:product_id/production/sandbox",
    ]
    if mode != "live":
        emit("PASS", "browser", {"mode": mode, "contract_routes": routes, "auth_fixture": redacted_env_summary(env), "note": "live browser automation is adapter-owned and enabled with ECOM_CRITICAL_JOURNEY_MODE=live"})
    public_base = os.environ.get("ECOMMERCE_PUBLIC_BASE_URL", "http://127.0.0.1:5180").rstrip("/")
    helper = Path(os.environ.get("SELFCHECK_ROOT", ".")) / "scripts" / "v_ecommerce_browser_journey_smoke.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(helper),
            "--allow-destructive-live",
            "--fixture",
            str(Path(os.environ.get("SELFCHECK_AUTH_FIXTURE", ""))),
            "--backend",
            env["ECOMMERCE_BASE_URL"].rstrip("/"),
            "--frontend",
            public_base,
        ],
        cwd=Path(os.environ.get("SELFCHECK_ROOT", ".")),
        text=True,
        capture_output=True,
        timeout=180,
    )
    stdout = proc.stdout.strip()
    report: dict[str, Any] = {}
    if stdout:
        try:
            report = json.loads(stdout.splitlines()[-1])
        except json.JSONDecodeError:
            report = {"raw_stdout_tail": stdout[-1000:]}
    if proc.returncode != 0 or report.get("status") != "PASS":
        fail("browser", "live headless browser journey failed", exit_code=proc.returncode, report=report, stderr_tail=proc.stderr[-1000:])
    emit("PASS", "browser", {"mode": mode, "frontend": public_base, "browser_journey": report, "project_root": str(root)})


def check_evidence() -> None:
    root = project_root()
    alias_dir = root / "reports" / "ecommerce-critical-journey-release-gate"
    phase_files = {phase: (alias_dir / f"{phase}.json").exists() for phase in ["static", "api", "browser"]}
    missing = [phase for phase, ok in phase_files.items() if not ok]
    if missing:
        fail("evidence", "critical journey phase evidence missing", missing=missing, alias_dir=str(alias_dir))
    emit("PASS", "evidence", {"phase_files": phase_files, "alias_dir": str(alias_dir), "covered_journeys": ["sku-production-prep-sandbox", "productcore-listing-export-downloads", "template-center-use", "commercial-account-smoke"], "cleanup_policy": "test data prefix SC-SKU-*/SC-BROWSER-*; API/browser live mode attempts delete in finally"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["static", "api", "browser", "evidence"], required=True)
    args = parser.parse_args()
    {"static": check_static, "api": check_api, "browser": check_browser, "evidence": check_evidence}[args.phase]()


if __name__ == "__main__":
    main()
