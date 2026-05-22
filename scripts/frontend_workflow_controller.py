#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_STATES = [
    "INTAKE",
    "CONTEXT_READY",
    "DESIGN_PACK_READY",
    "LANES_READY",
    "CRITIQUE_READY",
    "HUMAN_DECISION_REQUIRED",
    "ACCEPTED_FOR_FREEZE",
    "FROZEN",
    "IMPLEMENTATION_READY",
    "IMPLEMENTED",
    "PARITY_REVIEWED",
    "RUNTIME_VERIFIED",
    "FINAL_PASS",
    "BLOCKED",
]

PLACEHOLDERS = ("TODO", "TBD", "PLACEHOLDER")
STATE_FILE = "FRONTEND_WORKFLOW_STATE.json"
CANONICAL_TRANSITIONS = {
    "INTAKE": {"CONTEXT_READY", "BLOCKED"},
    "CONTEXT_READY": {"DESIGN_PACK_READY", "BLOCKED"},
    "DESIGN_PACK_READY": {"LANES_READY", "BLOCKED"},
    "LANES_READY": {"CRITIQUE_READY", "BLOCKED"},
    "CRITIQUE_READY": {"HUMAN_DECISION_REQUIRED", "BLOCKED"},
    "HUMAN_DECISION_REQUIRED": {"ACCEPTED_FOR_FREEZE", "BLOCKED"},
    "ACCEPTED_FOR_FREEZE": {"FROZEN", "BLOCKED"},
    "FROZEN": {"IMPLEMENTATION_READY", "BLOCKED"},
    "IMPLEMENTATION_READY": {"IMPLEMENTED", "BLOCKED"},
    "IMPLEMENTED": {"PARITY_REVIEWED", "BLOCKED"},
    "PARITY_REVIEWED": {"RUNTIME_VERIFIED", "BLOCKED"},
    "RUNTIME_VERIFIED": {"FINAL_PASS", "BLOCKED"},
    "FINAL_PASS": set(),
    "BLOCKED": set(),
}


@dataclass
class CheckResult:
    status: str
    workflow: str
    state: str | None = None
    target: str | None = None
    missing_evidence: list[str] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=list)
    allowed_next_actions: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "workflow": self.workflow,
            "state": self.state,
            "target": self.target,
            "missing_evidence": self.missing_evidence,
            "blocked_actions": self.blocked_actions,
            "allowed_next_actions": self.allowed_next_actions,
            "reasons": self.reasons,
        }


def fail(workflow: Path, reason: str, *, state: str | None = None, target: str | None = None, missing: list[str] | None = None) -> CheckResult:
    return CheckResult(
        status="BLOCKED",
        workflow=str(workflow),
        state=state,
        target=target,
        missing_evidence=missing or [],
        blocked_actions=[target] if target else [],
        reasons=[reason],
    )


def path_has_symlink(path: Path, stop: Path) -> bool:
    stop = stop.resolve()
    cur = path
    chain = [cur]
    while cur != stop and cur != cur.parent:
        cur = cur.parent
        chain.append(cur)
    return any(p.is_symlink() for p in chain)


def resolve_workflow(root: Path, raw: str) -> tuple[Path, str | None]:
    wf = Path(raw)
    if not wf.is_absolute():
        wf = root / wf
    governed = (root / ".hermes/workflows").resolve()
    resolved = wf.resolve()
    try:
        resolved.relative_to(governed)
    except Exception:
        return resolved, "workflow must stay under governed .hermes/workflows"
    if path_has_symlink(wf, governed):
        return resolved, "workflow path components must not be symlinked"
    return resolved, None


def safe_join(workflow: Path, rel: str | None) -> Path | None:
    if not rel:
        return None
    p = Path(rel)
    if p.is_absolute():
        candidate = p.resolve()
    else:
        candidate = (workflow / p).resolve()
    root = workflow.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError(f"path escapes workflow: {rel}")
    return candidate


