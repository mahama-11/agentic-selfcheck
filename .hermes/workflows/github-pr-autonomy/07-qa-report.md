# QA Report: GitHub PR Autonomy

Role: QA

## Verdict
PASS

## Commands verified
```bash
python3 scripts/github_pr_autonomy_policy_validate.py --root . --policy github-pr-autonomy-v-workspace
python3 -m selfcheck run --root . --feature github-pr-autonomy --groups static --timeout 300
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root .
python3 -m selfcheck run --root . --feature github-pr-autonomy --groups evidence --timeout 300
python3 -m selfcheck trigger --root . --event github.pull_request --route github-pr-autonomy --source local --payload-file /tmp/github-pr-event.json --dry-run
python3 -m selfcheck trigger --root . --event github.pull_request --route github-pr-autonomy --source local --payload-file /tmp/github-pr-event.json --timeout 300
```

## Evidence
- `reports/github-pr-autonomy/github-pr-autonomy-policy-validate.json`: PASS.
- `reports/github-pr-autonomy/evidence-gate.json`: PASS.
- `reports/events/github.pull_request-*.json`: generated for dry-run and local trigger.
- Trigger reports include `routes[0].pr_autonomy_decision`.

## Behavior confirmed
- Unknown repo -> `IGNORED`.
- Unknown action -> `BLOCKED`.
- High-risk workflow change -> `NEEDS_HUMAN`.
- Failed checks with repair disabled -> `BLOCKED`.
- Clean checks with auto-merge disabled -> `READY_FOR_HUMAN`.
- No live merge action is emitted.
- Dry-run remains true in policy decision output.

## Notes
QA created only temporary payloads under `/tmp` and generated report artifacts under `reports/`.
