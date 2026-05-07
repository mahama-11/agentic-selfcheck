# Spec Review Report: GitHub PR Autonomy

Role: Spec Reviewer

## Initial verdict
REQUEST_CHANGES

## Initial blockers
1. `defaults.unknown_action: blocked` was not honored; unsupported actions returned `IGNORED`.
2. Dispatcher emitted `WAITING_FOR_AUTHOR` and `READY_FOR_HUMAN` without a fully consistent policy/terminal-state declaration.
3. Representative coverage did not assert draft PR, disallowed base, missing/pending checks, large diff, medium risk, repair-enabled path, or terminal state membership.

## Repair applied
- Unknown action now respects `defaults.unknown_action`.
- `WAITING_FOR_AUTHOR` is declared in policy states.
- `READY_FOR_HUMAN` is declared as a terminal state.
- Missing changed-file snapshot now routes to `NEEDS_HUMAN`.
- Validator now asserts:
  - unknown repo
  - unknown action
  - draft PR
  - disallowed base branch
  - missing changed-file snapshot
  - missing/pending checks
  - high-risk workflow file
  - large diff high-risk
  - medium risk
  - failed checks with repair disabled
  - repair enabled/denied/exhausted paths
  - state/terminal-state membership
  - merge disabled everywhere
  - no live merge action

## Re-review verdict
APPROVE

## Evidence
```bash
python3 scripts/github_pr_autonomy_policy_validate.py --root . --policy github-pr-autonomy-v-workspace
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root .
python3 -m selfcheck run --root . --feature github-pr-autonomy --groups static --timeout 300
python3 -m selfcheck run --root . --feature github-pr-autonomy --groups evidence --timeout 300
python3 -m selfcheck trigger --root . --event github.pull_request --route github-pr-autonomy --source local --payload-file /tmp/github-pr-event.json --dry-run
python3 -m selfcheck trigger --root . --event github.pull_request --route github-pr-autonomy --source local --payload-file /tmp/github-pr-event.json --timeout 300
```

Result: PASS.
