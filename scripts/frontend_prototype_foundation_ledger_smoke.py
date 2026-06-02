#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

PREV = "<html><body><main><h1>Product Center</h1><section>Existing shell and visual workbench.</section></main></body></html>"
CAND = "<html><body><main><h1>Product Center</h1><section>Improved shell and visual workbench.</section></main></body></html>"
POLICY = """# Prototype Iteration Policy

## Decision
iteration_id: iteration-003
decision: optimize_existing
structural_restart_trigger: none
previous_prototype: prototype-artifacts/previous.html
candidate_prototype: prototype-artifacts/candidate.html

## Feedback summary
Human feedback: preserve the current product skeleton and improve hierarchy.

## Decision rules
The product goal, target user, route skeleton, and backend feasibility remain valid.

## Foundation constraints to carry forward
- Project/background constraint: commerce operations workflow remains intake to visual workbench to export.
- Existing route/shell constraint: preserve authenticated Ecommerce shell and product detail route.
- Visual/style constraint: preserve dark operations theme with blue/violet accents.
- Backend/API feasibility constraint: visual refinement callback remains contract-needed only.
- Requirement trace constraint: product list, visual status, asset saveback, export handoff, and error recovery remain covered.

## Must preserve from previous prototype
- Preserve authenticated Ecommerce shell and route context.
- Preserve product list to detail navigation.
- Preserve visual workflow state representation.

## Must change in this iteration
- Improve visual hierarchy.
- Clarify generation progress.
- Strengthen empty/error state guidance.

## Reusable constraints learned
- New general rule learned from this feedback: hierarchy feedback becomes a reusable constraint.
- Where it should be encoded: foundation ledger and future visual critique checklist.
- How future iterations will avoid repeating the same issue: carry hierarchy rule into later policies.

## Regression checklist
- Existing product baseline rechecked: yes
- API/backend feasibility rechecked: yes
- Product UI language boundary rechecked: yes
- Prototype coverage delta written: yes
- Previous accepted strengths preserved: yes
"""
GOOD_LEDGER = """# Prototype Foundation Ledger
foundation_id: foundation-003
current_foundation_version: foundation-003
foundation_status: active
last_feedback_iteration: iteration-003
source_of_truth: EXISTING_PRODUCT_BASELINE.md, API_BACKEND_FEASIBILITY_MAP.md, PROTOTYPE_REQUIREMENT_TRACE.md, PROTOTYPE_ITERATION_POLICY.md

## Product context
- Product/background: Agent Ecommerce product operations console for SKU creation and visual production.
- Target user: merchant operations user managing product assets and listing readiness.
- Current product stage: existing authenticated product center with backend-backed products and assets.
- Business workflow: intake product data, inspect visual workflow status, refine assets, export listing material.
- Success metric or review goal: reviewer can understand next action and readiness without internal governance terms.

## Prototype goal
- Primary job-to-be-done: make SKU visual production status and next actions clear.
- Target surface/routes: Ecommerce Product Center and Product Detail route family.
- Core user journey: list product, enter detail, review visual status, retry or save generated asset, export.
- Out of scope: provider execution controls not supported by current backend remain out of scope.
- Human acceptance focus: product direction, hierarchy, route flow, and honest feasibility boundary.

## Current product baseline
- Existing route/page shell: authenticated Ecommerce shell and product detail route are preserved.
- Existing components or design system: dark operations cards, navigation shell, product list/detail primitives.
- Current visual language: dense professional operations UI with blue/violet accents.
- Current interaction model: list to detail to workflow stations with explicit state transitions.
- Current screenshots/evidence: baseline screenshots are stored under workflow evidence and linked from intake.

## API/backend/data constraints
- Existing supported API/backend capability: product list/detail and asset/source relations are supported.
- Missing capability marked contract-needed: advanced inpaint/refinement provider execution remains contract-needed.
- Data ownership/source: Ecommerce owns SKU semantics; Platform owns shared runtime/provider capability.
- Runtime/state constraint: generation callbacks are server-owned and cannot be faked from frontend.
- Feasibility risk: every visible action must map to existing API or contract-needed boundary.

## Prototype skeleton
- Information architecture: Product Center overview leads to SKU Detail and station-specific workflow regions.
- Primary pages/regions: queue/list, detail summary, visual workbench, listing/export readiness.
- Critical states: empty, loading, processing, succeeded, failed, contract-needed, permission denied.
- Main interactions: select SKU, inspect status, retry supported action, save asset, export package.
- Route choreography: queue to detail to station pages with preserved global Ecommerce escape.

## Foundation constraints to preserve
- Preserve product context: commerce operations workflow remains intake to visual workbench to export.
- Preserve route/page skeleton: preserve authenticated Ecommerce shell and product detail route.
- Preserve backend/API feasibility boundary: visual refinement callback remains contract-needed only.
- Preserve user-facing language boundary: no internal gate, coverage, provider-debug, or workflow-control terms in UI.
- Preserve visual/interaction principle: dark operations theme with blue/violet accents and clear hierarchy.
- Preserve requirement trace: product list, visual status, asset saveback, export handoff, and error recovery remain covered.

## Accepted strengths to carry forward
- Strength 1: authenticated shell keeps the prototype grounded in existing product context.
- Strength 2: list-to-detail navigation keeps the user's primary workflow understandable.
- Strength 3: visual workflow status makes generation readiness visible without fake success.

## Rejected patterns
- Rejected pattern 1: static dashboard cards without route or action closure.
- Rejected pattern 2: showing internal governance words to product users.
- Rejected pattern 3: pretending missing backend/provider capability is available.

## Reusable lessons learned
- Pattern: weak visual hierarchy | Root cause: product metadata and actions compete | System rule: primary action and readiness state must dominate first screen | Verification: visual critique checks first-screen hierarchy.
- Pattern: fake capability wording | Root cause: frontend hides backend feasibility gaps | System rule: unsupported capabilities use user-facing unavailable wording and contract-needed evidence | Verification: feasibility map and UI language scan.
- Pattern: route-detached prototype | Root cause: design starts from blank canvas | System rule: prototype must preserve route shell and existing navigation context | Verification: baseline and route skeleton checks.

## Regression checklist
- Existing product baseline preserved: yes
- Backend/API feasibility boundary preserved: yes
- Product UI language boundary preserved: yes
- Accepted strengths preserved: yes
- Rejected patterns avoided: yes
- New feedback converted into reusable rule or explicit non-rule: yes
"""
BAD_PLACEHOLDER = GOOD_LEDGER.replace("foundation-003", "foundation-001")
BAD_THIN = "foundation_status: active\n"
BAD_NO_LESSON_RULE = GOOD_LEDGER.replace("System rule:", "Advice:")
BAD_REGRESSION = GOOD_LEDGER.replace("Rejected patterns avoided: yes", "Rejected patterns avoided: TODO")
BAD_MISMATCH = GOOD_LEDGER.replace("- Preserve product context: commerce operations workflow remains intake to visual workbench to export.\n- Preserve route/page skeleton: preserve authenticated Ecommerce shell and product detail route.\n- Preserve backend/API feasibility boundary: visual refinement callback remains contract-needed only.\n- Preserve user-facing language boundary: no internal gate, coverage, provider-debug, or workflow-control terms in UI.\n- Preserve visual/interaction principle: dark operations theme with blue/violet accents and clear hierarchy.\n- Preserve requirement trace: product list, visual status, asset saveback, export handoff, and error recovery remain covered.", "- Preserve unrelated animation flourish: keep decorative sparkles.\n- Preserve unrelated mascot: keep a mascot illustration.\n- Preserve unrelated onboarding copy: keep tutorial slogans.\n- Preserve unrelated marketing rhythm: keep campaign banners.\n- Preserve unrelated keyboard shortcut: keep a command palette hint.\n- Preserve unrelated chart decoration: keep a background chart.")
BAD_ONE_LESSON_ONLY = GOOD_LEDGER.replace("- Pattern: fake capability wording | Root cause: frontend hides backend feasibility gaps | System rule: unsupported capabilities use user-facing unavailable wording and contract-needed evidence | Verification: feasibility map and UI language scan.\n- Pattern: route-detached prototype | Root cause: design starts from blank canvas | System rule: prototype must preserve route shell and existing navigation context | Verification: baseline and route skeleton checks.", "- Generic note: be more careful next time.\n- Generic note: polish the layout better.")


