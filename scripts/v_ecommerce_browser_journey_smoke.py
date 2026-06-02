#!/usr/bin/env python3
"""Live headless browser smoke for the V/Ecommerce critical journey adapter.

V-specific by design: logs in through the Ecommerce API, seeds a disposable SKU,
injects the browser session into the local frontend origin, and verifies protected
SKU production pages render without console/runtime errors. Reports never include
raw tokens or passwords.
"""
from __future__ import annotations

import argparse
import base64
import asyncio
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import websockets


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def http_json(base: str, path: str, method: str = "GET", payload: dict[str, Any] | None = None, token: str | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "agentic-selfcheck-browser-journey/0.1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8", "replace")
        parsed = json.loads(body) if body.strip().startswith("{") else {}
        return {"status": resp.status, "json": parsed}


def extract_token(payload: dict[str, Any]) -> str | None:
    obj = payload.get("json") if isinstance(payload.get("json"), dict) else payload
    candidates = [obj]
    if isinstance(obj, dict) and isinstance(obj.get("data"), dict):
        candidates.append(obj["data"])
    for candidate in candidates:
        if isinstance(candidate, dict):
            for key in ("token", "access_token", "accessToken", "jwt"):
                value = candidate.get(key)
                if isinstance(value, str) and value:
                    return value
    return None


def login(base: str, env: dict[str, str]) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    for label, email_key, password_key in (
        ("ecommerce", "ECOMMERCE_AUTH_EMAIL", "ECOMMERCE_AUTH_PASSWORD"),
        ("platform", "PLATFORM_DEV_ADMIN_EMAIL", "PLATFORM_DEV_ADMIN_PASSWORD"),
    ):
        email = env.get(email_key)
        password = env.get(password_key)
        if not email or not password:
            continue
        try:
            result = http_json(base, "/api/v1/ecommerce/auth/login", "POST", {"email": email, "password": password})
            token = extract_token(result)
            attempts.append({"source": label, "status": result.get("status"), "token_present": bool(token)})
            if token:
                data = result.get("json", {}).get("data") if isinstance(result.get("json"), dict) else {}
                return token, (data if isinstance(data, dict) else {}), attempts
        except Exception as exc:  # redacted by design: no credentials in error
            attempts.append({"source": label, "error": type(exc).__name__})
    raise RuntimeError("login failed: " + json.dumps(attempts, ensure_ascii=False))


def object_payload(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def create_product(base: str, token: str, prefix: str = "SC-BROWSER", title_prefix: str = "SelfCheck Browser SKU") -> tuple[str, str]:
    run_id = str(time.time_ns())
    sku = f"{prefix}-{run_id[-12:]}"
    payload = {
        "sku_code": sku,
        "title": f"{title_prefix} {run_id[-12:]}",
        "brand": "SelfCheck",
        "category": "QA",
        "metadata": {"created_by": "agentic-selfcheck-browser", "run_id": run_id},
    }
    result = http_json(base, "/api/v1/ecommerce/products", "POST", payload, token)
    data = result.get("json", {}).get("data") if isinstance(result.get("json"), dict) else {}
    product = data.get("product") if isinstance(data, dict) and isinstance(data.get("product"), dict) else data
    product_id = product.get("id") if isinstance(product, dict) else None
    if not product_id:
        raise RuntimeError("product create failed")
    return str(product_id), sku


def create_pagination_fixture_products(base: str, token: str, count: int = 11) -> tuple[list[str], str]:
    ids: list[str] = []
    oldest_sku = ""
    for index in range(count):
        product_id, sku = create_product(base, token, "SC-PAGE", "SelfCheck Pagination SKU")
        ids.append(product_id)
        if index == 0:
            oldest_sku = sku
        time.sleep(0.01)
    return ids, oldest_sku


def create_visual_session(base: str, token: str, product_id: str, sku: str) -> str:
    result = http_json(base, f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id)}/v2/visual-sessions", "POST", {"sku_code": sku, "title": "SelfCheck semantic journey"}, token)
    data = result.get("json", {}).get("data") if isinstance(result.get("json"), dict) else {}
    session_id = data.get("id") if isinstance(data, dict) else None
    if not session_id:
        session = object_payload(data.get("session")) if isinstance(data, dict) else {}
        session_id = session.get("id")
    if not session_id:
        raise RuntimeError("visual session create failed")
    return str(session_id)


