# QA Report

Role: QA

## Commands

```bash
python3 -m py_compile scripts/frontend_quality_gate.py scripts/frontend_quality_gate_smoke.py
scripts/frontend_quality_gate_smoke.py --root . --format text
python3 -m selfcheck validate --root .
python3 -m selfcheck run --root . --feature frontend-prototype-gate --groups static --timeout 120
```

## Result

PASS.

## Smoke coverage

- `good-complete-coverage`: expected PASS, actual PASS.
- `bad-missing-coverage`: expected FAIL, actual FAIL.
- `bad-placeholder-coverage`: expected FAIL, actual FAIL.
- `bad-no-complete-coverage-row`: expected FAIL, actual FAIL.
- `bad-blocked-core-coverage`: expected FAIL, actual FAIL.
- `bad-incomplete-extra-row`: expected FAIL, actual FAIL.
- `bad-missing-row-screenshot`: expected FAIL, actual FAIL.
- `bad-coverage-path-traversal`: expected FAIL, actual FAIL.

## Final verifier

`frontend-high-fidelity-prototype-gate` PASS via SelfCheck static run.
