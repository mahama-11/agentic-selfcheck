# Developer Summary: GitHub PR Autonomy

Role: Developer

## Implemented
- Added generic PR autonomy policy schema: `schemas/pr-autonomy-policy.schema.json`.
- Added V workspace policy instance: `pr-autonomy-policies/github-pr-autonomy-v-workspace.yaml`.
- Added deterministic dispatcher module: `selfcheck/pr_autonomy.py`.
- Registered `pr_autonomy_policy` in SelfCheck validation registry.
- Added safe static harness execution for scripts under `scripts/`.
- Added policy validator/dry-run representative transitions: `scripts/github_pr_autonomy_policy_validate.py`.
- Added feature, verifier, event route, and docs:
  - `features/github-pr-autonomy.yaml`
  - `verifiers/github-pr-autonomy-policy-validate.yaml`
  - `events/github-pr-autonomy.yaml`
  - `docs/github-pr-autonomy.md`

## Key behavior
- Unknown repo -> `IGNORED`.
- High-risk file changes -> `NEEDS_HUMAN`.
- Failed required checks with repair disabled -> `BLOCKED`.
- Clean required checks with auto-merge disabled -> `READY_FOR_HUMAN`.
- Auto-merge remains disabled and no live GitHub actions are performed.

## Validation run
```bash
python3 -m compileall selfcheck scripts
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root .
python3 -m selfcheck run --root . --feature github-pr-autonomy --groups static --timeout 300
python3 -m selfcheck run --root . --feature github-pr-autonomy --groups evidence --timeout 300
```

Result: PASS.

## Evidence
- `reports/github-pr-autonomy/github-pr-autonomy-policy-validate.json`
- `reports/github-pr-autonomy/evidence-gate.json`
