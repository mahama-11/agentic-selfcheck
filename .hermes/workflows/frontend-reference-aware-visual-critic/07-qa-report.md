# QA Report

Verdict: PASS

Commands:

```bash
python3 -m py_compile scripts/frontend_reference_aware_critic.py scripts/frontend_reference_aware_critic_smoke.py scripts/frontend_quality_gate.py
python3 scripts/frontend_reference_aware_critic.py --root . --workflow .hermes/workflows/frontend-reference-aware-critic-smoke/good-c --risk C --input-json .hermes/workflows/frontend-reference-aware-critic-smoke/good-c/reference-aware-input.json --write-artifacts --format json
python3 scripts/frontend_reference_aware_critic.py --root . --workflow .hermes/workflows/frontend-reference-aware-critic-smoke/good-d --risk D --input-json .hermes/workflows/frontend-reference-aware-critic-smoke/good-d/reference-aware-input.json --write-artifacts --format json
python3 scripts/frontend_reference_aware_critic_smoke.py --root . --format json
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root . --feature frontend-reference-aware-visual-critic --strict-missing
python3 -m selfcheck run --root . --feature frontend-reference-aware-visual-critic --groups static
```

Results:

- good-c: PASS and materialized artifacts.
- good-d: PASS and materialized artifacts.
- all negative cases: FAIL as expected.
- selfcheck validate/audit/run: PASS.

Evidence:

- `/tmp/frontend-reference-aware-critic/*`
- `reports/frontend-reference-aware-visual-critic/frontend-reference-aware-visual-critic-gate.json`
