#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
V_ROOT = ROOT.parent / "v"
REPORT_DIR = V_ROOT / "reports" / "evidence-contract" / "menu-studio-core-chain"
REPORT_PATH = REPORT_DIR / "v-menu-safe-contract-smoke.json"

MENU_READINESS_PATHS = ["/healthz", "/readyz"]
MENU_CONTRACT_PATHS = [
    "GET /api/v1/menu/auth/session",
    "GET /api/v1/menu/user/credits",
    "POST /api/v1/menu/studio/assets",
    "POST /api/v1/menu/studio/jobs",
    "POST /api/v1/menu/studio/jobs/{jobID}/cancel",
    "GET /api/v1/menu/studio/jobs/{jobID}",
    "GET /api/v1/menu/studio/history/jobs",
    "GET /api/v1/menu/studio/library/assets",
    "POST /internal/v1/menu/studio/jobs/{jobID}/runtime",
    "POST /internal/v1/menu/studio/jobs/{jobID}/results",
]

PROD_LABELS = {"prod", "production", "cloud", "mix", "release", "prod-candidate"}
PROD_HOST_RE = re.compile(r"(prod|production|cloud|mix|agent-ecommerce|ai-menu|menu\.guo|menu\.ai|\.com$|\.cn$)", re.I)
SECRET_RE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+|((?:token|password|secret|api[_-]?key|authorization)\s*[:=]\s*)\S+")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def redact(text: str) -> str:
    text = SECRET_RE.sub(lambda m: (m.group(1) or m.group(2) or "") + "[REDACTED]", str(text))
    return IP_RE.sub("[REDACTED_IP]", text)


def refuse_if_unsafe(env: str, base_url: str, platform_base_url: str | None) -> list[dict]:
    findings: list[dict] = []
    env_lower = env.lower()
    if env_lower in PROD_LABELS:
        findings.append({"severity": "error", "message": "Menu live smoke refuses prod/prod-like env label", "env": env})
    for label, raw in [("base_url", base_url), ("platform_base_url", platform_base_url or "")]:
        if not raw:
            continue
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"}:
            findings.append({"severity": "error", "message": f"{label} must be http(s)", "value": redact(raw)})
        if env_lower == "local" and host not in {"localhost", "127.0.0.1", "::1"}:
            findings.append({"severity": "error", "message": f"local Menu smoke only accepts loopback {label}", "value": redact(raw)})
        if PROD_HOST_RE.search(host):
            findings.append({"severity": "error", "message": f"Menu smoke refuses prod-like host in {label}", "value": redact(raw)})
    return findings


def request(base_url: str, method: str, path: str, token: str = "", body: dict | None = None, timeout: float = 6.0) -> dict:
    url = base_url.rstrip("/") + path
    started = time.time()
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(4096).decode("utf-8", "replace")
            parsed = parse_json(raw)
            return {"method": method, "path": path, "url": redact(url), "status_code": resp.status, "ok": 200 <= resp.status < 300, "duration_seconds": round(time.time() - started, 3), "body": parsed, "body_tail": redact(raw[-500:])}
    except urllib.error.HTTPError as exc:
        raw = exc.read(4096).decode("utf-8", "replace")
        return {"method": method, "path": path, "url": redact(url), "status_code": exc.code, "ok": False, "duration_seconds": round(time.time() - started, 3), "body": parse_json(raw), "body_tail": redact(raw[-500:])}
    except Exception as exc:
        return {"method": method, "path": path, "url": redact(url), "ok": False, "duration_seconds": round(time.time() - started, 3), "error": redact(str(exc))}


def parse_json(raw: str):
    try:
        return json.loads(raw) if raw else None
    except Exception:
        return {"raw": raw[-500:]}


def data_of(envelope):
    if isinstance(envelope, dict) and "data" in envelope:
        return envelope.get("data")
    return envelope


