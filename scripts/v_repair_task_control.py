#!/usr/bin/env python3
"""AI-native RepairTask lifecycle controller for the V workspace.

This script is the operational layer above v_maintenance_control_plane.py.
It does not trust scan reports as completion. It maintains a durable task ledger,
creates bounded dispatch prompts for agent lanes, leases tasks for execution, and
records parent-side verifier results before any closure.
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SELF_ROOT = Path("/root/work/agentic-selfcheck")
DEFAULT_V_ROOT = Path("/root/work/v")
REPORT_REL = Path("reports/maintenance-control-plane")
SOURCE_TASKS = REPORT_REL / "repair-tasks.json"
TASK_LEDGER = REPORT_REL / "repair-task-ledger.json"
TASK_STATUS_MD = REPORT_REL / "repair-task-status.md"
EVENTS_JSONL = REPORT_REL / "repair-task-events.jsonl"
DISPATCH_DIR = Path(".hermes/dispatch/v-maintenance-tasks")

TERMINAL_STATUSES = {"verified_resolved", "accepted_false_positive", "accepted_risk", "needs_human"}
ACTIVE_STATUSES = {"ready", "leased", "dispatched", "in_progress", "verifying", "verification_failed", "pending_verification"}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def event(v_root: Path, kind: str, task_id: str | None, **fields: Any) -> None:
    payload = {"ts": now_iso(), "event": kind, "task_id": task_id}
    payload.update(fields)
    append_event(v_root / EVENTS_JSONL, payload)


def source_path(v_root: Path) -> Path:
    return v_root / SOURCE_TASKS


def ledger_path(v_root: Path) -> Path:
    return v_root / TASK_LEDGER


def project_short(project_path: str | None) -> str:
    if not project_path:
        return "unknown"
    return Path(project_path).name


def task_prompt(task: dict[str, Any]) -> str:
    verifiers = "\n".join(f"- {v.get('name')}: `{v.get('command')}`" for v in task.get("expected_verifiers") or [])
    permissions = json.dumps(task.get("permissions") or {}, ensure_ascii=False, indent=2)
    return f"""# RepairTask {task['task_id']}

Status: {task.get('status')}
Lane: {task.get('lane')}
Project: {task.get('project_id')}
Project path: `{task.get('project_path')}`
Finding: `{task.get('finding_id')}`
Finding type: `{task.get('finding_type')}`
Severity: `{task.get('severity')}`
Path: `{task.get('path')}`
Decision: `{task.get('decision')}`
Sandbox required: `{task.get('sandbox_required')}`
Worktree policy: `{task.get('worktree_policy')}`

## Mission

Validate whether the finding is real. If real and safe, prepare or implement the smallest production-shaped repair within this task's boundaries. If it is false positive or accepted architecture, return evidence and proposed status. Do not mark the task closed yourself; parent control plane must rerun verifiers.

## Permissions

```json
{permissions}
```

Hard rules:
- Do not delete source/docs.
- Do not change contracts, schemas, product commitments, secrets, or production data.
- Code/contract-affecting edits require isolated branch/worktree.
- Subagent self-report is evidence only, not closure.
- If repair is too broad, return `needs_human` or `accepted_risk` with concrete reason.

## Expected verifiers

{verifiers or '- selfcheck validate'}

## Acceptance contract

""" + "\n".join(f"- {x}" for x in task.get("acceptance_contract") or []) + f"""

## Evidence paths

