#!/usr/bin/env python3
"""Agentic SelfCheck gate for Ecommerce backend business quality closure.

The gate is deliberately prod-safe: static/api/evidence groups run local isolated
fixture execution only. They never call prod, never require prod approval, and never
print secrets. Local execute PASS is accepted as gate PASS; the report still records
a semantic PASS_WITH_NOTES reason when the only omitted evidence is prod_live_smoke.
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
    BACKEND_ROOT / "scripts" / "evidence-semantic-validator.py",
]
REQUIRED_SELFCHECK_FILES = [
    SELF_ROOT / "features" / f"{FEATURE}.yaml",
    SELF_ROOT / "verifiers" / "ecommerce-backend-quality-static.yaml",
    SELF_ROOT / "verifiers" / "ecommerce-backend-quality-api.yaml",
    SELF_ROOT / "verifiers" / "ecommerce-backend-quality-evidence.yaml",
    SELF_ROOT / "events" / "changed-ecommerce-backend-business-quality-closure.yaml",
]
REQUIRED_BUSINESS_JOURNEYS = {"auth-session-access", "product-asset-prompt", "wallet-commercial-billing"}
PROD_NOT_RUN_STATUSES = {"NOT_RUN", "BLOCKED", "REFUSED", "PENDING_APPROVAL"}


def norm(value: Any) -> str:
    return str(value or "UNKNOWN").strip().upper()


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
    report_path = REPORT_DIR / f"{kind}.json"
    report_path.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"feature": FEATURE, "kind": kind, "status": status, "report": str(report_path)}, ensure_ascii=False))
    raise SystemExit(exit_code)


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "FAIL", "path": str(path), "error_type": type(exc).__name__, "error": str(exc)}
    if not isinstance(data, dict):
        return {"status": "FAIL", "path": str(path), "error": "json_root_not_object"}
    data.setdefault("path", str(path))
    return data


def run_command(cmd: list[str], cwd: Path, timeout: int = 420) -> dict[str, Any]:
    env = os.environ.copy()
    # SelfCheck must never inherit or require prod approval; these local execute
    # commands use isolated httptest/temp sqlite fixture only.
    env.pop("ECOM_PROD_SMOKE_APPROVED", None)
    env.pop("PROD_SMOKE_APPROVED", None)
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout, env=env)
        return {
            "command": " ".join(cmd),
            "cwd": str(cwd),
            "exit_code": proc.returncode,
            "elapsed_ms": int((time.time() - started) * 1000),
            "stdout_tail": proc.stdout[-3000:],
            "stderr_tail": proc.stderr[-3000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(cmd),
            "cwd": str(cwd),
            "exit_code": 124,
            "elapsed_ms": int((time.time() - started) * 1000),
            "stdout_tail": (exc.stdout or "")[-3000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-3000:] if isinstance(exc.stderr, str) else "",
        }


def cleanup_status(report: dict[str, Any]) -> str:
    if report.get("cleanup_status") is not None:
        return norm(report.get("cleanup_status"))
    cleanup = report.get("cleanup")
    if isinstance(cleanup, dict):
        return norm(cleanup.get("status"))
    return "NOT_RUN"


def journey_pass_ids(report: dict[str, Any]) -> set[str]:
    journeys = report.get("journeys") or []
    if not isinstance(journeys, list):
        return set()
    return {str(j.get("id")) for j in journeys if isinstance(j, dict) and norm(j.get("status")) == "PASS"}


def prod_note(report: dict[str, Any], source: str) -> list[dict[str, str]]:
    prod_status = norm(report.get("prod_live_smoke"))
    if prod_status in PROD_NOT_RUN_STATUSES:
        return [{"source": source, "reason": "prod_not_run", "detail": f"prod_live_smoke={prod_status}; SelfCheck does not run prod by policy"}]
    return []


def local_execute_common_failures(report: dict[str, Any], source: str) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if norm(report.get("status")) != "PASS":
        failures.append({"source": source, "reason": "status_not_pass", "status": report.get("status")})
    if report.get("mode") != "local_harness_execute" or report.get("env") != "local":
        failures.append({"source": source, "reason": "local_harness_execute_required", "mode": report.get("mode"), "env": report.get("env")})
    if cleanup_status(report) != "PASS":
        failures.append({"source": source, "reason": "cleanup_not_pass", "cleanup_status": cleanup_status(report)})
    if norm(report.get("prod_live_smoke")) not in PROD_NOT_RUN_STATUSES:
        failures.append({"source": source, "reason": "prod_not_run_not_explicit", "prod_live_smoke": report.get("prod_live_smoke")})
    return failures


def check_static() -> None:
    missing = [str(p) for p in REQUIRED_BACKEND_SCRIPTS + REQUIRED_SELFCHECK_FILES if not p.exists()]
    script_findings: dict[str, Any] = {}
    for path in REQUIRED_BACKEND_SCRIPTS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.name == "evidence-semantic-validator.py":
            script_findings[str(path)] = {
                "validates_business_latest": "business-journeys" in text and "latest.json" in text,
                "validates_api_contract_latest": "api-contract-latest.json" in text,
                "classifies_pass_with_notes": "pass_with_notes_reasons" in text and "prod_not_run" in text and "cleanup_not_run" in text,
                "requires_contract_gates": "openapi_drift" in text and "frontend_consumer" in text and "platform_matrix" in text,
            }
            continue
        script_findings[str(path)] = {
            "has_prod_hard_refusal": "if args.env == \"prod\"" in text and "prod-refusal" in text and "BLOCKED" in text,
            "has_dry_run_safe_default": "--dry-run" in text and "default unless --execute" in text,
            "has_local_execute_fixture": "--execute" in text and "run_isolated_harness" in text and "--cleanup" in text,
            "writes_report_under_business_journeys": "reports" in text and "business-journeys" in text,
            "has_redaction": ("SECRET_RE" in text and "REDACTED" in text) or "critical_smoke.redact" in text,
            "marks_prod_not_run_in_execute_report": "prod_live_smoke" in text and "NOT_RUN" in text,
            "emits_cleanup_status": "cleanup_status" in text,
        }
    makefile = BACKEND_ROOT / "Makefile"
    make_text = makefile.read_text(encoding="utf-8", errors="ignore") if makefile.exists() else ""
    makefile_findings = {
        "release_gate_uses_execute_not_dry_run": "release-quality-gate" in make_text and "--execute --fixture isolated --cleanup" in make_text and "release-quality-gate: quality-gate openapi-drift-gate frontend-consumer-sweep platform-contract-gate" in make_text,
        "release_gate_runs_semantic_validator": "./scripts/evidence-semantic-validator.py" in make_text,
        "pr_layer_target_exists": "pr-quality-gate: test quality-gate" in make_text,
        "core_business_release_target_exists": "core-business-pr-gate: release-quality-gate" in make_text,
    }
    failed_checks = {
        script: [name for name, ok in checks.items() if not ok]
        for script, checks in script_findings.items()
        if any(not ok for ok in checks.values())
    }
    failed_make_checks = [name for name, ok in makefile_findings.items() if not ok]
    details = {
        "missing_files": missing,
        "script_findings": script_findings,
        "makefile_findings": makefile_findings,
        "failed_checks": failed_checks,
        "failed_make_checks": failed_make_checks,
        "prod_smoke_ran": False,
    }
    if missing or failed_checks or failed_make_checks:
        emit("static", "BLOCK", details, 2)
    emit("static", "PASS", details, 0)


def check_api() -> None:
    script = BACKEND_ROOT / "scripts" / "ecommerce-backend-api-contract-smoke.py"
    if not script.exists():
        emit("api", "BLOCK", {"missing_script": str(script)}, 2)
    result = run_command([sys.executable, str(script), "--env", "local", "--execute", "--fixture", "isolated", "--cleanup"], BACKEND_ROOT, timeout=420)
    report_path = BACKEND_ROOT / "reports" / "quality" / "business-journeys" / "api-contract-latest.json"
    report = read_json(report_path)
    failures = local_execute_common_failures(report, "api_contract")
    if norm((report.get("live_contract_evidence") or {}).get("status")) != "PASS":
        failures.append({"source": "api_contract", "reason": "live_contract_evidence_not_pass", "live_contract_status": (report.get("live_contract_evidence") or {}).get("status")})
    if result["exit_code"] != 0:
        failures.append({"source": "api_contract", "reason": "command_failed", "exit_code": result["exit_code"]})
    pass_with_notes_reasons = prod_note(report, "api_contract")
    details = {
        "local_execute": result,
        "backend_report_path": str(report_path),
        "backend_report": report,
        "prod_smoke_ran": False,
        "semantic_status": "PASS_WITH_NOTES" if pass_with_notes_reasons and not failures else ("FAIL" if failures else "PASS"),
        "pass_with_notes_reasons": pass_with_notes_reasons,
        "failures": failures,
    }
    if failures:
        emit("api", "BLOCK", details, 2)
    # Top-level SelfCheck status remains PASS so the exact requirement-gate command
    # succeeds; semantic_status captures the prod-only PASS_WITH_NOTES nuance.
    emit("api", "PASS", details, 0)


def check_evidence() -> None:
    script = BACKEND_ROOT / "scripts" / "ecommerce-backend-critical-journey-smoke.py"
    if not script.exists():
        emit("evidence", "BLOCK", {"missing_script": str(script)}, 2)
    result = run_command([sys.executable, str(script), "--env", "local", "--execute", "--fixture", "isolated", "--cleanup"], BACKEND_ROOT, timeout=420)
    report_path = BACKEND_ROOT / "reports" / "quality" / "business-journeys" / "latest.json"
    report = read_json(report_path)
    failures = local_execute_common_failures(report, "business_journey")
    passed = journey_pass_ids(report)
    if not REQUIRED_BUSINESS_JOURNEYS.issubset(passed):
        failures.append({"source": "business_journey", "reason": "required_journeys_missing", "required": sorted(REQUIRED_BUSINESS_JOURNEYS), "passed": sorted(passed & REQUIRED_BUSINESS_JOURNEYS)})
    if result["exit_code"] != 0:
        failures.append({"source": "business_journey", "reason": "command_failed", "exit_code": result["exit_code"]})
    pass_with_notes_reasons = prod_note(report, "business_journey")
    details = {
        "local_execute": result,
        "backend_report_path": str(report_path),
        "backend_report": report,
        "prod_smoke_ran": False,
        "semantic_status": "PASS_WITH_NOTES" if pass_with_notes_reasons and not failures else ("FAIL" if failures else "PASS"),
        "pass_with_notes_reasons": pass_with_notes_reasons,
        "required_journeys_passed": sorted(passed & REQUIRED_BUSINESS_JOURNEYS),
        "failures": failures,
    }
    if failures:
        emit("evidence", "BLOCK", details, 2)
    emit("evidence", "PASS", details, 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="SelfCheck verifier for Ecommerce backend business quality closure.")
    parser.add_argument("--kind", choices=["static", "api", "evidence"], required=True)
    args = parser.parse_args()
    {"static": check_static, "api": check_api, "evidence": check_evidence}[args.kind]()


if __name__ == "__main__":
    main()
