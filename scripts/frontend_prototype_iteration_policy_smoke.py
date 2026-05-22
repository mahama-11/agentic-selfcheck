#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

PREV = "<html><body><main><h1>Product Center</h1><section>Existing shell, product list, visual workbench, export readiness.</section></main></body></html>"
CAND = "<html><body><main><h1>Product Center</h1><section>Existing shell, product list, clearer visual workbench, export readiness, better empty/error states and preserved navigation.</section></main></body></html>"

GOOD_OPTIMIZE = """# Prototype Iteration Policy

## Decision
iteration_id: iteration-002
decision: optimize_existing
structural_restart_trigger: none
allowed_decisions: optimize_existing | fresh_lane | restart_from_foundation
previous_prototype: prototype-artifacts/previous.html
candidate_prototype: prototype-artifacts/candidate.html

## Feedback summary
Human/product feedback: visual hierarchy is weak, but core product flow and direction are acceptable.
Objective issue observed: product cards, generation status, and export readiness compete for attention.
Root cause category: local hierarchy and state clarity issue.
Why this is not just a cosmetic preference: it affects task completion and review confidence.

## Decision rules
The goal, target user, existing IA, backend feasibility, and route shell remain valid, so this is an optimize_existing pass.

## Foundation constraints to carry forward
- Project/background constraint: existing commerce operations workflow remains product intake -> visual workbench -> export.
- Existing route/shell constraint: preserve Ecommerce authenticated shell and product detail route.
- Visual/style constraint: preserve dark operations theme with blue/violet accents.
- Backend/API feasibility constraint: visual refinement callback remains internally marked as contract-needed only.
- Requirement trace constraint: product list, visual status, asset saveback, export handoff, and error recovery remain covered.

## Must preserve from previous prototype
- Preserve authenticated Ecommerce shell and route context.
- Preserve product list to detail navigation.
- Preserve visual workflow pending/success/error state representation.

## Must change in this iteration
- Improve visual hierarchy between product metadata and actions.
- Clarify generation progress and retry affordance.
- Add stronger empty/error state guidance without internal wording.

## Reusable constraints learned
- New general rule learned from this feedback: feedback about weak hierarchy should become a reusable visual hierarchy constraint, not a one-off patch.
- Where it should be encoded: workflow artifact and future visual critique checklist.
- How future iterations will avoid repeating the same issue: carry this hierarchy rule into every later prototype policy and critique.

## Regression checklist
- Existing product baseline rechecked: yes
- API/backend feasibility rechecked: yes
- Product UI language boundary rechecked: yes
- Prototype coverage delta written: yes
- Previous accepted strengths preserved: yes
"""

BAD_PLACEHOLDER = GOOD_OPTIMIZE.replace("iteration-002", "iteration-001").replace("yes", "TODO", 1)
BAD_RESTART = GOOD_OPTIMIZE.replace("decision: optimize_existing", "decision: restart_from_foundation").replace("The goal, target user, existing IA, backend feasibility, and route shell remain valid, so this is an optimize_existing pass.", "Restart because the button color feels off.")
BAD_NEGATED_RESTART = GOOD_OPTIMIZE.replace("decision: optimize_existing", "decision: restart_from_foundation").replace("The goal, target user, existing IA, backend feasibility, and route shell remain valid, so this is an optimize_existing pass.", "No product goal changed. The target user remains unchanged, existing IA remains valid, baseline remains valid, and backend feasibility remains valid; only button color feels off.")
BAD_OPT_IA = GOOD_OPTIMIZE.replace("The goal, target user, existing IA, backend feasibility, and route shell remain valid, so this is an optimize_existing pass.", "The existing IA or core flow is wrong, but continue optimizing existing.")
BAD_MISSING_TRIGGER = GOOD_OPTIMIZE.replace("structural_restart_trigger: none\n", "")
BAD_NEGATED_IA = GOOD_OPTIMIZE.replace("The goal, target user, existing IA, backend feasibility, and route shell remain valid, so this is an optimize_existing pass.", "Target user unchanged, but existing IA or core flow is wrong; continue optimizing existing anyway.")
BAD_THIN = "decision: optimize_existing\n"
GOOD_RESTART = GOOD_OPTIMIZE.replace("decision: optimize_existing", "decision: restart_from_foundation").replace("structural_restart_trigger: none", "structural_restart_trigger: product_goal_changed").replace("The goal, target user, existing IA, backend feasibility, and route shell remain valid, so this is an optimize_existing pass.", "Restart trigger: product goal changed materially and backend API feasibility changed materially after intake correction.")
BAD_ESCAPE = GOOD_RESTART.replace("previous_prototype: prototype-artifacts/previous.html", "previous_prototype: /tmp/outside-prev.html").replace("candidate_prototype: prototype-artifacts/candidate.html", "candidate_prototype: ../outside-candidate.html")


