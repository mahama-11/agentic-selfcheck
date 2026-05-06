# QA Report

Role: QA
Conclusion: PASS_WITH_NOTES

Commands executed:
```bash
python3 -m selfcheck validate --root .
python3 -m selfcheck plan --root . --feature ecommerce-product-ai-pipeline
python3 -m selfcheck run --root . --feature ecommerce-product-ai-pipeline --groups static --timeout 300
```

Results:
- Governance validation: PASS.
- Plan resolved active worktree commands:
  - `cd /root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-frontend && pnpm exec tsc --noEmit`
  - `cd /root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-frontend && pnpm run build`
- `frontend-typecheck`: PASS, report `reports/ecommerce-product-ai-pipeline/frontend-typecheck.json`.
- `frontend-build`: PASS, report `reports/ecommerce-product-ai-pipeline/frontend-build.json`.

Guard checks:
```bash
python3 -m selfcheck run --root . --feature ecommerce-product-ai-pipeline --groups api --timeout 10
# SKIPPED api-smoke; treated as nonzero unless --allow-skipped is explicit.

python3 -m selfcheck audit --root . --feature ecommerce-product-ai-pipeline --strict-missing
# Missing required workflow evidence is ERROR/nonzero.
```

Notes:
- This is static verifier execution only. API/browser verifier wiring remains pending and must not be reported as PASS.
