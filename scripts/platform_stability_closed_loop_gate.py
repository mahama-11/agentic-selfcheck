#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

FEATURE = "platform-stability-closed-loop-gates"
VERIFIER = "platform-stability-closed-loop-static"
SELFCHECK_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(os.environ.get("V_WORKSPACE_ROOT", "/root/work/v"))
PLATFORM_BACKEND = PROJECT_ROOT / "platform-backend"
REPORT = PROJECT_ROOT / "reports" / FEATURE / f"{VERIFIER}.json"

# These are the stability domains the user explicitly asked to make blocking for the shared platform.
REQUIRED_DOMAINS = {
    "auth_org_rbac": ["auth", "identity", "organization", "access"],
    "wallet_quota_grant_metering": ["wallet", "metering", "control", "commercial", "catalog", "incentive"],
    "runtime_provider_callback_result": ["runtime"],
    "storage_registry_asset_binding": ["assetstorage"],
    "audit_observability": ["audit", "diagnostics", "observability", "telemetry"],
    "downstream_consumers": ["ecommerce", "menu", "kyc"],
}

COMMANDS: list[dict[str, Any]] = [
    {
        "id": "platform_core_contract_static",
        "cwd": str(SELFCHECK_ROOT),
        "argv": [
            "python3",
            "scripts/platform_core_engineering_baseline.py",
            "--target-root",
            str(PROJECT_ROOT),
            "--report",
            str(PROJECT_ROOT / "reports" / FEATURE / "platform-core-engineering-baseline.json"),
        ],
        "timeout": 180,
        "coverage": ["contract surface", "route/spec drift", "product-boundary", "idempotency/status scanners"],
    },
    {
        "id": "platform_runtime_business_closed_loop",
        "cwd": str(SELFCHECK_ROOT),
        "argv": ["python3", "scripts/platform_runtime_business_integration_safety.py"],
        "timeout": 360,
        "coverage": ["job create/dispatch", "provider accepted", "fallback/retry", "callback/result", "charge binding", "terminal no-op"],
    },
    {
        "id": "platform_financial_business_closed_loop",
        "cwd": str(SELFCHECK_ROOT),
        "argv": ["python3", "scripts/platform_financial_business_consistency.py"],
        "timeout": 360,
        "coverage": ["wallet", "quota/control", "metering", "grant-policy/commercial", "runtime charge session"],
    },
    {
        "id": "platform_storage_audit_observability_closed_loop",
        "cwd": str(PLATFORM_BACKEND),
        "argv": [
            "go",
            "test",
            "./internal/modules/assetstorage",
            "./internal/modules/audit",
            "./internal/telemetry",
            "-run",
            "^(TestUploadRegisterResolveAndDataURL|TestImportLocalAssetUpdateAndConflict|TestSeedLocalDefaultsCreatesStorageBinding|TestAuditServiceRecordAndHelpers|TestSafeErrorRedactsSensitiveText|TestInitTracingDisabledAndStartGinSpan)$",
            "-count=1",
        ],
        "timeout": 240,
        "coverage": ["storage registry import/resolve", "asset binding seed", "audit record", "secret redaction", "trace span initialization"],
    },
    {
        "id": "platform_package_activation_closed_loop",
        "cwd": str(PLATFORM_BACKEND),
        "argv": [
            "go",
            "test",
            "./internal/modules/control",
            "./internal/migration",
            "-run",
            "^(TestActivatePackageAppliesPoliciesAndIsIdempotent|TestActivatePackageFailsClosedWithoutActivePolicies|TestSeedMenuOfferings)$",
            "-count=1",
        ],
        "timeout": 240,
        "coverage": ["generic package activation", "quota/capability policy execution", "idempotent reference_id", "disabled/no-policy fail-closed", "Menu signup trial seed policy"],
    },
    {
        "id": "menu_signup_package_activation_contract",
        "cwd": str(PROJECT_ROOT / "menu-backend"),
        "argv": [
            "go",
            "test",
            "./internal/modules/auth",
            "./internal/modules/user",
            "-run",
            "^(TestRegisterActivatesConfiguredSignupPackage|TestAssignCommercialPackage_SubscriptionGrantsQuota|TestAssignCommercialPackage_PermanentPackGrantsQuota|TestSimulateCommercialConsumption_ClosesAssignmentToSettlementLoop)$",
            "-count=1",
        ],
        "timeout": 240,
        "coverage": ["Menu signup chooses configured package", "Menu package assignment calls Platform activation", "quota available before Studio consumption probe"],
    },
    {
        "id": "ecommerce_backend_consumer_compile",
        "cwd": str(PROJECT_ROOT / "ecommerce-backend"),
        "argv": ["go", "test", "./...", "-run", "^$", "-count=1"],
        "timeout": 300,
        "coverage": ["downstream Ecommerce backend consumer compile against Platform contracts"],
    },
    {
        "id": "menu_backend_consumer_compile",
        "cwd": str(PROJECT_ROOT / "menu-backend"),
        "argv": ["go", "test", "./...", "-run", "^$", "-count=1"],
        "timeout": 300,
        "coverage": ["downstream Menu backend consumer compile against Platform contracts"],
    },
    {
        "id": "kyc_backend_consumer_compile",
        "cwd": str(PROJECT_ROOT / "kyc-backend"),
        "argv": ["go", "test", "./...", "-run", "^$", "-count=1"],
        "timeout": 300,
        "coverage": ["downstream KYC backend consumer compile against Platform auth/org/storage/quota contracts"],
    },
    {
        "id": "ecommerce_frontend_typecheck",
        "cwd": str(PROJECT_ROOT / "ecommerce-frontend"),
        "argv": ["npm", "run", "typecheck"],
        "timeout": 300,
        "coverage": ["Ecommerce frontend service/client/type assumptions against Platform-adjacent contract changes"],
    },
    {
        "id": "menu_frontend_typecheck",
        "cwd": str(PROJECT_ROOT / "menu-frontend"),
        "argv": ["npm", "run", "typecheck"],
        "timeout": 300,
        "coverage": ["Menu frontend service/client/type assumptions against shared auth/platform changes"],
    },
    {
        "id": "kyc_frontend_typecheck",
        "cwd": str(PROJECT_ROOT / "kyc-frontend"),
        "argv": ["npm", "run", "typecheck"],
        "timeout": 300,
        "coverage": ["KYC frontend service/client/type assumptions against shared auth/storage/quota changes"],
    },
]

