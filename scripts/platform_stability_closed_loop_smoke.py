#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    ROOT / "scripts/platform_stability_closed_loop_gate.py",
    ROOT / "features/platform-stability-closed-loop-gates.yaml",
    ROOT / "verifiers/platform-stability-closed-loop-static.yaml",
    ROOT / "events/changed-v-platform-stability-closed-loop.yaml",
    ROOT / "requirement-traces/platform-stability-closed-loop-gates.yaml",
    Path("/root/work/v/platform-backend/docs/architecture/PLATFORM_STABILITY_CLOSED_LOOP_GATES.md"),
]
REQUIRED_SELECTOR_TEXT = [
    "platform-stability-closed-loop-gates",
    "platform-backend/internal/modules/runtime/**",
    "platform-backend/internal/modules/wallet/**",
    "platform-backend/internal/modules/storage/**",
    "platform-backend/internal/migration/menu_offerings_seed.go",
    "menu-backend/internal/modules/auth/**",
    "menu-backend/internal/modules/user/**",
    "ecommerce-critical-journey-release-gate",
]
REQUIRED_GATE_SCRIPT_TEXT = [
    "platform_storage_audit_observability_closed_loop",
    "platform_package_activation_closed_loop",
    "menu_signup_package_activation_contract",
    "TestActivatePackageAppliesPoliciesAndIsIdempotent",
    "TestRegisterActivatesConfiguredSignupPackage",
    "TestSeedMenuOfferings",
    "TestUploadRegisterResolveAndDataURL",
    "TestAuditServiceRecordAndHelpers",
    "TestSafeErrorRedactsSensitiveText",
    "ecommerce_frontend_typecheck",
    "menu_frontend_typecheck",
    "kyc_frontend_typecheck",
]


def main() -> int:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    selector = ROOT / "config/v-business-gate-selector.yaml"
    selector_text = selector.read_text(encoding="utf-8") if selector.exists() else ""
    gate_script = ROOT / "scripts/platform_stability_closed_loop_gate.py"
    gate_script_text = gate_script.read_text(encoding="utf-8") if gate_script.exists() else ""
    missing_selector_terms = [term for term in REQUIRED_SELECTOR_TEXT if term not in selector_text]
    missing_gate_script_terms = [term for term in REQUIRED_GATE_SCRIPT_TEXT if term not in gate_script_text]
    payload = {
        "status": "PASS" if not missing and not missing_selector_terms and not missing_gate_script_terms else "FAIL",
        "missing_files": missing,
        "missing_selector_terms": missing_selector_terms,
        "missing_gate_script_terms": missing_gate_script_terms,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