def text_is_placeholder(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except UnicodeDecodeError:
        return False
    stripped = text.strip()
    if len(stripped) < 40:
        return True
    upper = stripped.upper()
    if any(token in upper for token in PLACEHOLDERS):
        return True
    if re.search(r"`<[^`]+>`|<lane-a|<responsible|<YYYY|<C\|D", stripped, re.IGNORECASE):
        return True
    return False


def evidence_file(workflow: Path, rel: str | None, label: str, *, reject_placeholder: bool = True) -> list[str]:
    missing: list[str] = []
    try:
        path = safe_join(workflow, rel)
    except ValueError as exc:
        return [f"{label}: {exc}"]
    if path is None:
        return [f"{label}: missing path"]
    if not path.exists() or not path.is_file():
        return [f"{label}: missing file {rel}"]
    if reject_placeholder and text_is_placeholder(path):
        return [f"{label}: placeholder or too thin {rel}"]
    return missing


def load_state(workflow: Path) -> tuple[dict[str, Any] | None, CheckResult | None]:
    state_path = workflow / STATE_FILE
    if state_path.is_symlink():
        return None, fail(workflow, f"refuse symlinked {STATE_FILE}", missing=[STATE_FILE])
    if not state_path.exists():
        return None, fail(workflow, f"missing {STATE_FILE}", missing=[STATE_FILE])
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, fail(workflow, f"invalid {STATE_FILE}: {exc}", missing=[STATE_FILE])
    required = ["schema_version", "workflow_id", "risk", "state", "allowed_transitions"]
    missing = [k for k in required if k not in data]
    if missing:
        return None, fail(workflow, f"state missing required fields: {', '.join(missing)}", missing=[STATE_FILE])
    if data.get("schema_version") != "1.0":
        return None, fail(workflow, "unsupported schema_version", missing=[STATE_FILE])
    if data.get("state") not in VALID_STATES:
        return None, fail(workflow, f"invalid state {data.get('state')}", missing=[STATE_FILE])
    if data.get("risk") not in {"A", "B", "C", "D", "E"}:
        return None, fail(workflow, f"invalid risk {data.get('risk')}", missing=[STATE_FILE])
    if not isinstance(data.get("workflow_id"), str) or not data.get("workflow_id").strip():
        return None, fail(workflow, "workflow_id must be a non-empty string", missing=[STATE_FILE])
    allowed = data.get("allowed_transitions")
    if not isinstance(allowed, list) or any(not isinstance(item, str) for item in allowed):
        return None, fail(workflow, "allowed_transitions must be a list of strings", missing=[STATE_FILE])
    if any(item not in VALID_STATES for item in allowed):
        return None, fail(workflow, "allowed_transitions contains unknown state", missing=[STATE_FILE])
    for key in ("project_adapter", "design_pack", "prototype_coverage", "parity_plan", "parity_report"):
        if key in data and data[key] is not None and not isinstance(data[key], str):
            return None, fail(workflow, f"{key} must be string or null", missing=[STATE_FILE])
    if "human_decision" in data and data["human_decision"] is not None:
        hd = data["human_decision"]
        if not isinstance(hd, dict):
            return None, fail(workflow, "human_decision must be object", missing=[STATE_FILE])
        for key in ("decision", "artifact", "notes", "signer", "signer_role", "decided_at", "decision_source", "notes_closure"):
            if key in hd and hd[key] is not None and not isinstance(hd[key], str):
                return None, fail(workflow, f"human_decision.{key} must be string or null", missing=[STATE_FILE])
    if "freeze" in data and data["freeze"] is not None:
        freeze = data["freeze"]
        if not isinstance(freeze, dict):
            return None, fail(workflow, "freeze must be object", missing=[STATE_FILE])
        for key in ("document", "payload"):
            if key in freeze and freeze[key] is not None and not isinstance(freeze[key], str):
                return None, fail(workflow, f"freeze.{key} must be string or null", missing=[STATE_FILE])
        shots = freeze.get("frozen_screenshots", [])
        if not isinstance(shots, list) or any(not isinstance(item, str) for item in shots):
            return None, fail(workflow, "freeze.frozen_screenshots must be a list of strings", missing=[STATE_FILE])
    if "runtime_evidence" in data:
        runtime = data["runtime_evidence"]
        if not isinstance(runtime, list) or any(not isinstance(item, str) for item in runtime):
            return None, fail(workflow, "runtime_evidence must be a list of strings", missing=[STATE_FILE])
    return data, None


def implementation_requirements(workflow: Path, state: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    missing += evidence_file(workflow, state.get("project_adapter"), "project_adapter")
    missing += evidence_file(workflow, state.get("design_pack"), "design_pack")
    missing += evidence_file(workflow, state.get("prototype_coverage"), "prototype_coverage")

    decision = state.get("human_decision") or {}
    if decision.get("decision") not in {"ACCEPTED", "ACCEPTED_WITH_NOTES"}:
        missing.append("human_decision: accepted decision required before implementation")
    for key in ("signer", "signer_role", "decided_at", "decision_source"):
        if not str(decision.get(key) or "").strip():
            missing.append(f"human_decision.{key}: required before implementation")
    if decision.get("decision") == "ACCEPTED_WITH_NOTES" and not str(decision.get("notes_closure") or "").strip():
        missing.append("human_decision.notes_closure: required when decision is ACCEPTED_WITH_NOTES")
    missing += evidence_file(workflow, decision.get("artifact"), "human_decision.artifact", reject_placeholder=False)

    freeze = state.get("freeze") or {}
    missing += evidence_file(workflow, freeze.get("document"), "freeze.document")
    missing += evidence_file(workflow, freeze.get("payload"), "freeze.payload", reject_placeholder=False)
    screenshots = freeze.get("frozen_screenshots") or []
    if not screenshots:
        missing.append("freeze.frozen_screenshots: at least one screenshot required")
    for shot in screenshots:
        missing += evidence_file(workflow, shot, "freeze.frozen_screenshot", reject_placeholder=False)

    missing += evidence_file(workflow, state.get("parity_plan"), "parity_plan")
    return missing


def final_requirements(workflow: Path, state: dict[str, Any]) -> list[str]:
    missing = implementation_requirements(workflow, state)
    missing += evidence_file(workflow, state.get("parity_report"), "parity_report")
    runtime = state.get("runtime_evidence") or []
    if not runtime:
        missing.append("runtime_evidence: at least one browser/runtime evidence file required")
    for item in runtime:
        missing += evidence_file(workflow, item, "runtime_evidence")
    return missing


def status(workflow: Path) -> CheckResult:
    data, err = load_state(workflow)
    if err:
        return err
    assert data is not None
    allowed = data.get("allowed_transitions") or []
    return CheckResult(
        status="PASS",
        workflow=str(workflow),
        state=data.get("state"),
        allowed_next_actions=allowed,
    )


def init_state(workflow: Path, workflow_id: str, risk: str, *, force: bool = False) -> CheckResult:
    state_path = workflow / STATE_FILE
    if state_path.is_symlink():
        return fail(workflow, f"refuse symlinked {STATE_FILE}", missing=[STATE_FILE])
    if state_path.exists() and not force:
        return fail(workflow, f"{STATE_FILE} already exists; pass --force to overwrite", missing=[])
    data = {
        "schema_version": "1.0",
        "workflow_id": workflow_id,
        "risk": risk,
        "state": "INTAKE",
        "allowed_transitions": ["CONTEXT_READY", "BLOCKED"],
        "project_adapter": "PROJECT_ADAPTER.yaml" if (workflow / "PROJECT_ADAPTER.yaml").exists() else None,
        "design_pack": "DESIGN_BRIEF.md" if (workflow / "DESIGN_BRIEF.md").exists() else None,
        "prototype_coverage": "PROTOTYPE_COVERAGE.md" if (workflow / "PROTOTYPE_COVERAGE.md").exists() else None,
        "human_decision": {"decision": None, "artifact": None, "signer": None, "signer_role": None, "decided_at": None, "decision_source": None, "notes": None, "notes_closure": None},
        "freeze": {
            "document": "PROTOTYPE_FREEZE.md" if (workflow / "PROTOTYPE_FREEZE.md").exists() else None,
            "payload": "prototype-freeze.json" if (workflow / "prototype-freeze.json").exists() else None,
            "frozen_screenshots": [],
        },
        "parity_plan": "PROTOTYPE_PARITY_PLAN.md" if (workflow / "PROTOTYPE_PARITY_PLAN.md").exists() else None,
        "parity_report": "PARITY_REPORT.md" if (workflow / "PARITY_REPORT.md").exists() else None,
        "runtime_evidence": [],
    }
    state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return CheckResult(
        status="PASS",
        workflow=str(workflow),
        state="INTAKE",
        target="init",
        allowed_next_actions=["CONTEXT_READY", "BLOCKED"],
        reasons=[f"created {STATE_FILE}"],
    )


def check_transition(workflow: Path, target: str) -> CheckResult:
    data, err = load_state(workflow)
    if err:
        err.target = target
        err.blocked_actions = [target]
        return err
    assert data is not None
    state = data.get("state")
    allowed = data.get("allowed_transitions") or []
    canonical = CANONICAL_TRANSITIONS.get(state, set())
    if target not in canonical:
        return CheckResult(
            status="BLOCKED",
            workflow=str(workflow),
            state=state,
            target=target,
            blocked_actions=[target],
            allowed_next_actions=sorted(canonical.intersection(set(allowed))),
            reasons=[f"illegal canonical transition from {state} to {target}"],
        )
    if target not in allowed:
        return CheckResult(
            status="BLOCKED",
            workflow=str(workflow),
            state=state,
            target=target,
            blocked_actions=[target],
            allowed_next_actions=allowed,
            reasons=[f"illegal transition from {state} to {target}"],
        )
    if target == "IMPLEMENTATION_READY":
        missing = implementation_requirements(workflow, data)
    elif target == "FINAL_PASS":
        missing = final_requirements(workflow, data)
    else:
        missing = []
    if missing:
        return CheckResult(
            status="BLOCKED",
            workflow=str(workflow),
            state=state,
            target=target,
            missing_evidence=missing,
            blocked_actions=[target],
            allowed_next_actions=allowed,
            reasons=["required frontend workflow evidence is missing or placeholder"],
        )
    return CheckResult(
        status="PASS",
        workflow=str(workflow),
        state=target,
        target=target,
        allowed_next_actions=[],
        reasons=[f"transition allowed: {state} -> {target}"],
    )


def print_result(result: CheckResult, fmt: str) -> None:
    data = result.to_dict()
    if fmt == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    print(f"status={data['status']}")
    print(f"workflow={data['workflow']}")
    if data.get("state"):
        print(f"state={data['state']}")
    if data.get("target"):
        print(f"target={data['target']}")
    for reason in data.get("reasons") or []:
        print(f"reason={reason}")
    for item in data.get("missing_evidence") or []:
        print(f"missing={item}")
    for item in data.get("allowed_next_actions") or []:
        print(f"allowed={item}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Frontend workflow controller: state/evidence gate for prototype-first frontend work.")
    sub = ap.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".")
    common.add_argument("--workflow", required=True, help="Workflow directory containing FRONTEND_WORKFLOW_STATE.json")
    common.add_argument("--format", choices=["json", "text"], default="json")
    sub.add_parser("status", parents=[common])
    init = sub.add_parser("init", parents=[common])
    init.add_argument("--workflow-id", required=True)
    init.add_argument("--risk", required=True, choices=["A", "B", "C", "D", "E"])
    init.add_argument("--force", action="store_true")
    check = sub.add_parser("check-transition", parents=[common])
    check.add_argument("--to", required=True, choices=VALID_STATES)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    workflow, workflow_err = resolve_workflow(root, args.workflow)
    if workflow_err:
        result = fail(workflow, workflow_err, target=getattr(args, "to", None), missing=[str(workflow)])
    elif not workflow.exists() or not workflow.is_dir():
        result = fail(workflow, "workflow directory does not exist", target=getattr(args, "to", None), missing=[str(workflow)])
    elif args.command == "init":
        result = init_state(workflow, args.workflow_id, args.risk, force=args.force)
    elif args.command == "status":
        result = status(workflow)
    else:
        result = check_transition(workflow, args.to)
    print_result(result, args.format)
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