REQUIRED_SELECTOR_GATES = {
    "platform-core-engineering-baseline",
    "platform-runtime-state-machine-baseline",
    "platform-runtime-business-integration-safety",
    "platform-financial-consistency-baseline",
    "platform-financial-business-consistency",
    "platform-ops-visible-baseline",
    "ecommerce-critical-journey-release-gate",
    FEATURE,
}

REQUIRED_DOC_TERMS = [
    "runtime/provider/callback/result asset",
    "quota/metering/grant-policy",
    "storage registry/product asset",
    "Ecom/Menu/KYC",
    "fail-closed",
    "RepairTask",
    "request_id",
    "trace_id",
]


def run_command(spec: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    cwd = Path(spec["cwd"])
    if not cwd.exists():
        return {
            "id": spec["id"],
            "status": "FAIL",
            "exit_code": 127,
            "duration_seconds": 0,
            "failure_reason": f"cwd missing: {cwd}",
            "coverage": spec.get("coverage", []),
        }
    try:
        proc = subprocess.run(
            spec["argv"],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=int(spec.get("timeout", 300)),
        )
        return {
            "id": spec["id"],
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "exit_code": proc.returncode,
            "duration_seconds": round(time.time() - started, 3),
            "cwd": str(cwd),
            "command_argv": spec["argv"],
            "coverage": spec.get("coverage", []),
            "stdout_tail": proc.stdout[-8000:],
            "stderr_tail": proc.stderr[-8000:],
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return {
            "id": spec["id"],
            "status": "FAIL",
            "exit_code": 124,
            "duration_seconds": round(time.time() - started, 3),
            "cwd": str(cwd),
            "command_argv": spec["argv"],
            "coverage": spec.get("coverage", []),
            "failure_reason": "timeout",
            "stdout_tail": stdout[-8000:],
            "stderr_tail": stderr[-8000:],
        }


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def manifest_checks() -> dict[str, Any]:
    selector_text = read_text(SELFCHECK_ROOT / "config/v-business-gate-selector.yaml")
    doc_path = PLATFORM_BACKEND / "docs/architecture/PLATFORM_STABILITY_CLOSED_LOOP_GATES.md"
    doc_text = read_text(doc_path)
    missing_selector_gates = sorted(gate for gate in REQUIRED_SELECTOR_GATES if gate not in selector_text)
    missing_doc_terms = sorted(term for term in REQUIRED_DOC_TERMS if term not in doc_text)
    feature_files = [
        SELFCHECK_ROOT / "features/platform-stability-closed-loop-gates.yaml",
        SELFCHECK_ROOT / "verifiers/platform-stability-closed-loop-static.yaml",
        SELFCHECK_ROOT / "events/changed-v-platform-stability-closed-loop.yaml",
        SELFCHECK_ROOT / "requirement-traces/platform-stability-closed-loop-gates.yaml",
        doc_path,
    ]
    missing_files = [str(path) for path in feature_files if not path.exists()]
    return {
        "status": "PASS" if not missing_files and not missing_selector_gates and not missing_doc_terms else "FAIL",
        "missing_files": missing_files,
        "missing_selector_gates": missing_selector_gates,
        "missing_doc_terms": missing_doc_terms,
        "required_domains": REQUIRED_DOMAINS,
    }


def main() -> int:
    started = time.time()
    results = []
    for spec in COMMANDS:
        results.append(run_command(spec))
    manifest = manifest_checks()
    failed = [item for item in results if item.get("status") != "PASS"]
    status = "PASS" if not failed and manifest["status"] == "PASS" else "FAIL"
    payload = {
        "feature": FEATURE,
        "verifier": VERIFIER,
        "status": status,
        "duration_seconds": round(time.time() - started, 3),
        "coverage_statement": "Platform stability closed-loop gate: core contracts + runtime/provider/callback/result + financial/quota/metering + package activation/signup quota + storage/audit/observability focused tests + Ecom/Menu/KYC backend compile and frontend typecheck consumer sweeps.",
        "manifest_checks": manifest,
        "commands": results,
        "failed_command_ids": [item["id"] for item in failed],
        "evidence_policy": "FAIL means not complete; do not report Platform stability closure until every command and manifest check passes in the same run.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "failed_command_ids": payload["failed_command_ids"], "report": str(REPORT)}, ensure_ascii=False, indent=2))
    print(f"SELF_CHECK_EVIDENCE: {REPORT}")
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
