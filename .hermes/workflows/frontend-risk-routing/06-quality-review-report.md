# Quality Review

Role: Quality Reviewer

## Initial result

REQUEST_CHANGES.

## Issues found

1. Production frontend feature with missing explicit risk could pass.
2. C-risk production implementation feature without route policy could pass.
3. Frontend path detection missed Vue/Svelte/HTML/views/routes/templates style frontends.
4. `--feature-file` / `--task-json` could read outside `--root`.
5. Smoke did not cover these edge cases.

## Fixes applied

- Production frontend feature contracts must declare explicit risk.
- Non-generic production implementation text now triggers production-chain enforcement even if route policy is missing.
- Frontend path hints now include `.vue`, `.svelte`, `.html`, `src/views/`, `app/routes/`, `routes/`, and `templates/`.
- Input files must resolve under `--root`.
- Smoke now covers missing risk, missing route policy, Vue-style frontend path, and outside-root task JSON.

## Re-test

PASS:

```bash
python3 -m py_compile scripts/frontend_risk_router.py scripts/frontend_risk_routing_smoke.py
scripts/frontend_risk_routing_smoke.py --root . --format text
scripts/frontend_risk_router.py --root . --scan-features --format text
python3 -m selfcheck validate --root .
python3 -m selfcheck run --root . --feature frontend-risk-routing --groups static --timeout 120
```
