#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

FEATURE = "platform-financial-business-consistency"
VERIFIER = "platform-financial-business-consistency-static"
PROJECT_ROOT = Path("/root/work/v")
BACKEND_ROOT = PROJECT_ROOT / "platform-backend"
REPORT = PROJECT_ROOT / "reports" / FEATURE / f"{VERIFIER}.json"
PACKAGES = [
    "./internal/modules/wallet",
    "./internal/modules/metering",
    "./internal/modules/control",
    "./internal/modules/runtime",
    "./internal/modules/commercial",
    "./internal/modules/catalog",
    "./internal/modules/incentive",
    "./internal/migration",
]
EXPECTED_TESTS_BY_PACKAGE = {
    "./internal/modules/wallet": [
        "TestExpireWalletBuckets_ExpiresExpiredRewardBucket",
        "TestGetWalletSummary_DoesNotExposeExpiredBalanceAsAvailable",
        "TestDebitAccountTx_BucketPriorityFIFO",
        "TestPostLedger_DebitIdempotencyWithReference",
        "TestPostLedger_ConcurrentDebitDoesNotOverdrawSharedSQLite",
    ],
    "./internal/modules/metering": [
        "TestIngestEvent_UsageBillingUsesWalletThenBilling",
        "TestIngestEvent_IncludedThenOverageConsumesQuotaBeforeBilling",
        "TestIngestEvent_DoesNotConsumeExpiredWalletBucket",
        "TestIngestEvent_ConcurrentIncludedThenOverageDoesNotOverconsumeQuotaSharedSQLite",
        "TestFinalize_UsesReservationAndIsIdempotent",
    ],
    "./internal/modules/control": [
        "TestControlServiceReserveCommitReleaseAndIdempotency",
        "TestCommitReservationCreditsPath",
    ],
    "./internal/modules/runtime": [
        "TestRuntimeTerminalChargeBindingCompletedSettlesReservedSessionIdempotently",
        "TestRuntimeTerminalChargeBindingFailedReleasesReservedSession",
        "TestRuntimeTerminalChargeBindingCanceledCancelsCreatedSession",
        "TestRuntimeTerminalChargeBindingNoChargeSessionNoop",
        "TestCreateChargeSessionReusesExistingReservationKeyForSameBoundary",
        "TestCreateChargeSessionRejectsDuplicateReservationKeyForDifferentSource",
    ],
    "./internal/modules/commercial": [
        "TestSeedEcommerceVisibleBaselineIdempotent",
    ],
    "./internal/modules/catalog": [
        "TestCatalogServiceAndHandler",
    ],
    "./internal/modules/incentive": [
        "TestRecordChannelCharge_AndRefundReverse",
        "TestRecordChannelCharge_IsIdempotentByEventAndCharge",
        "TestChannelSettlementBatch_GenerateConfirmProcessClose",
        "TestRedeemCommissions_IssuesRewardAndMarksCommissionRedeemed",
    ],
    "./internal/migration": [
        "TestSeedEcommerceOfferingsVisibleBaseline",
    ],
}
EXPECTED_TESTS = [test for package in PACKAGES for test in EXPECTED_TESTS_BY_PACKAGE[package]]
TEST_REGEX = r"^(" + "|".join(re.escape(test) for test in EXPECTED_TESTS) + r")$"
TIMEOUT_SECONDS = 300
LIST_TIMEOUT_SECONDS = 120


