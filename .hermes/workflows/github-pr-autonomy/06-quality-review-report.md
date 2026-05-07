# Quality/Security Review Report: GitHub PR Autonomy

Role: Quality/Security Reviewer

## Initial verdict
REQUEST_CHANGES

## Initial blockers
1. Unknown action policy was not enforced.
2. Repair bounds and repair allow/deny globs were schema-only and not enforced by dispatcher.
3. Event route described PR autonomy but trigger did not include dispatcher decision.
4. Missing changed-file snapshots could be classified as low risk.
5. `READY_FOR_HUMAN` terminal behavior was inconsistent with policy terminal states.

## Repair applied
- Unknown action now maps through `defaults.unknown_action`.
- Dispatcher accepts `repair_attempts` and enforces:
  - min(default max attempts, repo max attempts)
  - denied glob block
  - all files must match allowed globs
  - high-risk files cannot be repair-dispatched
  - exhausted attempts -> `BLOCKED`
- Missing changed files -> `NEEDS_HUMAN`.
- `cmd_trigger` attaches `pr_autonomy_decision` for `github-pr-autonomy` route, both dry-run and live trigger modes.
- `READY_FOR_HUMAN` is explicitly terminal in schema/policy.
- Validator covers edge cases and no live merge action.

## Final verdict
APPROVE

## Security notes
- No webhook secret, GitHub token, private key, or credential is committed.
- Auto-merge remains disabled.
- Repair remains disabled in the V policy instance.
- Current actions are planned/advisory only; no GitHub live side effects are performed.
- High-risk and missing-file-snapshot cases require human decision.

## Evidence
- `reports/github-pr-autonomy/github-pr-autonomy-policy-validate.json`: PASS.
- `reports/github-pr-autonomy/evidence-gate.json`: PASS.
- `reports/events/github.pull_request-*.json`: trigger reports include PR autonomy decision.