def write_report(payload: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tiny_png_data_url(label: str) -> str:
    # 1x1 transparent PNG with deterministic payload; label is not embedded to avoid leaking fixture details.
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def run_execute_smoke(base_url: str, token: str) -> tuple[str, list[dict], dict]:
    findings: list[dict] = []
    evidence: dict = {"steps": [], "created_asset_ids": [], "created_job_id": "", "cleanup": {}}

    def step(name: str, result: dict, required_ok: bool = True) -> bool:
        redacted_result = {k: v for k, v in result.items() if k != "body"}
        redacted_result["body_shape"] = shape_of(result.get("body"))
        evidence["steps"].append({"name": name, **redacted_result})
        if required_ok and not result.get("ok"):
            findings.append({"severity": "error", "message": f"{name} failed", "result": redacted_result})
            return False
        return bool(result.get("ok"))

    if not step("auth/session", request(base_url, "GET", "/api/v1/menu/auth/session", token)):
        return "FAIL", findings, evidence

    roles = ["dish_photo", "brand_logo", "menu_reference", "style_reference"]
    source_assets = []
    for idx, role in enumerate(roles, start=1):
        body = {
            "asset_type": "source",
            "source_type": "upload",
            "file_name": f"menu-smoke-{role}.png",
            "mime_type": "image/png",
            "source_url": tiny_png_data_url(role),
            "metadata": {"qa_smoke": True, "role": role},
        }
        result = request(base_url, "POST", "/api/v1/menu/studio/assets", token, body, timeout=12)
        if not step(f"register_asset/{role}", result):
            return "FAIL", findings, evidence
        data = data_of(result.get("body")) or {}
        asset_id = data.get("id") or data.get("asset_id")
        if not asset_id:
            findings.append({"severity": "error", "message": "asset registration response missing id", "role": role})
            return "FAIL", findings, evidence
        evidence["created_asset_ids"].append(asset_id)
        source_assets.append({"asset_id": asset_id, "role": role})

    create_body = {
        "mode": "single",
        "input_mode": "ask_for_required_input",
        "generation_strategy": "ask_for_required_input",
        "source_asset_ids": [x["asset_id"] for x in source_assets],
        "source_assets": source_assets,
        "prompt": "QA smoke: verify role-aware multi-image contract only.",
        "metadata": {"qa_smoke": True, "smoke_scope": "menu-safe-live-business-smoke"},
    }
    create = request(base_url, "POST", "/api/v1/menu/studio/jobs", token, create_body, timeout=20)
    if not step("create_multi_image_job", create):
        body = create.get("body") or {}
        err_code = body.get("error_code") if isinstance(body, dict) else ""
        if err_code in {"STUDIO_BILLING_CONFIG_MISSING", "STUDIO_BILLING_UPSTREAM_FAILED", "STUDIO_ASSET_STORAGE_NOT_READY"}:
            return "BLOCKED", findings, evidence
        return "FAIL", findings, evidence
    job = data_of(create.get("body")) or {}
    job_id = job.get("job_id") or job.get("id")
    evidence["created_job_id"] = job_id or ""
    if job.get("input_mode") != "multi_image":
        findings.append({"severity": "error", "message": "created job did not normalize to multi_image", "actual_input_mode": job.get("input_mode")})
    if job.get("provider") != "comfyui_bridge":
        findings.append({"severity": "error", "message": "created job did not route to comfyui_bridge", "actual_provider": job.get("provider")})

    if job_id:
        detail = request(base_url, "GET", f"/api/v1/menu/studio/jobs/{job_id}", token)
        step("job_detail", detail, required_ok=False)
        cancel = request(base_url, "POST", f"/api/v1/menu/studio/jobs/{job_id}/cancel", token, timeout=12)
        evidence["cleanup"] = {k: v for k, v in cancel.items() if k != "body"}
        if not cancel.get("ok"):
            findings.append({"severity": "warning", "message": "job cleanup/cancel did not succeed", "result": evidence["cleanup"]})

    history = request(base_url, "GET", "/api/v1/menu/studio/history/jobs?limit=5", token)
    step("history_readback", history, required_ok=False)
    library = request(base_url, "GET", "/api/v1/menu/studio/library/assets?limit=5", token)
    step("library_readback", library, required_ok=False)

    if any(f.get("severity") == "error" for f in findings):
        return "FAIL", findings, evidence
    if any(f.get("severity") == "warning" for f in findings):
        return "PASS_WITH_NOTES", findings, evidence
    return "PASS", findings, evidence


def shape_of(value):
    if isinstance(value, dict):
        return {k: shape_of(v) for k, v in list(value.items())[:12] if k.lower() not in {"access_token", "token", "authorization"}}
    if isinstance(value, list):
        return [shape_of(value[0])] if value else []
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if value is None:
        return None
    return type(value).__name__


def main() -> int:
    ap = argparse.ArgumentParser(description="Safe Menu local/dev contract smoke harness")
    ap.add_argument("--env", default="local", choices=["local", "dev"], help="Safe lane label; prod/cloud labels are refused")
    ap.add_argument("--base-url", default="http://127.0.0.1:8196", help="Menu backend base URL")
    ap.add_argument("--platform-base-url", default="http://127.0.0.1:8195", help="Platform backend base URL for lane classification")
    ap.add_argument("--execute", action="store_true", help="Run real local/dev fixture smoke; requires write and cleanup acknowledgements")
    ap.add_argument("--dry-run", action="store_true", help="Only validate safety/readiness; no writes")
    args = ap.parse_args()

    findings = refuse_if_unsafe(args.env, args.base_url, args.platform_base_url)
    execute_requested = args.execute and not args.dry_run
    if execute_requested:
        if os.environ.get("V_MENU_SMOKE_ALLOW_WRITES") != "1":
            findings.append({"severity": "error", "message": "execute mode requires V_MENU_SMOKE_ALLOW_WRITES=1"})
        if os.environ.get("V_MENU_SMOKE_CLEANUP_ACK") != "1":
            findings.append({"severity": "error", "message": "execute mode requires V_MENU_SMOKE_CLEANUP_ACK=1"})
        if not os.environ.get("V_MENU_SMOKE_FIXTURE_TOKEN"):
            findings.append({"severity": "error", "message": "execute mode requires a scoped V_MENU_SMOKE_FIXTURE_TOKEN"})

    readiness = []
    unsafe = any(f.get("severity") == "error" for f in findings)
    if unsafe:
        readiness.append({"status": "SKIPPED", "reason": "unsafe target refused before network probe"})
    else:
        for path in MENU_READINESS_PATHS:
            readiness.append(request(args.base_url, "GET", path))

    fixture_evidence = {}
    if unsafe:
        live_status = "REFUSED"
        final_status = "FAIL"
    elif execute_requested:
        live_status, fixture_findings, fixture_evidence = run_execute_smoke(args.base_url, os.environ.get("V_MENU_SMOKE_FIXTURE_TOKEN", ""))
        findings.extend(fixture_findings)
        final_status = "PASS" if live_status == "PASS" else ("PASS_WITH_NOTES" if live_status in {"PASS_WITH_NOTES", "BLOCKED"} else "FAIL")
    else:
        live_status = "NOT_RUN"
        final_status = "PASS_WITH_NOTES"

    payload = {
        "feature": "v-menu-contract-evidence-bridge",
        "verifier": "v-menu-safe-contract-smoke",
        "status": final_status,
        "env": args.env,
        "mode": "execute" if execute_requested else "dry_run",
        "base_url": redact(args.base_url),
        "platform_base_url": redact(args.platform_base_url),
        "contract_paths": MENU_CONTRACT_PATHS,
        "readiness_probes": [{k: v for k, v in p.items() if k != "body"} for p in readiness],
        "real_api_evidence": {
            "status": live_status,
            "execute_requested": execute_requested,
            "writes_allowed": os.environ.get("V_MENU_SMOKE_ALLOW_WRITES") == "1",
            "cleanup_ack": os.environ.get("V_MENU_SMOKE_CLEANUP_ACK") == "1",
            "fixture": fixture_evidence,
        },
        "findings": findings,
        "generated_at_epoch": time.time(),
        "report_path": str(REPORT_PATH),
    }
    write_report(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if live_status in {"REFUSED", "FAIL", "BLOCKED"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