def make(root: Path, name: str, ledger: str, policy: str = POLICY) -> Path:
    wf = root / ".hermes/workflows" / name
    if wf.exists(): shutil.rmtree(wf)
    (wf / "prototype-artifacts").mkdir(parents=True)
    (wf / "prototype-artifacts/previous.html").write_text(PREV, encoding="utf-8")
    (wf / "prototype-artifacts/candidate.html").write_text(CAND, encoding="utf-8")
    (wf / "PROTOTYPE_ITERATION_POLICY.md").write_text(policy, encoding="utf-8")
    (wf / "PROTOTYPE_FOUNDATION_LEDGER.md").write_text(ledger, encoding="utf-8")
    return wf


def run(root: Path, wf: Path, should_pass: bool, case: str, extra_args: list[str] | None = None) -> dict:
    cmd = ["scripts/frontend_prototype_foundation_ledger_gate.py", "--root", ".", "--workflow", str(wf), "--format", "json"]
    if extra_args:
        cmd.extend(extra_args)
    cp = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    passed = cp.returncode == 0
    no_traceback = "Traceback" not in cp.stdout and "Traceback" not in cp.stderr
    return {"case": case, "expected": "PASS" if should_pass else "FAIL", "actual": "PASS" if passed else "FAIL", "ok": passed == should_pass and no_traceback, "returncode": cp.returncode, "stdout": cp.stdout[-1800:], "stderr": cp.stderr[-1200:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    outside_policy = root.parent / "frontend-foundation-outside-policy-smoke.md"
    outside_policy.write_text(POLICY, encoding="utf-8")
    real_wf = make(root, "frontend-prototype-foundation-ledger-smoke-real-symlink-target", GOOD_LEDGER)
    alias = root / ".hermes/workflows/frontend-prototype-foundation-ledger-smoke-alias"
    if alias.exists() or alias.is_symlink():
        if alias.is_symlink(): alias.unlink()
        else: shutil.rmtree(alias)
    alias.symlink_to(real_wf.parent, target_is_directory=True)
    symlinked_child = alias / real_wf.name
    cases = [
        run(root, make(root, "frontend-prototype-foundation-ledger-smoke-good", GOOD_LEDGER), True, "good-foundation-ledger"),
        run(root, make(root, "frontend-prototype-foundation-ledger-smoke-placeholder", BAD_PLACEHOLDER), False, "bad-placeholder-foundation"),
        run(root, make(root, "frontend-prototype-foundation-ledger-smoke-thin", BAD_THIN), False, "bad-thin-ledger"),
        run(root, make(root, "frontend-prototype-foundation-ledger-smoke-no-rule", BAD_NO_LESSON_RULE), False, "bad-no-system-rule"),
        run(root, make(root, "frontend-prototype-foundation-ledger-smoke-one-lesson-only", BAD_ONE_LESSON_ONLY), False, "bad-one-lesson-only"),
        run(root, make(root, "frontend-prototype-foundation-ledger-smoke-regression", BAD_REGRESSION), False, "bad-regression-checklist"),
        run(root, make(root, "frontend-prototype-foundation-ledger-smoke-mismatch", BAD_MISMATCH), False, "bad-ledger-policy-mismatch"),
        run(root, make(root, "frontend-prototype-foundation-ledger-smoke-outside-policy", GOOD_LEDGER), False, "bad-outside-policy-path", ["--policy", str(outside_policy)]),
        run(root, symlinked_child, False, "bad-symlinked-workflow-path-component"),
    ]
    if alias.is_symlink():
        alias.unlink()
    if outside_policy.exists():
        outside_policy.unlink()
    ok = all(c["ok"] for c in cases)
    payload = {"status": "PASS" if ok else "FAIL", "cases": cases}
    if args.format == "json": print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("status=" + payload["status"])
        for c in cases: print(f"{c['case']}: expected {c['expected']} actual {c['actual']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
