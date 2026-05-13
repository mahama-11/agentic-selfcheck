#!/usr/bin/env python3
"""Cheap structural SelfCheck for Feishu AI state ledger.

This is safe to run from the 30m watchdog: it does not spawn Hermes CLI turns.
It verifies the Base schema/control-plane invariants and the local overlay state.
"""
from __future__ import annotations

import json
import subprocess

LEDGER = "/root/.hermes/scripts/state_ledger.py"
PATCH_MANAGER = "/root/.hermes/state-ledger/patches/ledger_patch_manager.py"


def run(cmd: list[str], timeout: int = 180) -> dict:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    try:
        parsed = json.loads(stdout) if stdout.startswith("{") or stdout.startswith("[") else stdout
    except json.JSONDecodeError:
        parsed = stdout
    return {"command": cmd, "exit_code": proc.returncode, "stdout": parsed, "stderr": stderr}

reports = []
failures: list[str] = []
exit_code = 0

for cmd in [
    [LEDGER, "health", "--heartbeat-sla-minutes", "60"],
    [LEDGER, "control-smoke"],
    [PATCH_MANAGER, "status", "--json"],
]:
    rep = run(cmd, timeout=180)
    reports.append(rep)
    if rep["exit_code"] != 0:
        failures.append(f"command failed: {' '.join(cmd)}")
        exit_code = rep["exit_code"] or 1
    if cmd[0] == PATCH_MANAGER and isinstance(rep["stdout"], dict):
        runtime_patch = rep["stdout"].get("runtime_patch") or {}
        # Local overlay files are the contract now; runtime patch status is advisory because
        # site-local hardening may intentionally add small deltas after the base patch.
        stale_copies = [x.get("target") for x in rep["stdout"].get("copy_files", []) if not x.get("matches_manifest")]
        if stale_copies:
            failures.append(f"ledger-aware managed files drifted from manifest: {stale_copies}")
        if not runtime_patch.get("already_applied") and not runtime_patch.get("can_apply_cleanly"):
            failures.append("ledger-aware runtime patch is neither applied nor cleanly applicable; manual rebase required")

ok = not failures
print(json.dumps({"ok": ok, "failures": failures, "checks": reports}, ensure_ascii=False, indent=2))
raise SystemExit(0 if ok else (exit_code or 1))