def seed_semantic_contract_state(base: str, token: str, product_id: str, sku: str) -> dict[str, Any]:
    """Drive the current deterministic semantic boundary.

    The local environment intentionally has no stable provider-backed image bytes
    or Prompt Center snapshot. The expected release-gate behavior is therefore
    fail-closed/contract-needed, not fake generation success.
    """
    run_id = sku.replace("SC-BROWSER-", "")
    session_id = create_visual_session(base, token, product_id, sku)
    source_results: list[dict[str, Any]] = []
    for role in ("sku", "reference"):
        result = http_json(
            base,
            f"/api/v1/ecommerce/v2/visual-workflows/{urllib.parse.quote(session_id)}/source-references",
            "POST",
            {
                "source_kind": "url",
                "source_url": f"https://example.com/selfcheck-{role}.jpg",
                "source_ref": f"selfcheck-{role}",
                "mime_type": "image/jpeg",
                "metadata": {"source_role": role, "file_name": f"selfcheck-{role}.jpg"},
            },
            token,
        )
        data = result.get("json", {}).get("data", {}) if isinstance(result.get("json"), dict) else {}
        source_results.append({"role": role, "status": result.get("status"), "source_status": data.get("status"), "resolve_status": data.get("resolve_status")})

    selections = []
    for slot, decision, label in [
        ("sku_product", "keep", "要，保留 SKU 产品主体"),
        ("sku_background", "drop", "不要，改换 SKU 背景"),
        ("reference_product", "drop", "不要使用参考产品元素"),
        ("reference_background", "keep", "要，采用参考背景场景"),
    ]:
        selections.append({
            "element_id": "fixed:" + slot,
            "element_type": "product_fact" if "product" in slot else "background",
            "element_key": slot,
            "decision": decision,
            "label": label,
            "value": {"description": label},
            "metadata": {
                "fixed_prompt_question": True,
                "prompt_slot": slot,
                "source_role": "sku" if slot.startswith("sku") else "reference",
                "semantic_action": decision,
            },
        })
    http_json(
        base,
        f"/api/v1/ecommerce/v2/visual-workflows/{urllib.parse.quote(session_id)}",
        "PATCH",
        {
            "current_stage": "prompt",
            "intent_spec": {
                "schema_version": "v1",
                "product_id": product_id,
                "selections": selections,
                "requirements": {"attribute_drift": {"reference_bias": 50, "sku_bias": 50, "mode": "balanced"}},
                "metadata": {"updated_from": "selfcheck-semantic-smoke"},
            },
        },
        token,
    )
    prompt = http_json(
        base,
        f"/api/v1/ecommerce/v2/visual-workflows/{urllib.parse.quote(session_id)}/prompt-planner-jobs",
        "POST",
        {
            "marketplace": "amazon",
            "locale": "zh-CN",
            "template_id": "selfcheck-template",
            "prompt_variables": {"prompt_diff": True},
            "idempotency_key": "selfcheck-prompt:" + run_id,
        },
        token,
    )
    prompt_data = prompt.get("json", {}).get("data", {}) if isinstance(prompt.get("json"), dict) else {}
    stage = http_json(base, f"/api/v1/ecommerce/v2/visual-workflows/{urllib.parse.quote(session_id)}/stage-view", token=token)
    stage_data = stage.get("json", {}).get("data", {}) if isinstance(stage.get("json"), dict) else {}
    prompt_plan = object_payload(stage_data.get("prompt_plan"))
    generation = http_json(
        base,
        f"/api/v1/ecommerce/v2/visual-workflows/{urllib.parse.quote(session_id)}/generation-versions",
        "POST",
        {
            "prompt_id": prompt_plan.get("prompt_id") or "selfcheck-missing-prompt",
            "status": "queued",
            "stage": "queued",
            "progress": 0,
            "idempotency_key": "selfcheck-generation:" + run_id,
            "metadata": {"source": "selfcheck-semantic-smoke"},
        },
        token,
    )
    generation_data = generation.get("json", {}).get("data", {}) if isinstance(generation.get("json"), dict) else {}
    prompt_blocker_codes = [b.get("code") for b in prompt_data.get("blockers", []) if isinstance(b, dict)]
    generation_blocker_codes = [b.get("code") for b in generation_data.get("blockers", []) if isinstance(b, dict)]
    semantic_ok = (
        len(selections) == 4
        and prompt_data.get("status") == "contract_needed"
        and "SKU_FACTS_REQUIRED" in prompt_blocker_codes
        and generation_data.get("status") == "contract_needed"
        and not generation_data.get("result_assets")
    )
    return {
        "ok": semantic_ok,
        "session_id": session_id,
        "source_references": source_results,
        "selection_count": len(selections),
        "prompt_planner": {"status": prompt_data.get("status"), "blocker_codes": prompt_blocker_codes},
        "prompt_plan": {"status": prompt_plan.get("status"), "prompt_id_present": bool(prompt_plan.get("prompt_id"))},
        "generation": {"status": generation_data.get("status"), "blocker_codes": generation_blocker_codes, "result_asset_count": len(generation_data.get("result_assets") or [])},
        "expected_boundary": "contract_needed_without_fake_generation_assets",
    }



