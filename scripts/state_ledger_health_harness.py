#!/usr/bin/env python3
"""SelfCheck harness for Feishu AI state ledger + ambient control-plane UX.

This verifier intentionally checks the user's real requirement: normal chat should
not force session IDs or explicit control commands. SESSION/CRON/DELEGATE records
are internal evidence; user-facing recovery should resolve natural descriptions to
human-readable TASK/LEDGER main records.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

LEDGER = "/root/.hermes/scripts/state_ledger.py"
HERMES = "/usr/local/lib/hermes-agent/venv/bin/hermes"
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


def parse_session_id(text: str) -> str:
    m = re.search(r"session_id:\s*(\S+)", text or "")
    return m.group(1) if m else ""


reports = []
exit_code = 0
failures: list[str] = []

# Baseline structural checks.
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
        if not runtime_patch.get("already_applied"):
            failures.append("ledger-aware Hermes runtime patch is not applied; run ledger_patch_manager.py apply after Hermes update")
        stale_copies = [x.get("target") for x in rep["stdout"].get("copy_files", []) if not x.get("matches_manifest")]
        if stale_copies:
            failures.append(f"ledger-aware managed files drifted from manifest: {stale_copies}")

# Ambient UX check 1: a normal greeting should not create a SESSION ledger card.
small = run([HERMES, "chat", "-q", "你好", "-t", "file", "--source", "ambient-selfcheck-smalltalk", "--quiet"], timeout=240)
reports.append(small)
small_sid = parse_session_id(str(small["stdout"]))
if small_sid:
    get_small = run([LEDGER, "get", "--task-id", f"SESSION-{small_sid}"], timeout=120)
    reports.append(get_small)
    if get_small["exit_code"] == 0:
        failures.append(f"smalltalk polluted ledger with SESSION-{small_sid}")
# Some Hermes quiet modes may omit session_id; that is acceptable for this UX check.

# Ambient UX check 2: a tasky continuation should resolve to a human-readable main task,
# not require the user to remember the fresh session id.
task_prompt = "继续状态账本无感控制面这个事，只输出 AMBIENT_SELFCHECK_OK"
task = run([HERMES, "chat", "-q", task_prompt, "-t", "file", "--source", "ambient-selfcheck-task", "--quiet"], timeout=300)
reports.append(task)
if "AMBIENT_SELFCHECK_OK" not in str(task["stdout"]):
    failures.append("ambient task smoke did not complete expected response")
resolve = run([LEDGER, "resolve", "状态账本无感控制面", "--top", "1"], timeout=120)
reports.append(resolve)
if resolve["exit_code"] != 0 or not isinstance(resolve["stdout"], dict):
    failures.append("natural resolve failed")
else:
    best = (resolve["stdout"].get("best") or {})
    task_id = str(best.get("任务ID") or "")
    title = str(best.get("任务标题") or "")
    if task_id.startswith("SESSION-") or title.startswith("Session("):
        failures.append(f"natural resolve regressed to technical session record: {task_id} {title}")
    if not (task_id.startswith("TASK-") or task_id.startswith("LEDGER-")):
        failures.append(f"natural resolve did not select a main TASK/LEDGER record: {task_id}")

# Ambient summary must be human-readable. It may mention historical Session records,
# but must include at least one non-technical collaboration mainline.
summary = run([LEDGER, "ambient-summary", "--top", "5"], timeout=120)
reports.append(summary)
if "无感" not in str(summary["stdout"]) and "控制面" not in str(summary["stdout"]):
    failures.append("ambient summary lacks the current human-readable mainline")

ok = not failures and all(r["exit_code"] == 0 or (r["command"][1:3] == ["get", "--task-id"]) for r in reports)
print(json.dumps({"ok": ok, "failures": failures, "checks": reports}, ensure_ascii=False, indent=2))
raise SystemExit(0 if ok else (exit_code or 1))
