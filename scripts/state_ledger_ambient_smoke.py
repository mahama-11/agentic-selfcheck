#!/usr/bin/env python3
"""Low-frequency/manual ambient UX SelfCheck for the AI state ledger.

This intentionally spawns Hermes CLI turns, so do not run it from the high-frequency watchdog.
It verifies human-facing UX: normal chat does not create ledger noise and natural continuation
resolves to a human-readable TASK/LEDGER mainline instead of raw SESSION IDs.
"""
from __future__ import annotations

import json
import re
import subprocess

LEDGER = "/root/.hermes/scripts/state_ledger.py"
HERMES = "/usr/local/lib/hermes-agent/venv/bin/hermes"


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
failures: list[str] = []

small = run([HERMES, "chat", "-q", "你好", "-t", "file", "--source", "ambient-selfcheck-smalltalk", "--quiet"], timeout=240)
reports.append(small)
small_sid = parse_session_id(str(small["stdout"]))
if small_sid:
    get_small = run([LEDGER, "get", "--task-id", f"SESSION-{small_sid}"], timeout=120)
    reports.append(get_small)
    if get_small["exit_code"] == 0:
        failures.append(f"smalltalk polluted ledger with SESSION-{small_sid}")

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
summary = run([LEDGER, "ambient-summary", "--top", "5"], timeout=120)
reports.append(summary)
if "无感" not in str(summary["stdout"]) and "控制面" not in str(summary["stdout"]):
    failures.append("ambient summary lacks the current human-readable mainline")

ok = not failures and all(r["exit_code"] == 0 or (r["command"][1:3] == ["get", "--task-id"]) for r in reports)
print(json.dumps({"ok": ok, "failures": failures, "checks": reports}, ensure_ascii=False, indent=2))
raise SystemExit(0 if ok else 1)
