# Repair Events — github-pr-autonomy-live-webhook

## 2026-05-07 — Live webhook reporter hardening

Status: CLOSED

### Issue 1: Public direct-IP webhook unreachable
- Observation: GitHub hook to `http://51.68.227.243:8655/github-pr-autonomy` produced delivery `status_code=0`; direct no-proxy curl to public IP port 8655 failed with connection refused.
- Repair: Installed Cloudflared quick tunnel service and updated 4 repo hooks to HTTPS trycloudflare URL.
- Verification: GitHub ping deliveries returned `status_code=200` for all 4 repos.

### Issue 2: Reporter duplicated comments and failed label application
- Observation: platform-frontend test PR #3 received repeated comments; labels were initially absent because `gh pr edit --add-label` hit a GraphQL projectCards issue.
- Repair: Reporter now upserts a single AI PR Autonomy comment and uses `gh issue edit` for labels.
- Verification: Manual reporter apply succeeded with status/comment/labels.

### Issue 3: Self-generated label events caused PR automation loop
- Observation: PR label changes emitted `pull_request:labeled` events, which policy classified as unsupported action and overwrote the decision as `BLOCKED`.
- Repair: Webhook receiver ignores `pull_request:labeled` and `pull_request:unlabeled` at receiver boundary; reporter reconciles managed `ai-state:*` and `risk:*` labels so stale states are removed.
- Verification: Redelivered workflow/check events updated PR #3 to `READY_FOR_HUMAN`; final labels converged to `ai-reviewed`, `risk:low`, `ai-state:ready-for-human`.

### Issue 4: Closed PR could receive a non-actionable IGNORED writeback
- Observation: Final verification noted that closing the temporary validation PR could still produce an `IGNORED` decision writeback.
- Repair: Webhook receiver now ignores live `pull_request:closed` at the receiver boundary, like self-generated label churn.
- Verification: `py_compile`, SelfCheck validate/audit, and final verification superseding report.

## Final repair status
CLOSED. No open repair events remain.
