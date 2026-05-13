# Architecture: frontend-prototype-freeze

Artifacts added:
- `templates/frontend/prototype-freeze/` handoff templates.
- `schemas/frontend-prototype-freeze.schema.json` strict payload contract.
- `scripts/frontend_prototype_freeze_gate.py` validation gate with base/workflow modes and optional artifact writing.
- `scripts/frontend_prototype_freeze_smoke.py` deterministic pass/fail fixture generator and verifier driver.
- Feature and verifier YAML wiring for selfcheck.

The gate is intentionally independent from `frontend_quality_gate.py`; the existing quality gate only reports freeze readiness when a payload is present and does not require freeze for prototype acceptance.
