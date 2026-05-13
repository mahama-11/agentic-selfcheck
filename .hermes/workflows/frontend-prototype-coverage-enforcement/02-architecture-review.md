# Architecture Review

Role: Architect

## Decision

Reuse the existing high-fidelity prototype gate and extend it with a coverage artifact. Do not create a separate prototype-completeness system.

## Layering

- Template layer: `templates/frontend/high-fidelity-prototype-gate/PROTOTYPE_COVERAGE.md`
- Gate layer: `scripts/frontend_quality_gate.py`
- Regression/smoke layer: `scripts/frontend_quality_gate_smoke.py`
- SelfCheck verifier layer: `verifiers/frontend-high-fidelity-prototype-gate.yaml`
- Feature contract: `features/frontend-prototype-gate.yaml`

## Why this is right

The existing frontend quality loop already owns prototype acceptance. Completeness is a dimension of prototype acceptance, so it belongs inside the same gate rather than a new workflow.

## Risks

- Current coverage check is structural, not visual-semantic. It catches missing/TODO/blocked coverage but does not yet prove screenshots visually match every surface.
- Next hardening should add route/screenshot existence validation against each coverage row.