- `/root/work/v/reports/maintenance-control-plane/repair-task-ledger.json`
- `/root/work/v/reports/maintenance-control-plane/repair-task-events.jsonl`
- `/root/work/v/reports/maintenance-control-plane/repair-task-status.md`
"""


def merge_source_into_ledger(v_root: Path) -> dict[str, Any]:
    ts = now_iso()
    source = load_json(source_path(v_root), {"tasks": []})
    existing = load_json(ledger_path(v_root), {"version": 1, "tasks": []})
    old_by_id = {t.get("task_id"): t for t in existing.get("tasks", []) if t.get("task_id")}
    merged: list[dict[str, Any]] = []
    new_count = 0
    refreshed_count = 0
    for src in source.get("tasks") or []:
        tid = src.get("task_id")
        if not tid:
            continue
        old = old_by_id.get(tid)
        task = dict(src)
        if old:
            # Preserve lifecycle fields while refreshing static routing/verifier fields.
            old_status = old.get("status")
            for key in ["status", "lease", "attempts", "dispatch", "verification", "resolution", "events", "first_synced_at"]:
                if key in old:
                    task[key] = old[key]
            task.setdefault("first_synced_at", old.get("first_synced_at") or ts)
            task["last_synced_at"] = ts
            if old_status == "verified_resolved":
                # The latest scan source contains this task again, so a previously verified
                # closure has regressed/reopened. Never keep it terminal in that case.
                task["status"] = "ready"
                task.setdefault("events", []).append({"ts": ts, "event": "reopened_from_verified_resolved"})
                task.pop("resolution", None)
                event(v_root, "task_reopened", tid, previous_status=old_status, lane=task.get("lane"), project_id=task.get("project_id"))
            refreshed_count += 1
        else:
            task["status"] = "ready"
            task["first_synced_at"] = ts
            task["last_synced_at"] = ts
            task["attempts"] = []
            task["events"] = [{"ts": ts, "event": "created_from_repair_tasks"}]
            new_count += 1
            event(v_root, "task_created", tid, lane=task.get("lane"), project_id=task.get("project_id"))
        merged.append(task)

    source_ids = {t.get("task_id") for t in source.get("tasks") or []}
    for tid, old in old_by_id.items():
        if tid not in source_ids:
            stale = dict(old)
            if stale.get("status") not in TERMINAL_STATUSES:
                stale["status"] = "pending_verification"
                stale["last_synced_at"] = ts
                stale.setdefault("events", []).append({"ts": ts, "event": "pending_verification_missing_from_latest_scan"})
                event(v_root, "task_pending_verification", tid)
            merged.append(stale)

    ledger = {
        "version": 1,
        "generated_at": ts,
        "source": str(source_path(v_root)),
        "policy_version": "ai_native_repair_task_lifecycle_v1",
        "contract": "Durable RepairTask lifecycle ledger. Only parent-side verifier evidence may close tasks.",
        "summary": summarize_tasks(merged),
        "sync": {"new": new_count, "refreshed": refreshed_count, "source_total": len(source.get("tasks") or [])},
        "tasks": sorted(merged, key=lambda t: (t.get("status") in TERMINAL_STATUSES, t.get("lane", ""), t.get("project_id", ""), t.get("task_id", ""))),
    }
    write_json(ledger_path(v_root), ledger)
    render_status(v_root, ledger)
    return ledger


def summarize_tasks(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_lane: dict[str, int] = {}
    by_project: dict[str, int] = {}
    for t in tasks:
        by_status[str(t.get("status") or "unknown")] = by_status.get(str(t.get("status") or "unknown"), 0) + 1
        by_lane[str(t.get("lane") or "unknown")] = by_lane.get(str(t.get("lane") or "unknown"), 0) + 1
        by_project[str(t.get("project_id") or "unknown")] = by_project.get(str(t.get("project_id") or "unknown"), 0) + 1
    active = sum(c for s, c in by_status.items() if s in ACTIVE_STATUSES)
    terminal = sum(c for s, c in by_status.items() if s in TERMINAL_STATUSES)
    return {
        "total": len(tasks),
        "active": active,
        "terminal": terminal,
        "by_status": dict(sorted(by_status.items())),
        "by_lane": dict(sorted(by_lane.items())),
        "by_project": dict(sorted(by_project.items(), key=lambda kv: kv[1], reverse=True)),
    }


def render_status(v_root: Path, ledger: dict[str, Any]) -> None:
    summary = ledger.get("summary") or {}
    lines = [
        "# V Maintenance RepairTask Lifecycle Status",
        "",
        f"- Generated: `{ledger.get('generated_at')}`",
        f"- Policy: `{ledger.get('policy_version')}`",
        f"- Total: {summary.get('total', 0)}",
        f"- Active: {summary.get('active', 0)}",
        f"- Terminal: {summary.get('terminal', 0)}",
        "",
        "## By Status",
        "",
    ]
    for status, count in (summary.get("by_status") or {}).items():
        lines.append(f"- `{status}`: {count}")
    lines += ["", "## By Lane", ""]
    for lane, count in (summary.get("by_lane") or {}).items():
        lines.append(f"- `{lane}`: {count}")
    lines += ["", "## Next Ready Tasks", ""]
    ready = [t for t in ledger.get("tasks", []) if t.get("status") in {"ready", "verification_failed", "pending_verification"}]
    if not ready:
        lines.append("- none")
    for t in ready[:30]:
        lines.append(f"- `{t.get('task_id')}` `{t.get('lane')}` `{t.get('project_id')}` `{t.get('path')}` status `{t.get('status')}`")
    (v_root / TASK_STATUS_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def select_tasks(tasks: list[dict[str, Any]], limit: int, lane: str | None = None, project: str | None = None) -> list[dict[str, Any]]:
    candidates = [t for t in tasks if t.get("status") in {"ready", "verification_failed", "pending_verification"}]
    if lane:
        candidates = [t for t in candidates if t.get("lane") == lane]
    if project:
        candidates = [t for t in candidates if t.get("project_id") == project]
    # Prefer docs/evidence and verification_failed first because they are safer and unblock governance evidence.
    priority = {"pending_verification": 0, "verification_failed": 1, "doc-agent": 2, "backend-agent": 3, "frontend-agent": 4}
    candidates.sort(key=lambda t: (priority.get(str(t.get("status")), 5), priority.get(str(t.get("lane")), 9), t.get("project_id", ""), t.get("task_id", "")))
    return candidates[:limit]


def plan(v_root: Path, self_root: Path, limit: int, lane: str | None, project: str | None) -> dict[str, Any]:
    ledger = merge_source_into_ledger(v_root)
    selected = select_tasks(ledger.get("tasks", []), limit, lane, project)
    plan_data = {
        "generated_at": now_iso(),
        "limit": limit,
        "selected": [{
            "task_id": t.get("task_id"),
            "lane": t.get("lane"),
            "project_id": t.get("project_id"),
            "project_path": t.get("project_path"),
            "path": t.get("path"),
            "status": t.get("status"),
            "sandbox_required": t.get("sandbox_required"),
            "expected_verifiers": t.get("expected_verifiers"),
        } for t in selected],
    }
    write_json(v_root / REPORT_REL / "repair-task-plan.json", plan_data)
    lines = ["# V Maintenance RepairTask Execution Plan", "", f"- Generated: `{plan_data['generated_at']}`", f"- Selected: {len(selected)}", ""]
    if not selected:
        lines.append("- none")
    for t in selected:
        lines.append(f"- `{t.get('task_id')}` `{t.get('lane')}` `{t.get('project_id')}` `{t.get('path')}` sandbox `{t.get('sandbox_required')}`")
    (v_root / REPORT_REL / "repair-task-plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return plan_data


def lease(v_root: Path, self_root: Path, limit: int, lane: str | None, project: str | None, executor: str) -> dict[str, Any]:
    ledger = merge_source_into_ledger(v_root)
    tasks = ledger.get("tasks", [])
    selected_ids = {t.get("task_id") for t in select_tasks(tasks, limit, lane, project)}
    ts = now_iso()
    dispatch_dir = self_root / DISPATCH_DIR
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    leased: list[dict[str, Any]] = []
    for t in tasks:
        if t.get("task_id") not in selected_ids:
            continue
        t["status"] = "leased"
        lease_info = {"leased_at": ts, "executor": executor, "lease_id": f"LEASE-{t['task_id']}-{ts}"}
        t["lease"] = lease_info
        t.setdefault("events", []).append({"ts": ts, "event": "leased", "executor": executor})
        card = dispatch_dir / f"{t['task_id']}.md"
        card.write_text(task_prompt(t), encoding="utf-8")
        t["dispatch"] = {"card": str(card), "created_at": ts, "executor": executor}
        leased.append({"task_id": t.get("task_id"), "lane": t.get("lane"), "project_id": t.get("project_id"), "card": str(card)})
        event(v_root, "task_leased", t.get("task_id"), lane=t.get("lane"), project_id=t.get("project_id"), card=str(card))
    ledger["generated_at"] = ts
    ledger["summary"] = summarize_tasks(tasks)
    write_json(ledger_path(v_root), ledger)
    render_status(v_root, ledger)
    write_json(v_root / REPORT_REL / "repair-task-leases.json", {"generated_at": ts, "leased": leased})
    return {"generated_at": ts, "leased_count": len(leased), "leased": leased, "dispatch_dir": str(dispatch_dir)}


def run_command(command: str, cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        argv = shlex.split(command)
        proc = subprocess.run(argv, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
        output = (proc.stdout or "") + (proc.stderr or "")
        return {"command": command, "argv": argv, "cwd": str(cwd), "exit_code": proc.returncode, "output_tail": output[-8000:]}
    except ValueError as exc:
        return {"command": command, "cwd": str(cwd), "exit_code": 2, "output_tail": f"invalid command syntax: {exc}"}
    except subprocess.TimeoutExpired as exc:
        out = ((exc.stdout or "") if isinstance(exc.stdout, str) else "") + ((exc.stderr or "") if isinstance(exc.stderr, str) else "")
        return {"command": command, "cwd": str(cwd), "exit_code": 124, "output_tail": out[-8000:], "timeout": timeout}


def verify(v_root: Path, self_root: Path, task_id: str, timeout: int) -> dict[str, Any]:
    refresh = run_command(
        f"python3 scripts/v_maintenance_control_plane.py --selfcheck-root {self_root} --v-root {v_root} --mode daily --repair-safe --format json",
        self_root,
        timeout,
    )
    ledger = merge_source_into_ledger(v_root)
    tasks = ledger.get("tasks", [])
    target = next((t for t in tasks if t.get("task_id") == task_id), None)
    if not target:
        raise SystemExit(f"task not found: {task_id}")
    ts = now_iso()
    target["status"] = "verifying"
    results = []
    for verifier in target.get("expected_verifiers") or []:
        command = str(verifier.get("command") or "")
        if not command:
            continue
        name = str(verifier.get("name") or command)
        if command.startswith("python3 -m selfcheck"):
            cwd = self_root
        else:
            cwd = Path(target.get("project_path") or self_root)
        res = run_command(command, cwd, timeout)
        res["name"] = name
        results.append(res)
    command_passed = bool(results) and all(r.get("exit_code") == 0 for r in results)
    latest_source = load_json(source_path(v_root), {"tasks": []})
    still_present = any(t.get("task_id") == task_id for t in latest_source.get("tasks", []))
    # Verifier commands proving the repo is healthy are necessary but not sufficient:
    # the originating finding must disappear from the latest RepairTask source before
    # the parent control plane may close it as resolved. This prevents pseudo-closure
    # when broad audits exit 0 while the normalized finding is still present.
    passed = command_passed and not still_present
    target["verification"] = {"verified_at": ts, "passed": passed, "refresh": refresh, "command_passed": command_passed, "finding_still_present": still_present, "results": results}
    target["status"] = "verified_resolved" if passed else "verification_failed"
    target.setdefault("events", []).append({"ts": ts, "event": "verified", "passed": passed, "command_passed": command_passed, "finding_still_present": still_present})
    event(v_root, "task_verified", task_id, passed=passed, command_passed=command_passed, finding_still_present=still_present)
    ledger["generated_at"] = ts
    ledger["summary"] = summarize_tasks(tasks)
    write_json(ledger_path(v_root), ledger)
    render_status(v_root, ledger)
    out_path = v_root / REPORT_REL / f"repair-task-verify-{task_id}.json"
    write_json(out_path, {"task_id": task_id, "passed": passed, "results": results})
    return {"task_id": task_id, "passed": passed, "status": target["status"], "evidence": str(out_path)}


def update_task(v_root: Path, task_id: str, new_status: str, note: str | None, evidence_path: str | None) -> dict[str, Any]:
    allowed = {
        "ready", "leased", "dispatched", "in_progress", "verifying", "verification_failed", "pending_verification",
        "needs_human", "accepted_false_positive", "accepted_risk", "verified_resolved",
    }
    if new_status not in allowed:
        raise SystemExit(f"invalid status {new_status}; allowed={sorted(allowed)}")
    ledger = load_json(ledger_path(v_root), None)
    if ledger is None:
        ledger = merge_source_into_ledger(v_root)
    tasks = ledger.get("tasks", [])
    target = next((t for t in tasks if t.get("task_id") == task_id), None)
    if not target:
        raise SystemExit(f"task not found: {task_id}")
    ts = now_iso()
    old_status = target.get("status")
    # Fail-closed: verified_resolved must use verify(), not manual update.
    if new_status == "verified_resolved":
        raise SystemExit("verified_resolved cannot be set manually; run action verify so parent-side verifier evidence is recorded")
    if new_status in {"needs_human", "accepted_false_positive", "accepted_risk"} and (not note or not evidence_path):
        raise SystemExit(f"{new_status} requires both --note and --evidence so terminal non-code decisions remain auditable")
    target["status"] = new_status
    record = {"ts": ts, "event": "manual_status_update", "from": old_status, "to": new_status}
    if note:
        record["note"] = note
    if evidence_path:
        record["evidence"] = evidence_path
    target.setdefault("events", []).append(record)
    if new_status in {"needs_human", "accepted_false_positive", "accepted_risk"}:
        target["resolution"] = {"status": new_status, "at": ts, "note": note, "evidence": evidence_path}
    event(v_root, "task_status_updated", task_id, old_status=old_status, new_status=new_status, note=note, evidence=evidence_path)
    ledger["generated_at"] = ts
    ledger["summary"] = summarize_tasks(tasks)
    write_json(ledger_path(v_root), ledger)
    render_status(v_root, ledger)
    return {"task_id": task_id, "old_status": old_status, "new_status": new_status, "ledger": str(ledger_path(v_root))}


def status(v_root: Path) -> dict[str, Any]:
    ledger = load_json(ledger_path(v_root), None)
    if ledger is None:
        ledger = merge_source_into_ledger(v_root)
    render_status(v_root, ledger)
    return {"summary": ledger.get("summary"), "ledger": str(ledger_path(v_root)), "markdown": str(v_root / TASK_STATUS_MD)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["sync", "plan", "lease", "verify", "update", "status"])
    ap.add_argument("--selfcheck-root", default=str(DEFAULT_SELF_ROOT))
    ap.add_argument("--v-root", default=str(DEFAULT_V_ROOT))
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--lane")
    ap.add_argument("--project")
    ap.add_argument("--task-id")
    ap.add_argument("--status")
    ap.add_argument("--note")
    ap.add_argument("--evidence")
    ap.add_argument("--executor", default="Hermes cron/delegation")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()

    self_root = Path(args.selfcheck_root).resolve()
    v_root = Path(args.v_root).resolve()
    if args.action == "sync":
        result = merge_source_into_ledger(v_root)
        result = {"summary": result.get("summary"), "sync": result.get("sync"), "ledger": str(ledger_path(v_root))}
    elif args.action == "plan":
        result = plan(v_root, self_root, args.limit, args.lane, args.project)
    elif args.action == "lease":
        result = lease(v_root, self_root, args.limit, args.lane, args.project, args.executor)
    elif args.action == "verify":
        if not args.task_id:
            raise SystemExit("--task-id is required for verify")
        result = verify(v_root, self_root, args.task_id, args.timeout)
    elif args.action == "update":
        if not args.task_id or not args.status:
            raise SystemExit("--task-id and --status are required for update")
        result = update_task(v_root, args.task_id, args.status, args.note, args.evidence)
    else:
        result = status(v_root)

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
