#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

MENU_READINESS_PATHS = [
    "/healthz",
    "/readyz",
]

MENU_CONTRACT_PATHS = [
    "GET /api/v1/menu/auth/session",
    "GET /api/v1/menu/user/credits",
    "POST /api/v1/menu/studio/assets",
    "POST /api/v1/menu/studio/jobs",
    "GET /api/v1/menu/studio/jobs",
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
    text = SECRET_RE.sub(lambda m: (m.group(1) or m.group(2) or "") + "[REDACTED]", text)
    return IP_RE.sub("[REDACTED_IP]", text)


def refuse_if_unsafe(env: str, base_url: str, platform_base_url: str | None) -> list[dict]:
    findings: list[dict] = []
    if env.lower() in PROD_LABELS:
        findings.append({"severity": "error", "message": "Menu live smoke refuses prod/prod-like env label", "env": env})
    for label, raw in [("base_url", base_url), ("platform_base_url", platform_base_url or "")]:
        if not raw:
            continue
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"}:
            findings.append({"severity": "error", "message": f"{label} must be http(s)", "value": redact(raw)})
        if env == "local" and host not in {"localhost", "127.0.0.1", "::1"}:
            findings.append({"severity": "error", "message": f"local Menu smoke only accepts loopback {label}", "value": redact(raw)})
        if PROD_HOST_RE.search(host):
            findings.append({"severity": "error", "message": f"Menu smoke refuses prod-like host in {label}", "value": redact(raw)})
    return findings


def http_probe(base_url: str, path: str, timeout: float = 2.0) -> dict:
    url = base_url.rstrip("/") + path
    started = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(512).decode("utf-8", "replace")
            return {"path": path, "url": redact(url), "status_code": resp.status, "duration_seconds": round(time.time() - started, 3), "body_tail": redact(body[-300:])}
    except urllib.error.HTTPError as exc:
        body = exc.read(512).decode("utf-8", "replace")
        return {"path": path, "url": redact(url), "status_code": exc.code, "duration_seconds": round(time.time() - started, 3), "body_tail": redact(body[-300:])}
    except Exception as exc:
        return {"path": path, "url": redact(url), "error": redact(str(exc)), "duration_seconds": round(time.time() - started, 3)}


def write_report(payload: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
        # Hard refusal means no network access at all, even read-only health probes.
        readiness.append({"status": "SKIPPED", "reason": "unsafe target refused before network probe"})
    else:
        # Readiness probes are GET-only and best-effort; a stopped local lane is recorded as BLOCKED, not overclaimed.
        for path in MENU_READINESS_PATHS:
            readiness.append(http_probe(args.base_url, path))

    live_status = "REFUSED" if unsafe else ("NOT_RUN" if not execute_requested else "BLOCKED")
    final_status = "FAIL" if live_status == "REFUSED" else "PASS_WITH_NOTES"
    if execute_requested and live_status != "REFUSED":
        findings.append({"severity": "warning", "message": "execute fixture implementation is intentionally not enabled until scoped auth fixture and cleanup assertions are wired"})
        live_status = "BLOCKED"
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
        "readiness_probes": readiness,
        "real_api_evidence": {"status": live_status, "execute_requested": execute_requested, "writes_allowed": os.environ.get("V_MENU_SMOKE_ALLOW_WRITES") == "1", "cleanup_ack": os.environ.get("V_MENU_SMOKE_CLEANUP_ACK") == "1"},
        "findings": findings,
        "generated_at_epoch": time.time(),
        "report_path": str(REPORT_PATH),
    }
    write_report(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if live_status in {"REFUSED", "BLOCKED"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
