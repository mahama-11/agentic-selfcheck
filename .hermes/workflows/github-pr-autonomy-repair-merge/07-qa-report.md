# QA Report: github-pr-autonomy-repair-merge

Role: QA
Status: PASS

## Scope
Validate live GitHub PR autonomy behavior for:
- automatic bounded repair push commit
- policy-gated automatic squash merge
- high-risk human gate
- cleanup of validation artifacts

## Environment
- Receiver: `agentic-selfcheck-github-webhook.service`
- Direct webhook endpoint: `http://115.190.171.176:8655/github-pr-autonomy`
- Runtime flags:
  - `GITHUB_PR_AUTONOMY_ALLOW_REPAIR=true`
  - `GITHUB_PR_AUTONOMY_ALLOW_MERGE=true`
- Policy: `github-pr-autonomy-v-workspace`

## Static validation
- `py_compile` for PR autonomy core, webhook server, reporter, repair executor, policy validator: PASS
- Policy validator after security fixes: PASS
  - `fork_pr_needs_human=true`
  - `repair_execution_disabled_blocks=true`
  - `repair_exhausted_blocked=true`
  - `live_merge_action_policy_gated=true`
- `selfcheck validate`: PASS
- `selfcheck audit`: PASS
- `git diff --check`: PASS

## Live PR: repair + auto-merge
PR: `https://github.com/mahama-11/platform-backend/pull/3`

Flow observed:
1. PR introduced a low-risk Go formatting failure.
2. CI `Go baseline checks` failed.
3. Webhook produced `NEEDS_REPAIR`.
4. Repair executor applied deterministic `gofmt` repair and pushed fix commit.
5. Head changed from `4a83e5bca37db33ea2ccb0b5d7dabab96db28e5f` to `8d151c9abd536990de9d90e701c361f506513735`.
6. CI reran and passed.
7. Webhook produced `READY_TO_MERGE` with `MERGE_PR`.
8. PR was squash-merged.

Evidence:
- PR state: `MERGED`
- Merge commit: `54066789f414cb07e005c952e093e15c89470d3b`
- Manual repair report: `reports/github-pr-autonomy-repair-merge/manual-repair-pr3.json`

## Live PR: post-security-fix auto-merge
PR: `https://github.com/mahama-11/platform-frontend/pull/4`

Flow observed:
1. Low-risk docs PR opened.
2. Webhook produced `WAITING_FOR_CHECKS`.
3. CI `Build` passed.
4. Webhook produced `READY_TO_MERGE` with `MERGE_PR`.
5. PR was squash-merged automatically.

Evidence:
- PR state: `MERGED`
- Merge commit: `b10c5ca4c04250cb13a578e3850890ac09a33d94`

## Live PR: cleanup auto-merge
PR: `https://github.com/mahama-11/platform-frontend/pull/5`

Flow observed:
1. Removed the temporary docs validation file.
2. CI `Build` passed.
3. Webhook produced `READY_TO_MERGE`.
4. PR was squash-merged automatically.

Evidence:
- PR state: `MERGED`
- Merge commit: `91ea471b4c52397776cd15278d82da717da258ec`

## High-risk gate / cleanup
PR: `https://github.com/mahama-11/platform-backend/pull/5`

Purpose:
- Fix platform-backend CI deletion-file handling discovered by the repair validation.
- Remove temporary Go validation file left by PR #3.

Flow observed:
1. PR touched `.github/workflows/ci.yml`; risk classified as high.
2. Webhook produced `NEEDS_HUMAN` with labels `risk:high`, `ai-needs-human`.
3. CI `Go baseline checks` passed after workflow syntax correction.
4. PR was manually squash-merged as a high-risk cleanup after evidence review.

Evidence:
- PR state: `MERGED`
- Merge commit: `98aa95b78273ae4d6aa3508a983ead71d1bb869a`
- Verification on platform-backend main: `TEMP_FILE_REMOVED`

## Result
PASS. The live system now supports:
- webhook-triggered repair decision
- bounded deterministic repair commit push
- CI rerun after repair
- policy-gated automatic merge
- high-risk human gate
- validation artifact cleanup
