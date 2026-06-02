#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REQUIRED_TEMPLATE = Path("templates/frontend/prototype-foundation-ledger/PROTOTYPE_FOUNDATION_LEDGER.md")
PLACEHOLDER_RE = re.compile(r"\b(TODO|TBD|placeholder|Fill|foundation-001|iteration-001)\b|待补|填写", re.I)
YES = {"yes", "pass", "done", "complete"}


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
        raise ValueError("workflow and foundation artifacts must not be symlinked")
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
    out: list[str] = []
    for line in block.splitlines():
        s = line.strip()
        if not s.startswith("-"):
            continue
        item = s[1:].strip()
        if not item or PLACEHOLDER_RE.search(item):
            continue
        if item.endswith(":") or (":" in item and not item.split(":", 1)[1].strip()):
            continue
        out.append(item)
    return out


def lesson_bullets_have_schema(block: str) -> bool:
    bullets = concrete_bullets(block)
    if len(bullets) < 3:
        return False
    return all(all(marker in b for marker in ["Pattern:", "Root cause:", "System rule:", "Verification:"]) for b in bullets)


def check_ledger(root: Path, workflow_raw: str, ledger_rel: str, policy_rel: str) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    if not (root / REQUIRED_TEMPLATE).exists():
        findings.append(finding(root / REQUIRED_TEMPLATE, "required prototype foundation ledger template missing"))
    try:
        wf = resolve_workflow(root, workflow_raw)
    except ValueError as exc:
        return {"status": "FAIL", "findings": [finding(workflow_raw, str(exc))]}

    ledger = wf / ledger_rel
    ledger_ok = True
    try:
        ledger.resolve().relative_to(wf.resolve())
    except Exception:
        findings.append(finding(ledger, "foundation ledger must stay under workflow"))
        ledger_ok = False
    if not ledger_ok:
        text = ""
    elif not ledger.exists() or ledger.stat().st_size < 900:
        findings.append(finding(ledger, "prototype foundation ledger missing or too thin"))
        text = ""
    else:
        text = read(ledger)
    if text and PLACEHOLDER_RE.search(text):
        findings.append(finding(ledger, "foundation ledger contains placeholders/TODOs or unadvanced initial ids"))

    for key in ["foundation_id", "current_foundation_version", "foundation_status", "last_feedback_iteration", "source_of_truth"]:
        if not field(text, key):
            findings.append(finding(ledger, f"missing required field: {key}"))
    if field(text, "foundation_status") not in {"active", "restarted", "superseded"}:
        findings.append(finding(ledger, "foundation_status must be active|restarted|superseded"))

    required_sections = [
        ("Product context", 5),
        ("Prototype goal", 5),
        ("Current product baseline", 5),
        ("API/backend/data constraints", 5),
        ("Prototype skeleton", 5),
        ("Foundation constraints to preserve", 6),
        ("Accepted strengths to carry forward", 3),
        ("Rejected patterns", 3),
        ("Reusable lessons learned", 3),
    ]
    for title, minimum in required_sections:
        if len(concrete_bullets(section(text, title))) < minimum:
            findings.append(finding(ledger, f"{title} requires at least {minimum} concrete bullets"))

    lessons = section(text, "Reusable lessons learned")
    if not lesson_bullets_have_schema(lessons):
        findings.append(finding(ledger, "each reusable lesson bullet must encode Pattern, Root cause, System rule, and Verification"))

    regression = section(text, "Regression checklist")
    for marker in [
        "Existing product baseline preserved",
        "Backend/API feasibility boundary preserved",
        "Product UI language boundary preserved",
        "Accepted strengths preserved",
        "Rejected patterns avoided",
        "New feedback converted into reusable rule or explicit non-rule",
    ]:
        m = re.search(rf"{re.escape(marker)}:\s*(.+)", regression)
        if not m or m.group(1).strip().lower() not in YES:
            findings.append(finding(ledger, f"regression checklist item must be yes/pass/done/complete: {marker}"))

    policy = wf / policy_rel
    policy_ok = True
    try:
        policy.resolve().relative_to(wf.resolve())
    except Exception:
        findings.append(finding(policy, "prototype iteration policy must stay under workflow"))
        policy_ok = False
    ptext = read(policy) if policy_ok else ""
    if policy_ok and policy.exists():
        policy_carry = section(ptext, "Foundation constraints to carry forward")
        if policy_carry and len(concrete_bullets(policy_carry)) >= 3:
            ledger_constraints = section(text, "Foundation constraints to preserve")
            hits = 0
            for token in ["product", "route", "backend", "language", "visual", "requirement"]:
                if token in policy_carry.lower() and token in ledger_constraints.lower():
                    hits += 1
            if hits < 3:
                findings.append(finding(ledger, "foundation ledger does not visibly carry forward iteration-policy constraints"))
        if "restart_from_foundation" in ptext and field(ptext, "structural_restart_trigger") != "none":
            if field(text, "foundation_status") != "restarted":
                findings.append(finding(ledger, "restart_from_foundation requires foundation_status: restarted and updated foundation"))
    elif policy_ok:
        findings.append(finding(policy, "prototype iteration policy missing; foundation must be checked together with iteration policy"))

    return {
        "status": "PASS" if not findings else "FAIL",
        "workflow": str(wf),
        "ledger": str(ledger),
        "foundation_id": field(text, "foundation_id") or "UNKNOWN",
        "current_foundation_version": field(text, "current_foundation_version") or "UNKNOWN",
        "foundation_status": field(text, "foundation_status") or "UNKNOWN",
        "findings": findings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Require a growing prototype foundation ledger before/after prototype iteration.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--ledger", default="PROTOTYPE_FOUNDATION_LEDGER.md")
    ap.add_argument("--policy", default="PROTOTYPE_ITERATION_POLICY.md")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()
    result = check_ledger(Path(args.root).resolve(), args.workflow, args.ledger, args.policy)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']} foundation={result.get('foundation_id','UNKNOWN')} state={result.get('foundation_status','UNKNOWN')}")
        for f in result.get("findings", []):
            print(f"ERROR: {f['path']}: {f['message']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