def write_report(payload: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def list_package_tests(package: str) -> dict:
    command = ["go", "test", package, "-list", "."]
    proc = subprocess.run(
        command,
        cwd=BACKEND_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=LIST_TIMEOUT_SECONDS,
    )
    tests = sorted(line.strip() for line in proc.stdout.splitlines() if line.startswith("Test"))
    expected = EXPECTED_TESTS_BY_PACKAGE[package]
    missing = sorted(set(expected) - set(tests))
    return {
        "package": package,
        "command_argv": command,
        "exit_code": proc.returncode,
        "expected_tests": expected,
        "present_expected_tests": sorted(set(expected) & set(tests)),
        "missing_expected_tests": missing,
        "matched_expected_count": len(set(expected) & set(tests)),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def preflight_expected_tests() -> list[dict]:
    return [list_package_tests(package) for package in PACKAGES]


def main() -> int:
    started = time.time()
    command = ["go", "test", *PACKAGES, "-run", TEST_REGEX, "-count=1"]
    list_commands = [["go", "test", package, "-list", "."] for package in PACKAGES]
    base_payload = {
        "feature": FEATURE,
        "verifier": VERIFIER,
        "cwd": str(BACKEND_ROOT),
        "command_argv": command,
        "command": " ".join(command),
        "preflight_command_argv": list_commands,
        "packages": PACKAGES,
        "expected_tests_by_package": EXPECTED_TESTS_BY_PACKAGE,
        "expected_tests": EXPECTED_TESTS,
        "expected_test_count": len(EXPECTED_TESTS),
        "targeted_regex": TEST_REGEX,
        "timeout_seconds": TIMEOUT_SECONDS,
        "list_timeout_seconds": LIST_TIMEOUT_SECONDS,
        "coverage_intent": [
            "wallet ledger debit idempotency and expired-bucket exclusion",
            "wallet concurrent debit no-overdraw regression with SQLite shared-cache limitation documented in test",
            "metering wallet/quota/billing settlement and finalize idempotency",
            "metering quota aggregate-row no-overconsume regression with SQLite shared-cache limitation documented in test",
            "control reserve/commit/release and idempotency",
            "runtime charge-session idempotency and terminal binding",
            "commercial/catalog visible baseline seeding and catalog handler smoke",
            "incentive channel settlement/idempotency and commission redemption",
        ],
        "production_like_concurrency_note": (
            "Default verifier evidence uses deterministic SQLite/shared-cache regressions and is not, by itself, proof of production database locking behavior. "
            "For 80% production-like financial/concurrency claims, rerun the same impacted Go package tests against a local-prod/Postgres DSN via PLATFORM_TEST_DATABASE_DSN when that harness is available and cite that evidence separately."
        ),
    }
    try:
        preflight = preflight_expected_tests()
        preflight_failures = [
            item
            for item in preflight
            if item["exit_code"] != 0 or item["missing_expected_tests"]
        ]
        if preflight_failures:
            duration = round(time.time() - started, 3)
            payload = {
                **base_payload,
                "status": "FAIL",
                "exit_code": 2,
                "duration_seconds": duration,
                "failure_reason": "expected targeted Go tests missing or package test listing failed",
                "preflight": preflight,
            }
            write_report(payload)
            print(json.dumps({"failure_reason": payload["failure_reason"], "preflight_failures": preflight_failures}, ensure_ascii=False, indent=2))
            print(f"SELF_CHECK_EVIDENCE: {REPORT}")
            return 2
        proc = subprocess.run(
            command,
            cwd=BACKEND_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=TIMEOUT_SECONDS,
        )
        duration = round(time.time() - started, 3)
        payload = {
            **base_payload,
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "exit_code": proc.returncode,
            "duration_seconds": duration,
            "preflight": preflight,
            "stdout_tail": proc.stdout[-8000:],
            "stderr_tail": proc.stderr[-8000:],
        }
        write_report(payload)
        print(proc.stdout, end="")
        print(proc.stderr, end="")
        print(f"SELF_CHECK_EVIDENCE: {REPORT}")
        return proc.returncode
    except subprocess.TimeoutExpired as exc:
        duration = round(time.time() - started, 3)
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        payload = {
            **base_payload,
            "status": "FAIL",
            "exit_code": 124,
            "duration_seconds": duration,
            "failure_reason": "go test timeout",
            "stdout_tail": stdout[-8000:],
            "stderr_tail": stderr[-8000:],
        }
        write_report(payload)
        print(stdout, end="")
        print(stderr, end="")
        print(f"SELF_CHECK_EVIDENCE: {REPORT}")
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
