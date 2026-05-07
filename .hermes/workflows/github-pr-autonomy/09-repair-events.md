# Repair Events: GitHub PR Autonomy

Status: CLOSED

## Repair 1

Blocked by: Spec Reviewer, Quality/Security Reviewer

Issues:
- Unknown GitHub PR action ignored despite policy `unknown_action: blocked`.
- Dispatcher emitted states not consistently declared in policy/terminal state set.
- Repair policy was not enforced by dispatcher.
- Missing changed-file snapshot could be treated as low risk.
- Event route did not attach PR autonomy dispatcher decision.

Fixes:
- Enforced `defaults.unknown_action`.
- Added `WAITING_FOR_AUTHOR` state and `READY_FOR_HUMAN` terminal state.
- Added missing changed-file snapshot -> `NEEDS_HUMAN`.
- Added bounded repair checks: attempt limit, allowed globs, denied globs, high-risk guard.
- Attached `pr_autonomy_decision` to `selfcheck trigger` route reports for `github-pr-autonomy`.
- Expanded validator coverage.

Verification:
```bash
python3 -m compileall selfcheck scripts
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root .
python3 -m selfcheck run --root . --feature github-pr-autonomy --groups static --timeout 300
python3 -m selfcheck run --root . --feature github-pr-autonomy --groups evidence --timeout 300
python3 -m selfcheck trigger --root . --event github.pull_request --route github-pr-autonomy --source local --payload-file /tmp/github-pr-event.json --dry-run
python3 -m selfcheck trigger --root . --event github.pull_request --route github-pr-autonomy --source local --payload-file /tmp/github-pr-event.json --timeout 300
```

Result: PASS
