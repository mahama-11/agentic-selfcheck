# 02 Architecture — frontend-prototype-parity-gate

Status: PASS

## Artifacts
- `schemas/frontend-parity-report.schema.json` defines the strict report contract with `additionalProperties: false`, score bounds, coverage/comparison structures, deviations, non-visual contract exceptions, and approval.
- `scripts/frontend_prototype_parity_gate.py` validates base artifacts and workflow evidence.
- `scripts/frontend_prototype_parity_smoke.py` creates deterministic PASS/FAIL fixtures under `.hermes/workflows/frontend-prototype-parity-smoke/`.
- `templates/frontend/prototype-parity/PARITY_REPORT.md` documents report generation.
- `features/frontend-prototype-parity-gate.yaml` and `verifiers/frontend-prototype-parity-gate.yaml` wire the gate into SelfCheck.

## Gate model
The gate is structured rather than CV-diff based for this tranche. It compares frozen prototype screenshots from `prototype-freeze.json` against production screenshots referenced by the parity report. Every frozen prototype screen must be represented in both `coverage[]` and `comparisons[]`.

## Fail-closed controls
- Prototype freeze evidence path must resolve inside the workflow and be named `prototype-freeze.json`.
- Production screenshots must resolve inside `production-screenshots/` and pass strict PNG chunk/CRC/zlib/scanline validation.
- Prototype screenshots must resolve inside `prototype-screenshots/` or `frozen-prototype/` and match the freeze report screen mapping.
- Scores must be within threshold..100, default threshold >= 80.
- D-risk top-level approval must be `human_approved`; D-risk material deviations also require `human_approved`.
- Contract-needed exceptions must be explicit, approved, and `visual_parity_scope: false`.
