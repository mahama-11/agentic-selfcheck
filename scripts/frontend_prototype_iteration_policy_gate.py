#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REQUIRED_TEMPLATE = Path("templates/frontend/prototype-iteration-policy/PROTOTYPE_ITERATION_POLICY.md")
DECISIONS = {"optimize_existing", "fresh_lane", "restart_from_foundation"}
STRUCTURAL_TRIGGERS = {
    "none",
    "product_goal_changed",
    "target_user_changed",
    "core_ia_or_flow_invalid",
    "existing_baseline_invalid",
    "backend_api_feasibility_changed",
    "direction_structurally_rejected",
}
STRUCTURAL_NON_NONE = STRUCTURAL_TRIGGERS - {"none"}
PLACEHOLDER_RE = re.compile(r"\b(TODO|TBD|placeholder|Fill|iteration-001)\b|待补|填写", re.I)


def finding(path: Path | str, msg: str) -> dict[str, str]:
    return {"severity": "error", "path": str(path), "message": msg}


def is_within(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def path_has_symlink(path: Path, stop: Path) -> bool:
    stop = stop.resolve()
    cur = path
    chain = [cur]
    while cur != stop and cur != cur.parent:
        cur = cur.parent
        chain.append(cur)
    return any(p.is_symlink() for p in chain)


def resolve_workflow(root: Path, raw: str) -> Path:
    wf = Path(raw)
    if not wf.is_absolute():
        wf = root / wf
    governed = (root / ".hermes/workflows").resolve()
    resolved = wf.resolve()
    if not is_within(resolved, governed):
        raise ValueError("workflow must stay under governed .hermes/workflows")
    if path_has_symlink(wf, governed) or any(p.is_symlink() for p in resolved.rglob("*")):
        raise ValueError("workflow and iteration artifacts must not be symlinked")
    return resolved


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def field(text: str, key: str) -> str:
    m = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", text, flags=re.M)
    return m.group(1).strip() if m else ""


def section(text: str, title: str) -> str:
    m = re.search(rf"^##\s+{re.escape(title)}\s*$([\s\S]*?)(?=^##\s+|\Z)", text, flags=re.M)
    return m.group(1).strip() if m else ""


def concrete_bullets(block: str) -> list[str]:
    bullets = []
    for line in block.splitlines():
        s = line.strip()
        if not s.startswith("-"):
            continue
        item = s[1:].strip()
        if not item or PLACEHOLDER_RE.search(item):
            continue
        # Require something after a label colon, not just the template label.
        if item.endswith(":"):
            continue
        if ":" in item and not item.split(":", 1)[1].strip():
            continue
        bullets.append(item)
    return bullets


def resolve_artifact(wf: Path, raw: str) -> tuple[Path | None, str | None]:
    if not raw:
        return None, None
    p = Path(raw)
    if not p.is_absolute():
        p = wf / p
    try:
        resolved = p.resolve()
        resolved.relative_to(wf.resolve())
        return resolved, None
    except Exception:
        return None, f"artifact path must stay under workflow: {raw}"


def check_policy(root: Path, workflow_raw: str, policy_rel: str) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    if not (root / REQUIRED_TEMPLATE).exists():
        findings.append(finding(root / REQUIRED_TEMPLATE, "required prototype iteration policy template missing"))
    try:
        wf = resolve_workflow(root, workflow_raw)
    except ValueError as exc:
        return {"status": "FAIL", "findings": [finding(workflow_raw, str(exc))]}
    policy = wf / policy_rel
    policy_ok = True
    try:
        policy.resolve().relative_to(wf.resolve())
    except Exception:
        findings.append(finding(policy, "policy file must stay under workflow"))
        policy_ok = False
    if not policy_ok:
        text = ""
    elif not policy.exists() or policy.stat().st_size < 500:
        findings.append(finding(policy, "prototype iteration policy missing or too thin"))
        text = ""
    else:
        text = read(policy)
    if text and PLACEHOLDER_RE.search(text):
        findings.append(finding(policy, "policy contains placeholders/TODOs"))
    decision = field(text, "decision")
    trigger_raw = field(text, "structural_restart_trigger")
    trigger = trigger_raw or ""
    if decision not in DECISIONS:
        findings.append(finding(policy, "decision must be one of optimize_existing|fresh_lane|restart_from_foundation"))
    if not trigger_raw:
        findings.append(finding(policy, "structural_restart_trigger is required and must be explicit"))
    elif trigger not in STRUCTURAL_TRIGGERS:
        findings.append(finding(policy, "structural_restart_trigger must be one of: " + ", ".join(sorted(STRUCTURAL_TRIGGERS))))
    previous, previous_err = resolve_artifact(wf, field(text, "previous_prototype"))
    candidate, candidate_err = resolve_artifact(wf, field(text, "candidate_prototype"))
    if previous_err:
        findings.append(finding(policy, previous_err))
    if candidate_err:
        findings.append(finding(policy, candidate_err))
    if decision in {"optimize_existing", "fresh_lane"}:
        if not previous or not previous.exists() or previous.stat().st_size < 120:
            findings.append(finding(policy, "optimize/fresh_lane requires an existing previous_prototype under workflow"))
    if candidate and candidate.exists() and candidate.stat().st_size < 120:
        findings.append(finding(candidate, "candidate_prototype too thin"))
    for title, minimum in [
        ("Foundation constraints to carry forward", 5),
        ("Must preserve from previous prototype", 3),
        ("Must change in this iteration", 3),
    ]:
        if len(concrete_bullets(section(text, title))) < minimum:
            findings.append(finding(policy, f"{title} requires at least {minimum} concrete bullets"))
    learned = section(text, "Reusable constraints learned")
    for marker in ["New general rule learned", "Where it should be encoded", "How future iterations will avoid"]:
        if marker not in learned:
            findings.append(finding(policy, f"reusable constraints section missing: {marker}"))
    regression = section(text, "Regression checklist")
    for marker in [
        "Existing product baseline rechecked",
        "API/backend feasibility rechecked",
        "Product UI language boundary rechecked",
        "Prototype coverage delta written",
        "Previous accepted strengths preserved",
    ]:
        m = re.search(rf"{re.escape(marker)}:\s*(.+)", regression)
        if not m or m.group(1).strip().lower() not in {"yes", "pass", "done", "complete"}:
            findings.append(finding(policy, f"regression checklist item must be yes/pass/done/complete: {marker}"))
    decision_context = "\n".join([section(text, "Feedback summary"), section(text, "Decision rules")]).lower()
    structural_patterns = [
        r"product goal\s+(changed|invalid|wrong)",
        r"target user\s+(changed|invalid|wrong)",
        r"(existing\s+)?ia\s+(is\s+)?(wrong|invalid|broken)",
        r"core flow\s+(is\s+)?(wrong|invalid|broken)",
        r"baseline\s+(was\s+)?(wrong|invalid|incomplete)",
        r"backend\s*/?\s*api feasibility\s+(changed|invalid|wrong)",
        r"api feasibility\s+(changed|invalid|wrong)",
        r"direction\s+(is\s+)?(structurally wrong|rejected)",
        r"foundation\s+(is\s+)?(invalid|wrong)",
    ]
    structural_language_present = any(re.search(p, decision_context) for p in structural_patterns)
    if decision == "restart_from_foundation" and trigger not in STRUCTURAL_NON_NONE:
        findings.append(finding(policy, "restart_from_foundation requires explicit non-none structural_restart_trigger"))
    if decision in {"optimize_existing", "fresh_lane"} and trigger != "none":
        findings.append(finding(policy, "optimize_existing/fresh_lane must use structural_restart_trigger: none"))
    if decision in {"optimize_existing", "fresh_lane"} and structural_language_present:
        findings.append(finding(policy, "structural foundation change cannot be handled as optimize_existing/fresh_lane"))
    result = {
        "status": "PASS" if not findings else "FAIL",
        "workflow": str(wf),
        "policy": str(policy),
        "decision": decision or "UNKNOWN",
        "structural_restart_trigger": trigger,
        "findings": findings,
    }
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Decide whether prototype feedback should optimize an existing prototype, create a fresh lane, or restart from foundation.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--policy", default="PROTOTYPE_ITERATION_POLICY.md")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()
    result = check_policy(Path(args.root).resolve(), args.workflow, args.policy)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']} decision={result.get('decision','UNKNOWN')}")
        for f in result.get("findings", []):
            print(f"ERROR: {f['path']}: {f['message']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
