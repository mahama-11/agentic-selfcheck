# Prototype Iteration Policy

Use this file before generating the next prototype candidate.

## Decision

iteration_id: iteration-001
decision: optimize_existing
structural_restart_trigger: none
allowed_decisions: optimize_existing | fresh_lane | restart_from_foundation
previous_prototype: prototype-artifacts/previous.html
candidate_prototype: prototype-artifacts/candidate.html

## Feedback summary

Required:
- Human/product feedback:
- Objective issue observed:
- Root cause category:
- Why this is not just a cosmetic preference:

## Decision rules

Choose `optimize_existing` when:
- Core product goal remains valid.
- Existing IA/business flow remains valid.
- Existing prototype direction is acceptable or partially acceptable.
- Feedback is local: copy, spacing, emphasis, missing state, interaction clarity, specific visual refinement.

Choose `fresh_lane` when:
- The foundation is valid but the design direction/taste needs a materially different alternative.
- You need a parallel candidate while preserving the same project context, backend feasibility, and requirement trace.

Choose `restart_from_foundation` only when:
- Product goal changed materially.
- Target user/job changed materially.
- Existing IA or core flow is wrong.
- Existing project baseline/intake was wrong or incomplete.
- Backend/API feasibility assumption changed materially.
- User explicitly rejects the direction as structurally wrong, not merely needing polish.

## Foundation constraints to carry forward

Required list, at least 5 concrete constraints:
- Project/background constraint:
- Existing route/shell constraint:
- Visual/style constraint:
- Backend/API feasibility constraint:
- Requirement trace constraint:

## Must preserve from previous prototype

Required list, at least 3 concrete strengths that must not regress:
- Preserved strength 1:
- Preserved strength 2:
- Preserved strength 3:

## Must change in this iteration

Required list, at least 3 concrete changes:
- Change 1:
- Change 2:
- Change 3:

## Reusable constraints learned

Required:
- New general rule learned from this feedback:
- Where it should be encoded: workflow artifact / template / gate / skill / docs
- How future iterations will avoid repeating the same issue:

## Regression checklist

Required:
- Existing product baseline rechecked: TODO
- API/backend feasibility rechecked: TODO
- Product UI language boundary rechecked: TODO
- Prototype coverage delta written: TODO
- Previous accepted strengths preserved: TODO