def make(root: Path, name: str, policy: str, with_prev: bool = True) -> Path:
    wf = root / ".hermes/workflows" / name
    if wf.exists(): shutil.rmtree(wf)
    (wf / "prototype-artifacts").mkdir(parents=True)
    if with_prev:
        (wf / "prototype-artifacts/previous.html").write_text(PREV, encoding="utf-8")
    (wf / "prototype-artifacts/candidate.html").write_text(CAND, encoding="utf-8")
    (wf / "PROTOTYPE_ITERATION_POLICY.md").write_text(policy, encoding="utf-8")
    return wf


def run(root: Path, wf: Path, should_pass: bool, case: str) -> dict:
    cp = subprocess.run(["scripts/frontend_prototype_iteration_policy_gate.py", "--root", ".", "--workflow", str(wf), "--format", "json"], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    passed = cp.returncode == 0
    no_traceback = "Traceback" not in cp.stdout and "Traceback" not in cp.stderr
    return {"case": case, "expected": "PASS" if should_pass else "FAIL", "actual": "PASS" if passed else "FAIL", "ok": passed == should_pass and no_traceback, "returncode": cp.returncode, "stdout": cp.stdout[-1800:], "stderr": cp.stderr[-1200:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    cases = [
        run(root, make(root, "frontend-prototype-iteration-policy-smoke-good-optimize", GOOD_OPTIMIZE), True, "good-optimize-existing"),
        run(root, make(root, "frontend-prototype-iteration-policy-smoke-good-restart", GOOD_RESTART), True, "good-restart-with-structural-trigger"),
        run(root, make(root, "frontend-prototype-iteration-policy-smoke-placeholder", BAD_PLACEHOLDER), False, "bad-placeholder-regression-checklist"),
        run(root, make(root, "frontend-prototype-iteration-policy-smoke-restart-no-trigger", BAD_RESTART), False, "bad-restart-without-explicit-structural-trigger"),
        run(root, make(root, "frontend-prototype-iteration-policy-smoke-negated-restart", BAD_NEGATED_RESTART), False, "bad-negated-restart-trigger"),
        run(root, make(root, "frontend-prototype-iteration-policy-smoke-missing-trigger", BAD_MISSING_TRIGGER), False, "bad-missing-structural-trigger-field"),
        run(root, make(root, "frontend-prototype-iteration-policy-smoke-optimize-ia-wrong", BAD_OPT_IA), False, "bad-optimize-despite-ia-or-core-flow-wrong"),
        run(root, make(root, "frontend-prototype-iteration-policy-smoke-negated-ia", BAD_NEGATED_IA), False, "bad-negated-other-field-does-not-mask-ia-wrong"),
        run(root, make(root, "frontend-prototype-iteration-policy-smoke-escape", BAD_ESCAPE), False, "bad-artifact-path-escape"),
        run(root, make(root, "frontend-prototype-iteration-policy-smoke-thin", BAD_THIN), False, "bad-thin-policy"),
        run(root, make(root, "frontend-prototype-iteration-policy-smoke-missing-prev", GOOD_OPTIMIZE, with_prev=False), False, "bad-missing-previous-for-optimize"),
    ]
    ok = all(c["ok"] for c in cases)
    payload = {"status": "PASS" if ok else "FAIL", "cases": cases}
    if args.format == "json": print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("status=" + payload["status"])
        for c in cases: print(f"{c['case']}: expected {c['expected']} actual {c['actual']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
