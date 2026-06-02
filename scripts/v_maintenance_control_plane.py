#!/usr/bin/env python3
"""V workspace maintenance control-plane ledger.

This script turns scanner outputs into durable maintenance findings with
stable IDs, lifecycle timestamps, project classification, and notification
summary. It is intentionally conservative: it records and routes work; it does
not delete source/docs or perform behavior-affecting fixes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"PyYAML is required: {exc}")


DOC_FEATURE = "project-doc-governance"
CODE_FEATURE = "project-code-health-governance"
REPORT_INPUTS = [
    (DOC_FEATURE, "reports/project-doc-governance/audit.json"),
    (CODE_FEATURE, "reports/project-code-health-governance/audit.json"),
]


@dataclass
class LedgerFinding:
    finding_id: str
    project_id: str
    type: str
    severity: str
    category: str
    path: str
    message: str
    recommended_action: str
    first_seen: str
    last_seen: str
    seen_count: int
    status: str
    auto_fixable: bool
    human_required: bool
    repair_strategy: str
    action_owner: str
    cadence: str
    evidence: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"registry not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def stable_id(feature: str, path: str, category: str, message: str) -> str:
    raw = f"{feature}\n{path}\n{category}\n{normalize_message(message)}"
    return "MNT-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()


def normalize_message(message: str) -> str:
    # Keep IDs stable when line counts drift moderately.
    return re.sub(r"\b\d+\b", "N", message.strip().lower())


def project_for_path(path: str, projects: list[dict[str, Any]]) -> str:
    norm = path.lstrip("./")
    best = ("workspace", 0)
    for project in projects:
        pid = str(project.get("id", ""))
        ppath = str(project.get("path", "")).rstrip("/")
        name = Path(ppath).name
        prefixes = [name + "/"]
        if pid == "workspace-docs":
            prefixes.append("docs/")
        for prefix in prefixes:
            if norm == prefix.rstrip("/") or norm.startswith(prefix):
                if len(prefix) > best[1]:
                    best = (pid, len(prefix))
    return best[0]


def type_for(feature: str, category: str, message: str) -> str:
    text = f"{category} {message}".lower()
    if feature == DOC_FEATURE:
        if "evidence" in text or "pass/success" in text:
            return "evidence_gap"
        if "link target not found" in text or "todo" in text or "mock/fake" in text:
            return "docs_standards"
        return "docs_staleness"
    if "large source file" in text or "repeated source filename" in text:
        return "code_redundancy"
    if "temporary/backup" in text:
        return "code_hygiene"
    return "code_logic_risk"


def auto_fixable_for(ftype: str, human_required: bool, message: str) -> bool:
    if human_required:
        return False
    # Direct auto-fix must be deterministic. Most evidence/doc findings need
    # semantic review, so they are delegated rather than patched silently.
    if ftype == "code_hygiene" and "Temporary/backup file" in message:
        return False  # deletion still needs review in this workspace
    if ftype == "docs_standards" and "Markdown link target not found" in message:
        return True
    return False


def repair_strategy_for(ftype: str, severity: str, human_required: bool, auto_fixable: bool) -> tuple[str, str]:
    if human_required or severity == "human":
        return "human_decision", "郭凯"
    if severity == "error":
        return "delegate_repair", "Hermes/工程代理"
    if auto_fixable:
        return "direct_safe_repair", "Hermes maintenance cron"
    if ftype in {"code_redundancy", "code_logic_risk", "contract_drift", "docs_redundancy", "docs_staleness", "docs_standards", "evidence_gap", "code_hygiene"}:
        return "delegate_repair", "Hermes/工程代理"
    return "monitor", "Hermes maintenance cron"


def cadence_for(ftype: str, severity: str, human_required: bool) -> str:
    if human_required or severity in {"error", "human"}:
        return "event_or_2h"
    if ftype in {"code_logic_risk", "contract_drift"}:
        return "event_or_2h"
    if ftype in {"code_redundancy", "docs_redundancy", "docs_staleness"}:
        return "daily_or_weekly"
    return "daily"


def ingest_reports(v_root: Path, projects: list[dict[str, Any]], timestamp: str) -> list[LedgerFinding]:
    out: list[LedgerFinding] = []
    for feature, rel_report in REPORT_INPUTS:
        report_path = v_root / rel_report
        report = load_json(report_path)
        for raw in report.get("findings") or []:
            path = str(raw.get("path") or ".")
            category = str(raw.get("category") or feature)
            message = str(raw.get("message") or "")
            recommended = str(raw.get("recommended_action") or "Review and route through maintenance control plane.")
            human_required = bool(raw.get("human_required"))
            ftype = type_for(feature, category, message)
            severity = str(raw.get("severity") or "warn")
            auto_fixable = auto_fixable_for(ftype, human_required, message)
            repair_strategy, action_owner = repair_strategy_for(ftype, severity, human_required, auto_fixable)
            finding_id = stable_id(feature, path, category, message)
            out.append(LedgerFinding(
                finding_id=finding_id,
                project_id=project_for_path(path, projects),
                type=ftype,
                severity=severity,
                category=category,
                path=path,
                message=message,
                recommended_action=recommended,
                first_seen=timestamp,
                last_seen=timestamp,
                seen_count=1,
                status="needs_human" if human_required else "open",
                auto_fixable=auto_fixable,
                human_required=human_required,
                repair_strategy=repair_strategy,
                action_owner=action_owner,
                cadence=cadence_for(ftype, severity, human_required),
                evidence=[rel_report],
            ))
    return out


def merge_ledger(existing: dict[str, Any], current: list[LedgerFinding], timestamp: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    old_by_id = {f.get("finding_id"): f for f in existing.get("findings", []) if f.get("finding_id")}
    current_ids = {f.finding_id for f in current}
    merged: list[dict[str, Any]] = []
    new_count = 0
    reopened_count = 0
    for item in current:
        data = asdict(item)
        old = old_by_id.get(item.finding_id)
        if old:
            data["first_seen"] = old.get("first_seen") or item.first_seen
            data["seen_count"] = int(old.get("seen_count") or 0) + 1
            if old.get("status") == "resolved":
                reopened_count += 1
                data["status"] = "open"
            else:
                data["status"] = old.get("status") or data["status"]
            # Preserve user/agent workflow state, but refresh routing fields for old ledger rows.
            data["repair_strategy"] = data.get("repair_strategy") or old.get("repair_strategy") or "monitor"
            data["action_owner"] = data.get("action_owner") or old.get("action_owner") or "Hermes maintenance cron"
            data["cadence"] = data.get("cadence") or old.get("cadence") or "daily"
            old_evidence = list(old.get("evidence") or [])
            data["evidence"] = sorted(set(old_evidence + data["evidence"]))
        else:
            new_count += 1
        merged.append(data)

    resolved_count = 0
    for fid, old in old_by_id.items():
        if fid not in current_ids:
            clone = dict(old)
            if clone.get("status") not in {"resolved", "accepted_risk"}:
                clone["status"] = "resolved"
                clone["resolved_at"] = timestamp
                resolved_count += 1
            merged.append(clone)

    return sorted(merged, key=lambda f: (f.get("status") == "resolved", f.get("project_id", ""), f.get("type", ""), f.get("path", ""))), {
        "new": new_count,
        "resolved": resolved_count,
        "reopened": reopened_count,
    }


def summarize(findings: list[dict[str, Any]], deltas: dict[str, int], timestamp: str) -> dict[str, Any]:
    open_findings = [f for f in findings if f.get("status") not in {"resolved", "accepted_risk"}]
    by_type: dict[str, int] = {}
    by_project: dict[str, int] = {}
    by_status: dict[str, int] = {}
    human_required: list[dict[str, Any]] = []
    high_risk: list[dict[str, Any]] = []
    direct_safe_repair: list[dict[str, Any]] = []
    delegate_repair: list[dict[str, Any]] = []
    for f in open_findings:
        by_type[f.get("type", "unknown")] = by_type.get(f.get("type", "unknown"), 0) + 1
        by_project[f.get("project_id", "unknown")] = by_project.get(f.get("project_id", "unknown"), 0) + 1
        by_status[f.get("status", "open")] = by_status.get(f.get("status", "open"), 0) + 1
        if f.get("human_required") or f.get("status") == "needs_human":
            human_required.append(f)
        if f.get("severity") in {"error", "human"}:
            high_risk.append(f)
        if f.get("repair_strategy") == "direct_safe_repair":
            direct_safe_repair.append(f)
        if f.get("repair_strategy") == "delegate_repair":
            delegate_repair.append(f)
    status = "NEEDS_HUMAN" if human_required else ("NEEDS_REPAIR" if high_risk else "PASS_WITH_NOTES" if open_findings else "PASS")
    notify = bool(human_required or high_risk or deltas.get("new", 0) > 0 or deltas.get("reopened", 0) > 0)
    return {
        "generated_at": timestamp,
        "status": status,
        "notify": notify,
        "deltas": deltas,
        "counts": {
            "total": len(findings),
            "open": len(open_findings),
            "human_required": len(human_required),
            "high_risk": len(high_risk),
            "direct_safe_repair": len(direct_safe_repair),
            "delegate_repair": len(delegate_repair),
            "by_type": dict(sorted(by_type.items())),
            "by_project": dict(sorted(by_project.items(), key=lambda kv: kv[1], reverse=True)),
            "by_status": dict(sorted(by_status.items())),
        },
        "top_human_required": trim_findings(human_required, 5),
        "top_high_risk": trim_findings(high_risk, 5),
        "top_direct_safe_repair": trim_findings(direct_safe_repair, 5),
        "top_delegate_repair": trim_findings(delegate_repair, 10),
        "top_open": trim_findings(open_findings, 12),
        "evidence": {
            "ledger": "reports/maintenance-control-plane/findings-ledger.json",
            "markdown": "reports/maintenance-control-plane/latest.md",
            "repair_tasks": "reports/maintenance-control-plane/repair-tasks.json",
            "inputs": [rel for _, rel in REPORT_INPUTS],
        },
        "next_action": "需要郭凯决策" if human_required else "Hermes/工程代理按维护队列处理",
    }


def trim_findings(items: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    keys = ["finding_id", "project_id", "type", "severity", "status", "repair_strategy", "action_owner", "cadence", "actionability", "repair_decision", "not_repairing_now_reason", "path", "message", "recommended_action"]
    return [{k: f.get(k) for k in keys} for f in items[:n]]


def render_md(summary: dict[str, Any]) -> str:
    lines = [
        "# V Workspace Maintenance Control Plane",
        "",
        f"- Status: `{summary['status']}`",
        f"- Generated: `{summary['generated_at']}`",
        f"- Notify: `{summary['notify']}`",
        f"- Next action: {summary['next_action']}",
        "",
        "## Counts",
        "",
        f"- Open findings: {summary['counts']['open']}",
        f"- New this run: {summary['deltas'].get('new', 0)}",
        f"- Resolved this run: {summary['deltas'].get('resolved', 0)}",
        f"- Reopened this run: {summary['deltas'].get('reopened', 0)}",
        f"- Human required: {summary['counts']['human_required']}",
        f"- High risk: {summary['counts']['high_risk']}",
        f"- Direct safe repair candidates: {summary['counts']['direct_safe_repair']}",
        f"- Delegate repair candidates: {summary['counts']['delegate_repair']}",
        "",
        "## By Project",
        "",
    ]
    if not summary["counts"]["by_project"]:
        lines.append("- none")
    for project, count in summary["counts"]["by_project"].items():
        lines.append(f"- `{project}`: {count}")
    lines += ["", "## By Type", ""]
    if not summary["counts"]["by_type"]:
        lines.append("- none")
    for ftype, count in summary["counts"]["by_type"].items():
        lines.append(f"- `{ftype}`: {count}")
    lines += ["", "## Top Open Findings", ""]
    if not summary.get("top_open"):
        lines.append("- none")
    for f in summary.get("top_open", []):
        lines.append(f"- `{f['finding_id']}` [{f['severity']}/{f['type']}] `{f['project_id']}` `{f['path']}` — {f['message']}")
    lines += ["", "## Repair Queue", ""]
    direct = summary.get("top_direct_safe_repair") or []
    delegated = summary.get("top_delegate_repair") or []
    if not direct and not delegated:
        lines.append("- none")
    for f in direct:
        lines.append(f"- DIRECT `{f['finding_id']}` `{f['project_id']}` `{f['path']}` — {f['message']}")
    for f in delegated:
        lines.append(f"- DELEGATE `{f['finding_id']}` `{f['project_id']}` `{f['path']}` — {f['message']}")
    tasks = summary.get("repair_tasks") or {}
    if tasks:
        lines += ["", "## AI RepairTasks", ""]
        lines.append(f"- Total: {tasks.get('total', 0)}")
        for lane, count in (tasks.get("by_lane") or {}).items():
            lines.append(f"- `{lane}`: {count}")
        lines.append(f"- Ledger: `{tasks.get('json')}`")
    lines += ["", "## Human Required", ""]
    if not summary.get("top_human_required"):
        lines.append("- none")
    for f in summary.get("top_human_required", []):
        lines.append(f"- `{f['finding_id']}` `{f['project_id']}` `{f['path']}` — {f['message']}")
    lines += ["", "## Evidence", ""]
    for k, v in summary["evidence"].items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")
    return "\n".join(lines)


def actionability_for(f: dict[str, Any], mode: str) -> tuple[str, str, str]:
    """Return (actionability, repair_decision, not_repairing_now_reason).

    Principle: every finding must be evaluated immediately after scan. If it is
    not repaired now, the ledger must say why. "delegate_now" means the scan run
    must create a dispatch card immediately; a later agent may execute the code
    change, but the issue is no longer merely reported.
    """
    if f.get("human_required") or f.get("repair_strategy") == "human_decision":
        return "blocked", "human_decision", "requires human decision because action may be destructive, contractual, product/architecture-changing, or permission/secret-bound"
    if f.get("repair_strategy") == "direct_safe_repair":
        return "immediate", "repair_now", ""
    if f.get("repair_strategy") == "delegate_repair":
        if f.get("type") == "code_redundancy" and f.get("severity") == "info":
            return "actionable", "delegate_now", "not patched directly because repeated names may be legitimate architecture; dispatched for validation/refactor decision with evidence"
        if f.get("type") == "code_redundancy" and f.get("severity") == "warn":
            return "actionable", "delegate_now", "not patched directly because large-file refactor can change behavior; dispatched for isolated branch, tests, and review"
        if f.get("type") in {"evidence_gap", "docs_standards", "docs_staleness"}:
            return "actionable", "delegate_now", "not patched silently because evidence/doc semantics must be verified; dispatched for document repair and verifier evidence"
        return "actionable", "delegate_now", "not patched directly because fix requires reproduction, scoped implementation, and verification"
    return "monitor", "monitor", "no safe repair rule matched; keep in ledger until scanner/routing improves"


def enrich_actionability(items: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    out = []
    for f in items:
        g = dict(f)
        actionability, decision, reason = actionability_for(g, mode)
        g["actionability"] = actionability
        g["repair_decision"] = decision
        g["not_repairing_now_reason"] = reason
        out.append(g)
    return out


def repair_task_id_for(finding_id: str) -> str:
    return "RT-" + hashlib.sha1(finding_id.encode("utf-8")).hexdigest()[:12].upper()


def lane_for(f: dict[str, Any], projects_by_id: dict[str, dict[str, Any]]) -> str:
    project = projects_by_id.get(str(f.get("project_id") or ""), {})
    kind = str(project.get("kind") or "")
    ftype = str(f.get("type") or "")
    if ftype in {"evidence_gap", "docs_standards", "docs_staleness", "docs_redundancy"} or kind == "docs":
        return "doc-agent"
    if "frontend" in kind:
        return "frontend-agent"
    if "backend" in kind:
        return "backend-agent"
    if ftype in {"contract_drift", "code_logic_risk"}:
        return "contract-agent"
    return "maintenance-agent"


def expected_verifiers_for(f: dict[str, Any], projects_by_id: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    project = projects_by_id.get(str(f.get("project_id") or ""), {})
    commands = project.get("commands") or {}
    verifiers: list[dict[str, str]] = []
    if f.get("type") in {"evidence_gap", "docs_standards", "docs_staleness", "docs_redundancy"}:
        verifiers.append({"name": "v-doc-governance", "command": "python3 scripts/governance_audit.py --root /root/work/v --feature project-doc-governance --format json"})
    if str(project.get("kind") or "").endswith("backend"):
        cmd = str(commands.get("test") or commands.get("build") or "go test ./...")
        verifiers.append({"name": "project-backend-tests", "command": cmd})
    if str(project.get("kind") or "").endswith("frontend"):
        if commands.get("typecheck"):
            verifiers.append({"name": "project-frontend-typecheck", "command": str(commands["typecheck"])})
        if commands.get("build"):
            verifiers.append({"name": "project-frontend-build", "command": str(commands["build"])})
    if not verifiers:
        verifiers.append({"name": "selfcheck-validate", "command": "python3 -m selfcheck validate --root ."})
    return verifiers


def build_repair_tasks(
    queue: dict[str, Any],
    reports_dir: Path,
    timestamp: str,
    mode: str,
    projects_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Create the AI-native RepairTask ledger.

    RepairTask is the durable work object. It binds a finding to a lane, sandbox
    requirement, verifier contract, evidence paths, and resumption status. This
    keeps cron from being the real system of record and avoids trusting subagent
    self-reports without parent verification.
    """
    task_items: list[dict[str, Any]] = []
    # RepairTask source is the durable universe of actionable work. It must not
    # shrink just because a light run decides not to execute low-urgency tasks in
    # this cadence; otherwise the lifecycle controller will incorrectly treat
    # existing tasks as missing-from-scan and move them to pending_verification.
    delegated_source = queue.get("all_delegate_repair") or queue.get("delegate_repair") or []
    task_source = list(queue.get("direct_safe_repair") or []) + list(delegated_source)
    for f in task_source:
        project = projects_by_id.get(str(f.get("project_id") or ""), {})
        decision = str(f.get("repair_decision") or "")
        sandbox_required = decision != "repair_now" or str(project.get("kind") or "") != "docs"
        sandbox_contract = {
            "required": sandbox_required,
            "isolation": "dedicated_worktree_or_branch" if sandbox_required else "in_place_allowed_for_low_risk_docs",
            "destructive_actions_allowed": False,
        }
        task = {
            "task_id": repair_task_id_for(str(f.get("finding_id"))),
            "finding_id": f.get("finding_id"),
            "status": "ready",
            "mode_created": mode,
            "lane": lane_for(f, projects_by_id),
            "project_id": f.get("project_id"),
            "project_path": project.get("path"),
            "finding_type": f.get("type"),
            "severity": f.get("severity"),
            "path": f.get("path"),
            "decision": decision,
            "owner": "Hermes/工程代理",
            "sandbox": sandbox_contract,
            "sandbox_required": sandbox_required,
            "worktree_policy": "required_for_code_or_contract_changes" if sandbox_required else "optional_for_low_risk_docs",
            "permissions": {
                "may_edit_source": bool(str(project.get("kind") or "") != "docs"),
                "may_edit_docs": True,
                "may_delete_source": False,
                "may_change_contracts": False,
                "may_run_tests": True,
                "requires_human_before_destructive_action": True,
            },
            "expected_verifiers": expected_verifiers_for(f, projects_by_id),
            "acceptance_contract": [
                "validate finding is real or explicitly mark false positive with evidence",
                "apply the smallest safe patch if real and actionable",
                "parent control plane reruns the expected verifier(s); subagent self-report is not closure",
                "update findings ledger only after verifier evidence exists",
            ],
            "evidence_paths": [
                "reports/maintenance-control-plane/findings-ledger.json",
                "reports/maintenance-control-plane/repair-queue.json",
                "reports/maintenance-control-plane/repair-tasks.json",
            ],
            "created_at": timestamp,
            "last_updated_at": timestamp,
            "resume_hint": f"Use lifecycle dispatch card .hermes/dispatch/v-maintenance-tasks/{repair_task_id_for(str(f.get('finding_id')))}.md after v_repair_task_control.py lease; verify task {repair_task_id_for(str(f.get('finding_id')))} before closure.",
            "not_repairing_directly_reason": f.get("not_repairing_now_reason") or "direct deterministic repair candidate",
        }
        task_items.append(task)
    by_lane: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for task in task_items:
        by_lane[task["lane"]] = by_lane.get(task["lane"], 0) + 1
        by_status[task["status"]] = by_status.get(task["status"], 0) + 1
    ledger = {
        "version": 1,
        "generated_at": timestamp,
        "mode": mode,
        "policy_version": "ai_native_repair_task_v1",
        "contract": "RepairTask is the durable AI work object: finding -> decision -> lane -> sandbox/worktree -> verifier -> evidence -> closure.",
        "counts": {"total": len(task_items), "by_lane": dict(sorted(by_lane.items())), "by_status": dict(sorted(by_status.items()))},
        "tasks": task_items,
    }
    (reports_dir / "repair-tasks.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# V Maintenance AI RepairTasks", "", f"- Generated: `{timestamp}`", f"- Mode: `{mode}`", "- Policy: `ai_native_repair_task_v1`", "", "## Counts", "", f"- Total tasks: {len(task_items)}"]
    for lane, count in sorted(by_lane.items()):
        lines.append(f"- `{lane}`: {count}")
    lines += ["", "## Tasks", ""]
    if not task_items:
        lines.append("- none")
    for task in task_items[:120]:
        verifiers = "; ".join(v["name"] for v in task["expected_verifiers"])
        lines.append(f"- `{task['task_id']}` `{task['lane']}` `{task['project_id']}` finding `{task['finding_id']}` path `{task['path']}` status `{task['status']}` sandbox `{task['sandbox_required']}` verifiers: {verifiers}")
    (reports_dir / "repair-tasks.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ledger


def build_repair_queue(findings: list[dict[str, Any]], reports_dir: Path, timestamp: str, mode: str) -> dict[str, Any]:
    open_findings = [f for f in findings if f.get("status") not in {"resolved", "accepted_risk"}]
    enriched = enrich_actionability(open_findings, mode)
    direct = [f for f in enriched if f.get("repair_decision") == "repair_now"]
    delegated = [f for f in enriched if f.get("repair_decision") == "delegate_now"]
    human = [f for f in enriched if f.get("repair_decision") == "human_decision"]
    monitor = [f for f in enriched if f.get("repair_decision") == "monitor"]

    if mode == "light":
        # Light runs still evaluate every open finding, but only execute/dispatch urgent or changed-signal work.
        # Non-urgent findings remain in the decision ledger with explicit reasons.
        execution_delegated = [f for f in delegated if f.get("cadence") == "event_or_2h" or f.get("severity") in {"error", "human"}]
    else:
        execution_delegated = delegated

    queue = {
        "generated_at": timestamp,
        "mode": mode,
        "policy_version": "scan_evaluate_repair_or_explain_v2",
        "evaluation_contract": "Every scan evaluates every finding. repair_now is fixed immediately when deterministic; delegate_now creates dispatch immediately; human_decision records the blocker; monitor records why no repair is safe yet.",
        "direct_safe_repair": trim_findings(direct, 100),
        "delegate_repair": trim_findings(execution_delegated, 100),
        "all_delegate_repair": trim_findings(delegated, 500),
        "human_required": trim_findings(human, 100),
        "monitor_only": trim_findings(monitor, 100),
        "counts": {
            "evaluated": len(enriched),
            "repair_now": len(direct),
            "delegate_now": len(delegated),
            "delegate_in_this_mode": len(execution_delegated),
            "human_decision": len(human),
            "monitor": len(monitor),
        },
        "policy": {
            "direct_safe_repair": "Patch immediately only when deterministic and low-risk, then rerun verifier before resolving.",
            "delegate_repair": "Create dispatch immediately after scan; execution must use isolated branch/worktree where code changes are involved, with verification evidence.",
            "human_required": "Escalate only for product/architecture/deletion/secret/destructive decisions, with exact reason.",
            "not_repairing_now": "Every non-repaired item must carry not_repairing_now_reason.",
        },
    }
    (reports_dir / "repair-queue.json").write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# V Maintenance Repair Queue", "", f"- Generated: `{timestamp}`", f"- Mode: `{mode}`", f"- Policy: `{queue['policy_version']}`", "", "## Evaluation Counts", ""]
    for k, v in queue["counts"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    sections = [
        ("Direct Safe Repair Now", "direct_safe_repair"),
        ("Delegate Repair Now", "delegate_repair"),
        ("Human Decision", "human_required"),
        ("Monitor Only", "monitor_only"),
    ]
    for title, key in sections:
        lines += [f"## {title}", ""]
        items = queue[key]
        if not items:
            lines.append("- none")
        for f in items:
            reason = f.get("not_repairing_now_reason") or ""
            suffix = f" Reason: {reason}" if reason else ""
            lines.append(f"- `{f['finding_id']}` [{f['severity']}/{f['type']}] `{f['project_id']}` `{f['path']}` — {f['message']} Decision: `{f.get('repair_decision')}`.{suffix} Next: {f['recommended_action']}")
        lines.append("")
    (reports_dir / "repair-queue.md").write_text("\n".join(lines), encoding="utf-8")

    # Dispatch cards are now owned by scripts/v_repair_task_control.py lease
    # under .hermes/dispatch/v-maintenance-tasks/{task_id}.md. Keeping this
    # script source-only prevents agents from bypassing RepairTask lifecycle
    # state (leased/in_progress/verified) by acting on finding-id cards.
    return queue


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck-root", default="/root/work/agentic-selfcheck")
    ap.add_argument("--v-root", default="/root/work/v")
    ap.add_argument("--registry", default="config/v-project-registry.yaml")
    ap.add_argument("--format", choices=["json", "markdown", "both"], default="both")
    ap.add_argument("--mode", choices=["light", "daily", "weekly"], default="daily")
    ap.add_argument("--repair-safe", action="store_true", help="Generate repair queue and dispatch cards; direct fixes remain conservative.")
    args = ap.parse_args()

    self_root = Path(args.selfcheck_root).resolve()
    v_root = Path(args.v_root).resolve()
    registry_path = Path(args.registry)
    if not registry_path.is_absolute():
        registry_path = self_root / registry_path
    registry = load_yaml(registry_path)
    projects = list(registry.get("projects") or [])
    projects_by_id = {str(p.get("id")): p for p in projects if p.get("id")}
    reports_dir = Path(registry.get("workspace", {}).get("reports_dir") or (v_root / "reports/maintenance-control-plane"))
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = now_iso()
    ledger_path = reports_dir / "findings-ledger.json"
    existing = load_json(ledger_path)
    current = ingest_reports(v_root, projects, timestamp)
    merged, deltas = merge_ledger(existing, current, timestamp)
    summary = summarize(merged, deltas, timestamp)
    repair_queue = build_repair_queue(merged, reports_dir, timestamp, args.mode) if args.repair_safe else None
    repair_tasks = build_repair_tasks(repair_queue, reports_dir, timestamp, args.mode, projects_by_id) if repair_queue else None
    if repair_queue:
        summary["repair_queue"] = {
            "json": "reports/maintenance-control-plane/repair-queue.json",
            "markdown": "reports/maintenance-control-plane/repair-queue.md",
            "direct_safe_repair": len(repair_queue["direct_safe_repair"]),
            "delegate_repair": len(repair_queue["delegate_repair"]),
            "all_delegate_repair": len(repair_queue.get("all_delegate_repair", [])),
            "human_required": len(repair_queue["human_required"]),
        }
    if repair_tasks:
        summary["repair_tasks"] = {
            "json": "reports/maintenance-control-plane/repair-tasks.json",
            "markdown": "reports/maintenance-control-plane/repair-tasks.md",
            "total": repair_tasks["counts"]["total"],
            "by_lane": repair_tasks["counts"].get("by_lane", {}),
        }

    ledger = {
        "version": 1,
        "workspace": registry.get("workspace", {}).get("id", "v-workspace"),
        "generated_at": timestamp,
        "registry": str(registry_path),
        "summary": summary,
        "findings": merged,
    }
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    (reports_dir / "latest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md = render_md(summary)
    (reports_dir / "latest.md").write_text(md, encoding="utf-8")

    if args.format in {"json", "both"}:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.format in {"markdown", "both"}:
        print(md)


if __name__ == "__main__":
    main()