def data_payload(resp: dict[str, Any]) -> Any:
    obj = resp.get("json") if isinstance(resp.get("json"), dict) else {}
    return obj.get("data") if isinstance(obj, dict) and "data" in obj else obj


def payload_id(resp: dict[str, Any]) -> str | None:
    data = data_payload(resp)
    if isinstance(data, dict):
        value = data.get("id") or data.get("package_id") or data.get("templateInstanceId") or data.get("template_instance_id")
        return str(value) if value else None
    return None


def seed_productcore_delivery_state(base: str, token: str, product_id: str, sku: str) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    def record(name: str, resp: dict[str, Any], **extra: Any) -> dict[str, Any]:
        item = {"name": name, "status": resp.get("status"), "ok": 200 <= int(resp.get("status", 0)) < 300, **extra}
        steps.append(item)
        return item
    payload = "data:image/png;base64," + base64.b64encode(b"selfcheck-pixel").decode("ascii")
    asset = http_json(base, "/api/v1/ecommerce/assets/source", "POST", {
        "product_id": product_id,
        "sku_code": sku,
        "file_name": "selfcheck-source.png",
        "mime_type": "image/png",
        "payload": payload,
        "width": 16,
        "height": 16,
        "metadata": {"source": "agentic-selfcheck-browser", "semantic": "delivery-contract"},
    }, token)
    asset_id = payload_id(asset)
    record("register_source_asset", asset, asset_id_present=bool(asset_id))
    relation_id = None
    if asset_id:
        relation = http_json(base, f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id)}/assets", "POST", {"asset_id": asset_id, "relation_type": "primary", "asset_role": "hero", "is_primary": True}, token)
        relation_id = payload_id(relation)
        record("attach_primary_asset", relation, relation_id_present=bool(relation_id))
        record("mark_assets_ready", http_json(base, f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id)}/status", "PATCH", {"status": "assets_ready"}, token))
    listing = http_json(base, f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id)}/listing-versions", "POST", {
        "version_label": "SelfCheck Delivery", "title": "SelfCheck Listing " + sku, "description": "Deterministic listing", "bullet_points": ["SelfCheck bullet"], "keywords": ["selfcheck"], "platform": "amazon", "site": "US", "locale": "en-US",
    }, token)
    listing_id = payload_id(listing)
    record("create_listing_version", listing, listing_id_present=bool(listing_id))
    if listing_id:
        record("adopt_listing_version", http_json(base, f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id)}/listing-versions/adopt", "POST", {"version_id": listing_id}, token))
    record("calculate_profit_snapshot", http_json(base, f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id)}/profit-snapshots/calculate", "POST", {"platform": "amazon", "site": "US", "cost_price": 10, "listing_price": 20, "logistics_cost": 2, "platform_fee": 1}, token))
    export_task = http_json(base, f"/api/v1/ecommerce/products/{urllib.parse.quote(product_id)}/export-tasks", "POST", {"platform": "amazon", "site": "US", "locale": "en-US", "format": "json", "asset_relation_ids": [relation_id] if relation_id else None}, token)
    record("create_export_task", export_task, export_task_id_present=bool(payload_id(export_task)))
    package = http_json(base, "/api/v1/ecommerce/export-packages", "POST", {"items": [{"product_id": product_id}], "platform": "amazon", "site": "US", "locale": "en-US", "format": "json"}, token)
    record("create_export_package", package, package_id_present=bool(payload_id(package)))
    downloads = http_json(base, "/api/v1/ecommerce/downloads", token=token)
    data = data_payload(downloads)
    items = data if isinstance(data, list) else (data.get("items", []) if isinstance(data, dict) else [])
    record("list_downloads", downloads, download_count=len(items) if isinstance(items, list) else 0)
    return {"ok": all(step.get("ok") for step in steps), "steps": steps}


