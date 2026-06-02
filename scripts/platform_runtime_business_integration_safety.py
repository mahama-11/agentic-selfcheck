#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

FEATURE = "platform-runtime-business-integration-safety"
VERIFIER = "platform-runtime-business-integration-safety-static"
PROJECT_ROOT = Path("/root/work/v")
BACKEND_ROOT = PROJECT_ROOT / "platform-backend"
REPORT = PROJECT_ROOT / "reports" / FEATURE / f"{VERIFIER}.json"
PACKAGE = "./internal/modules/runtime"
PACKAGES = [PACKAGE]
EXPECTED_TESTS_BY_PACKAGE = {
    PACKAGE: [
        "TestDispatchRuntimeJobAcceptsAsyncSubmissionAndEnqueuesPoll",
        "TestHandleDispatchErrorSchedulesFallback",
        "TestApplyRuntimeJobTransitionRetryAndFallbackAllowProcessingToQueued",
        "TestRuntimeTerminalChargeBindingCompletedSettlesReservedSessionIdempotently",
        "TestRuntimeTerminalChargeBindingFailedReleasesReservedSession",
        "TestRuntimeTerminalChargeBindingCanceledCancelsCreatedSession",
        "TestRuntimeTerminalChargeBindingNoChargeSessionNoop",
        "TestTransitionRuntimeJobStaleProviderEventsDoNotOverwriteTerminalDBRow",
        "TestHandleProviderCallbackPayloadProgressDoesNotDowngradeCompletedJob",
        "TestApplyRuntimeJobTransitionCompletedProviderProgressNoops",
        "TestApplyRuntimeJobTransitionTerminalProviderAcceptedNoops",
        "TestApplyRuntimeJobTransitionFailedAdminQueuedErrors",
        "TestUpdateRuntimeJobRejectsFailedToQueued",
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


def timeout_payload(exc: subprocess.TimeoutExpired, base_payload: dict, started: float, failure_reason: str) -> dict:
    stdout = exc.stdout or ""
    stderr = exc.stderr or ""
    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    return {
        **base_payload,
        "status": "FAIL",
        "exit_code": 124,
        "duration_seconds": round(time.time() - started, 3),
        "failure_reason": failure_reason,
        "stdout_tail": stdout[-8000:],
        "stderr_tail": stderr[-8000:],
    }


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
            "dispatch/provider accepted",
            "fallback/retry",
            "completion/charge binding",
            "stale terminal progress/callback/no-op",
            "failed-to-queued rejection",
        ],
    }
    try:
        preflight = preflight_expected_tests()
        preflight_failures = [
            item
            for item in preflight
            if item["exit_code"] != 0 or item["missing_expected_tests"]
        ]
        if preflight_failures:
            payload = {
                **base_payload,
                "status": "FAIL",
                "exit_code": 2,
                "duration_seconds": round(time.time() - started, 3),
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
        payload = {
            **base_payload,
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "exit_code": proc.returncode,
            "duration_seconds": round(time.time() - started, 3),
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
        payload = timeout_payload(exc, base_payload, started, "go test preflight or execution timeout")
        write_report(payload)
        print(payload.get("stdout_tail", ""), end="")
        print(payload.get("stderr_tail", ""), end="")
        print(f"SELF_CHECK_EVIDENCE: {REPORT}")
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
