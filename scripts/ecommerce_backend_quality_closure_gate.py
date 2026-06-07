#!/usr/bin/env python3
"""Agentic SelfCheck gate for Ecommerce backend business quality closure Phase G.

The gate is deliberately safe: static/api/evidence groups run local dry-run project
smokes only. It does not run production smoke and does not print secrets. PASS_WITH_NOTES
is used whenever live/prod evidence is NOT_RUN, matching the feature contract.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SELF_ROOT = Path(__file__).resolve().parents[1]
FEATURE = "ecommerce-backend-business-quality-closure"
REPORT_DIR = SELF_ROOT / "reports" / FEATURE
BACKEND_ROOT = Path(os.environ.get("ECOM_BACKEND_ROOT", "/root/work/v/ecommerce-backend")).resolve()

SECRET_RE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._~+/=-]+|authorization\s*[:=]\s*[^\s,}]+|access[_-]?token\s*[:=]\s*[^\s,}]+|refresh[_-]?token\s*[:=]\s*[^\s,}]+|password\s*[:=]\s*[^\s,}]+|secret\s*[:=]\s*[^\s,}]+|service[_-]?secret\s*[:=]\s*[^\s,}]+|postgres://[^\s]+|mysql://[^\s]+|redis://[^\s]+)"
)

REQUIRED_BACKEND_SCRIPTS = [
    BACKEND_ROOT / "scripts" / "ecommerce-backend-critical-journey-smoke.py",
    BACKEND_ROOT / "scripts" / "ecommerce-backend-api-contract-smoke.py",
]
REQUIRED_SELFCHECK_FILES = [
    SELF_ROOT / "features" / f"{FEATURE}.yaml",
    SELF_ROOT / "verifiers" / "ecommerce-backend-quality-static.yaml",
    SELF_ROOT / "verifiers" / "ecommerce-backend-quality-api.yaml",
    SELF_ROOT / "verifiers" / "ecommerce-backend-quality-evidence.yaml",
    SELF_ROOT / "events" / "changed-ecommerce-backend-business-quality-closure.yaml",
]


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return SECRET_RE.sub("[REDACTED]", value)
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items() if "token" not in k.lower() and "secret" not in k.lower() and "password" not in k.lower()}
    return value


def emit(kind: str, status: str, details: dict[str, Any], exit_code: int = 0) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "feature": FEATURE,
        "kind": kind,
        "status": status,
        "generated_at_unix": int(time.time()),
        "selfcheck_root": str(SELF_ROOT),
        "backend_root": str(BACKEND_ROOT),
        "details": details,
    }
    sanitized = redact(payload)
    (REPORT_DIR / f"{kind}.json").write_text(json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"feature": FEATURE, "kind": kind, "status": status, "report": str(REPORT_DIR / f'{kind}.json')}, ensure_ascii=False))
    raise SystemExit(exit_code)


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "FAIL", "path": str(path), "error_type": type(exc).__name__}


def run_command(cmd: list[str], cwd: Path, timeout: int = 120) -> dict[str, Any]:
    env = os.environ.copy()
    # Preserve explicit paths but do not require or pass prod approval.
    env.pop("ECOM_PROD_SMOKE_APPROVED", None)
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout, env=env)
        return {
            "command": " ".join(cmd),
            "cwd": str(cwd),
            "exit_code": proc.returncode,
            "elapsed_ms": int((time.time() - started) * 1000),
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(cmd),
            "cwd": str(cwd),
            "exit_code": 124,
            "elapsed_ms": int((time.time() - started) * 1000),
            "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
        }


def check_static() -> None:
    missing = [str(p) for p in REQUIRED_BACKEND_SCRIPTS + REQUIRED_SELFCHECK_FILES if not p.exists()]
    script_findings: dict[str, Any] = {}
    for path in REQUIRED_BACKEND_SCRIPTS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        script_findings[str(path)] = {
            "has_prod_approval_guard": "ECOM_PROD_SMOKE_APPROVED" in text and "prod" in text and "BLOCKED" in text,
            "has_dry_run_default": "dry-run" in text and "default=True" in text,
            "writes_report_under_business_journeys": "reports" in text and "business-journeys" in text,
            "has_redaction": "SECRET_RE" in text and "REDACTED" in text,
            "mentions_no_mutation_cleanup_policy": "cleanup" in text and "writes_performed" in text,
        }
    failed_checks = {
        script: [name for name, ok in checks.items() if not ok]
        for script, checks in script_findings.items()
        if any(not ok for ok in checks.values())
    }
    details = {
        "missing_files": missing,
        "script_findings": script_findings,
        "failed_checks": failed_checks,
        "prod_smoke_ran": False,
    }
    if missing or failed_checks:
        emit("static", "BLOCK", details, 2)
    emit("static", "PASS", details, 0)


def check_api() -> None:
    script = BACKEND_ROOT / "scripts" / "ecommerce-backend-api-contract-smoke.py"
    if not script.exists():
        emit("api", "BLOCK", {"missing_script": str(script)}, 2)
    result = run_command([sys.executable, str(script), "--env", "local", "--dry-run"], BACKEND_ROOT)
    report = read_json(BACKEND_ROOT / "reports" / "quality" / "business-journeys" / "api-contract-latest.json")
    prod_status = str(report.get("prod_live_smoke", "NOT_RUN")).upper()
    full_pass_claimed = report.get("status") == "PASS" and prod_status in {"NOT_RUN", "PENDING", "REQUIRED"}
    details = {"dry_run": result, "backend_report": report, "prod_smoke_ran": False, "full_pass_claimed_with_not_run_prod": full_pass_claimed}
    if result["exit_code"] != 0 or report.get("status") not in {"PASS_WITH_NOTES", "PARTIAL_PASS", "PASS"} or full_pass_claimed:
        emit("api", "BLOCK", details, 2)
    # Dry-run is intentionally not full PASS evidence.
    emit("api", "PASS_WITH_NOTES", details, 0)


def check_evidence() -> None:
    script = BACKEND_ROOT / "scripts" / "ecommerce-backend-critical-journey-smoke.py"
    if not script.exists():
        emit("evidence", "BLOCK", {"missing_script": str(script)}, 2)
    result = run_command([sys.executable, str(script), "--env", "local", "--dry-run"], BACKEND_ROOT)
    report_path = BACKEND_ROOT / "reports" / "quality" / "business-journeys" / "latest.json"
    report = read_json(report_path)
    prod_status = str(report.get("prod_live_smoke", "NOT_RUN")).upper()
    full_pass_claimed = report.get("status") == "PASS" and prod_status in {"NOT_RUN", "PENDING", "REQUIRED"}
    journeys = report.get("journeys") or []
    missing_cleanup_policy = [j.get("id") for j in journeys if j.get("mutates") and not j.get("cleanup_required")]
    details = {
        "dry_run": result,
        "backend_report_path": str(report_path),
        "backend_report": report,
        "prod_smoke_ran": False,
        "full_pass_claimed_with_not_run_prod": full_pass_claimed,
        "missing_cleanup_policy": missing_cleanup_policy,
    }
    if result["exit_code"] != 0 or report.get("status") not in {"PASS_WITH_NOTES", "PARTIAL_PASS", "PASS"} or full_pass_claimed or missing_cleanup_policy:
        emit("evidence", "BLOCK", details, 2)
    emit("evidence", "PASS_WITH_NOTES", details, 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="SelfCheck verifier for Ecommerce backend business quality closure.")
    parser.add_argument("--kind", choices=["static", "api", "evidence"], required=True)
    args = parser.parse_args()
    {"static": check_static, "api": check_api, "evidence": check_evidence}[args.kind]()


if __name__ == "__main__":
    main()