def seed_template_commercial_state(base: str, token: str) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    def record(name: str, resp: dict[str, Any], **extra: Any) -> None:
        steps.append({"name": name, "status": resp.get("status"), "ok": 200 <= int(resp.get("status", 0)) < 300, **extra})
    catalog = http_json(base, "/api/v1/ecommerce/template-center/catalog?locale=zh-CN&modality=image&sortBy=recommended", token=token)
    data = data_payload(catalog)
    items = data if isinstance(data, list) else []
    template_id = str(items[0].get("id")) if items and isinstance(items[0], dict) and items[0].get("id") else None
    record("template_catalog", catalog, template_id_present=bool(template_id), template_count=len(items))
    record("template_facets", http_json(base, "/api/v1/ecommerce/template-center/catalog/facets?locale=zh-CN", token=token))
    if template_id:
        record("template_detail", http_json(base, "/api/v1/ecommerce/template-center/catalog/" + urllib.parse.quote(template_id) + "?locale=zh-CN", token=token))
        record("template_favorite", http_json(base, "/api/v1/ecommerce/template-center/catalog/" + urllib.parse.quote(template_id) + "/favorite", "POST", {}, token))
        record("template_unfavorite", http_json(base, "/api/v1/ecommerce/template-center/catalog/" + urllib.parse.quote(template_id) + "/favorite", "DELETE", token=token))
        use = http_json(base, "/api/v1/ecommerce/template-center/catalog/" + urllib.parse.quote(template_id) + "/use", "POST", {}, token)
        use_data = data_payload(use)
        record("template_use", use, preloaded_payload_present=isinstance(use_data, dict) and bool(use_data.get("preloadedTemplatePayload") or use_data.get("preloaded_template_payload")))
    for name, path in [("commercial_offerings", "/api/v1/ecommerce/commercial/offerings"), ("wallet_summary", "/api/v1/ecommerce/wallet/summary"), ("billing_summary", "/api/v1/ecommerce/billing/summary"), ("promotion_programs", "/api/v1/ecommerce/promotions/programs"), ("commission_overview", "/api/v1/ecommerce/commissions/me/overview")]:
        record(name, http_json(base, path, token=token))
    return {"ok": all(step.get("ok") for step in steps), "steps": steps}

