#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

FEATURE = "platform-runtime-business-integration-safety"
VERIFIER = "platform-runtime-business-integration-safety-static"
PROJECT_ROOT = Path("/root/work/v")
BACKEND_ROOT = PROJECT_ROOT / "platform-backend"
REPORT = PROJECT_ROOT / "reports" / FEATURE / f"{VERIFIER}.json"
TEST_REGEX = r"Test(DispatchRuntimeJobAcceptsAsyncSubmissionAndEnqueuesPoll|HandleDispatchErrorSchedulesFallback|ApplyRuntimeJobTransitionRetryAndFallbackAllowProcessingToQueued|RuntimeTerminalChargeBinding(CompletedSettlesReservedSessionIdempotently|FailedReleasesReservedSession|CanceledCancelsCreatedSession|NoChargeSessionNoop)|TransitionRuntimeJobStaleProviderEventsDoNotOverwriteTerminalDBRow|HandleProviderCallbackPayloadProgressDoesNotDowngradeCompletedJob|ApplyRuntimeJobTransition(CompletedProviderProgressNoops|TerminalProviderAcceptedNoops|FailedAdminQueuedErrors)|UpdateRuntimeJobRejectsFailedToQueued)$"


def main() -> int:
    started = time.time()
    command = ["go", "test", "./internal/modules/runtime", "-run", TEST_REGEX, "-count=1"]
    proc = subprocess.run(command, cwd=BACKEND_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "feature": FEATURE,
        "verifier": VERIFIER,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "exit_code": proc.returncode,
        "duration_seconds": round(time.time() - started, 3),
        "cwd": str(BACKEND_ROOT),
        "command": " ".join(command),
        "targeted_regex": TEST_REGEX,
        "coverage_intent": [
            "dispatch/provider accepted",
            "fallback/retry",
            "completion/charge binding",
            "stale terminal progress/callback/no-op",
            "failed-to-queued rejection",
        ],
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(proc.stdout, end="")
    print(proc.stderr, end="")
    print(f"SELF_CHECK_EVIDENCE: {REPORT}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