def cleanup_product(base: str, token: str, product_id: str) -> dict[str, Any]:
    try:
        result = http_json(base, "/api/v1/ecommerce/products/" + urllib.parse.quote(product_id), "DELETE", token=token)
        return {"status": result.get("status"), "ok": 200 <= int(result.get("status", 0)) < 300}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class CdpPage:
    def __init__(self, ws: Any):
        self.ws = ws
        self.next_id = 0
        self.pending: dict[int, asyncio.Future] = {}
        self.console: list[dict[str, str]] = []
        self.exceptions: list[str] = []
        self.failed_requests: list[dict[str, str]] = []

    async def reader(self) -> None:
        async for raw in self.ws:
            msg = json.loads(raw)
            if "id" in msg and msg["id"] in self.pending:
                self.pending.pop(msg["id"]).set_result(msg)
                continue
            method = msg.get("method")
            params = msg.get("params", {})
            if method == "Runtime.consoleAPICalled":
                text = " ".join(str(arg.get("value", arg.get("description", ""))) for arg in params.get("args", []))
                self.console.append({"type": params.get("type", ""), "text": text[:500]})
            elif method == "Runtime.exceptionThrown":
                details = params.get("exceptionDetails", {})
                self.exceptions.append(str(details.get("text") or details.get("exception", {}).get("description") or "exception")[:500])
            elif method == "Network.loadingFailed":
                self.failed_requests.append({"requestId": str(params.get("requestId", "")), "errorText": str(params.get("errorText", ""))[:200]})

    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.next_id += 1
        fut = asyncio.get_running_loop().create_future()
        self.pending[self.next_id] = fut
        await self.ws.send(json.dumps({"id": self.next_id, "method": method, "params": params or {}}))
        result = await asyncio.wait_for(fut, timeout=20)
        if "error" in result:
            raise RuntimeError(f"CDP {method} failed: {result['error']}")
        return result.get("result", {})

    async def eval(self, expression: str) -> Any:
        result = await self.call("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
        remote = result.get("result", {})
        if "value" in remote:
            return remote["value"]
        return remote.get("description")

    async def wait_ready(self) -> None:
        for _ in range(80):
            state = await self.eval("document.readyState")
            if state == "complete":
                break
            await asyncio.sleep(0.1)
        await asyncio.sleep(1.0)

    async def snapshot_assert(self, must_contain: list[str], label: str, before_console: int, before_exceptions: int) -> dict[str, Any]:
        text = await self.eval("document.body ? document.body.innerText.slice(0, 12000) : ''")
        href = await self.eval("location.href")
        placeholder_hrefs = await self.eval("Array.from(document.querySelectorAll('a[href]')).map(a => a.href).filter(h => h.includes(':productId') || h.includes(':id')).slice(0, 10)")
        missing = [needle for needle in must_contain if needle not in text]
        return {
            "label": label,
            "url": href,
            "ok": not missing and "Unexpected Application Error" not in text and not placeholder_hrefs,
            "missing": missing,
            "placeholder_hrefs": placeholder_hrefs,
            "console_error_count": len([m for m in self.console[before_console:] if m.get("type") in {"error", "assert"}]),
            "exception_count": len(self.exceptions) - before_exceptions,
            "text_sample": text[:500],
        }

    async def navigate(self, url: str, must_contain: list[str], label: str) -> dict[str, Any]:
        before_console = len(self.console)
        before_exceptions = len(self.exceptions)
        await self.call("Page.navigate", {"url": url})
        await self.wait_ready()
        return await self.snapshot_assert(must_contain, label, before_console, before_exceptions)

    async def click_next_page_and_assert(self, must_contain: list[str]) -> dict[str, Any]:
        before_console = len(self.console)
        before_exceptions = len(self.exceptions)
        expression = """
(() => {
  const buttons = Array.from(document.querySelectorAll('button'));
  const button = buttons.find(b => (b.textContent || '').includes('下一页'));
  if (!button) return {clicked: false, reason: 'missing_next_button'};
  if (button.disabled) return {clicked: false, reason: 'next_button_disabled'};
  button.click();
  return {clicked: true, text: button.textContent};
})()
"""
        clicked = await self.eval(expression)
        await asyncio.sleep(0.5)
        result = await self.snapshot_assert(must_contain, "sku_pagination_next_page", before_console, before_exceptions)
        result["click"] = clicked
        result["ok"] = bool(clicked.get("clicked") if isinstance(clicked, dict) else False) and result["ok"]
        return result

    async def click_production_link_for_product(self, product_id: str) -> dict[str, Any]:
        before_console = len(self.console)
        before_exceptions = len(self.exceptions)
        expression = """
(pid => {
  const links = Array.from(document.querySelectorAll('a[href]'));
  const link = links.find(a => a.href.includes(`/products/${pid}/production/prep`) && a.textContent.includes('进入视觉生产'));
  if (!link) return {clicked: false, hrefs: links.map(a => a.href).filter(h => h.includes(pid)).slice(0, 10)};
  link.click();
  return {clicked: true, href: link.href};
})(%s)
""" % json.dumps(product_id)
        clicked = await self.eval(expression)
        await self.wait_ready()
        result = await self.snapshot_assert(["Production Prep", "SKU Source Upload"], "click_product_center_to_prep", before_console, before_exceptions)
        result["click"] = clicked
        result["ok"] = bool(clicked.get("clicked") if isinstance(clicked, dict) else False) and product_id in str(result.get("url")) and result["ok"]
        return result


async def run_browser(frontend: str, token: str, session_payload: dict[str, Any], product_id: str, sku: str, pagination_sku: str) -> dict[str, Any]:
    port = free_port()
    user_data = tempfile.TemporaryDirectory(prefix="selfcheck-chrome-", ignore_cleanup_errors=True)
    proc = subprocess.Popen([
        "/usr/bin/chromium",
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data.name}",
        "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        version = None
        for _ in range(80):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1) as resp:
                    pages = json.loads(resp.read().decode())
                    if pages:
                        version = pages[0]
                        break
            except Exception:
                await asyncio.sleep(0.1)
        if not version:
            raise RuntimeError("chromium CDP did not become ready")
        async with websockets.connect(version["webSocketDebuggerUrl"], max_size=8_000_000) as ws:
            page = CdpPage(ws)
            reader_task = asyncio.create_task(page.reader())
            await page.call("Runtime.enable")
            await page.call("Page.enable")
            await page.call("Network.enable")
            frontend = frontend.rstrip("/")
            steps: list[dict[str, Any]] = []
            steps.append(await page.navigate(frontend + "/login", ["Sign In"], "login_public"))
            safe_session = {k: v for k, v in session_payload.items() if k != "token"}
            storage_expr = """
(() => {
  localStorage.setItem('ecommerce_access_token', %s);
  localStorage.setItem('ecommerce_session', %s);
  return true;
})()
""" % (json.dumps(token), json.dumps(json.dumps(safe_session, ensure_ascii=False)))
            await page.eval(storage_expr)
            steps.append(await page.navigate(frontend + "/products", [sku, "进入视觉生产", "下一页"], "product_center_lists_created_sku"))
            steps.append(await page.click_next_page_and_assert([pagination_sku]))
            steps.append(await page.navigate(frontend + "/products/workbench/batch-listing", [sku], "batch_listing_contains_created_sku"))
            steps.append(await page.navigate(frontend + "/products/workbench/downloads", ["Delivery"], "downloads_page_renders"))
            steps.append(await page.navigate(frontend + "/aiChat/template", ["Template"], "template_center_page_renders"))
            steps.append(await page.navigate(frontend + "/account/billing", ["Billing"], "billing_page_renders"))
            steps.append(await page.navigate(frontend + "/account/promotion", ["Promotion"], "promotion_page_renders"))
            steps.append(await page.navigate(frontend + "/account/commission", ["Commission"], "commission_page_renders"))
            steps.append(await page.navigate(frontend + "/products", [sku, "进入视觉生产"], "product_center_before_click"))
            steps.append(await page.click_production_link_for_product(product_id))
            steps.append(await page.navigate(frontend + "/products/" + urllib.parse.quote(product_id) + "/production/prep", ["Production Prep", "SKU Source Upload"], "prep_direct"))
            steps.append(await page.navigate(frontend + "/products/" + urllib.parse.quote(product_id) + "/production/sandbox", ["Intent Configuration", "补齐生成条件"], "sandbox_blocked_until_ready"))
            await asyncio.sleep(0.2)
            reader_task.cancel()
            console_errors = [m for m in page.console if m.get("type") in {"error", "assert"}]
            return {
                "steps": steps,
                "console_errors": console_errors[:10],
                "exception_count": len(page.exceptions),
                "failed_request_count": len(page.failed_requests),
                "failed_requests": page.failed_requests[:10],
            }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        user_data.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--frontend", required=True)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--allow-destructive-live", action="store_true", help="required acknowledgement: this smoke creates and deletes disposable Ecommerce test data")
    args = parser.parse_args()
    if not args.allow_destructive_live:
        raise SystemExit("refusing to run destructive live browser smoke without --allow-destructive-live")
    env = load_env(Path(args.fixture).expanduser())
    token = ""
    product_id = ""
    pagination_product_ids: list[str] = []
    cleanup: dict[str, Any] = {"ok": False, "skipped": True}
    try:
        token, session_payload, login_attempts = login(args.backend, env)
        pagination_product_ids, pagination_sku = create_pagination_fixture_products(args.backend, token)
        product_id, sku = create_product(args.backend, token)
        semantic = seed_semantic_contract_state(args.backend, token, product_id, sku)
        delivery = seed_productcore_delivery_state(args.backend, token, product_id, sku)
        template_commercial = seed_template_commercial_state(args.backend, token)
        browser = asyncio.run(run_browser(args.frontend, token, session_payload, product_id, sku, pagination_sku))
        cleanup_main = cleanup_product(args.backend, token, product_id)
        cleanup_page = [cleanup_product(args.backend, token, item) for item in pagination_product_ids]
        cleanup = {"main": cleanup_main, "pagination": cleanup_page, "ok": cleanup_main.get("ok") and all(item.get("ok") for item in cleanup_page)}
        ok_steps = all(step.get("ok") for step in browser["steps"])
        ok = bool(semantic.get("ok")) and bool(delivery.get("ok")) and bool(template_commercial.get("ok")) and ok_steps and not browser["console_errors"] and browser["exception_count"] == 0
        report = {
            "status": "PASS" if ok else "FAIL",
            "product_id": product_id,
            "sku_code": sku,
            "pagination_probe_sku": pagination_sku,
            "login_attempts": login_attempts,
            "semantic_contract": semantic,
            "productcore_delivery": delivery,
            "template_commercial": template_commercial,
            "steps": browser["steps"],
            "console_errors": browser["console_errors"],
            "exception_count": browser["exception_count"],
            "failed_request_count": browser["failed_request_count"],
            "cleanup": cleanup,
        }
        print(json.dumps(report, ensure_ascii=False))
        return 0 if ok else 2
    except Exception as exc:
        if token and product_id:
            cleanup = cleanup_product(args.backend, token, product_id)
        if token and pagination_product_ids:
            for item in pagination_product_ids:
                cleanup_product(args.backend, token, item)
        print(json.dumps({"status": "FAIL", "message": type(exc).__name__, "cleanup": cleanup}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
