# QA Report — github-pr-autonomy-live-webhook

Status: PASS

## Runtime services
- `agentic-selfcheck-github-webhook.service`: active/running.
- Local health: `GET http://127.0.0.1:8655/health -> 200 {"status":"ok","service":"github-pr-autonomy-webhook"}`.
- Cloudflared tunnel service: active/running.
- Public webhook URL configured in GitHub hooks: `https://karl-combo-dome-hub.trycloudflare.com/github-pr-autonomy`.

## GitHub webhook/tunnel configuration
- Cloudflared quick tunnel is supervised by `agentic-selfcheck-github-webhook-tunnel.service`.
- Hook URL synchronization is supervised by `agentic-selfcheck-github-webhook-sync.timer` every 5 minutes.
- Latest sync report status: `PASS`, URL `https://karl-combo-dome-hub.trycloudflare.com/github-pr-autonomy`.

4/4 V workspace repos have active webhooks:
- `mahama-11/platform-backend` hook `619032381`, events `check_run`, `pull_request`, `workflow_run`, ping `200 OK`.
- `mahama-11/ecommerce-backend` hook `619032528`, events `check_run`, `pull_request`, `workflow_run`, ping `200 OK`.
- `mahama-11/platform-frontend` hook `619032669`, events `check_run`, `pull_request`, `workflow_run`, ping `200 OK`.
- `mahama-11/ecommerce-frontend` hook `619032786`, events `check_run`, `pull_request`, `workflow_run`, ping `200 OK`.

## Live PR test
Temporary PR:
- URL: `https://github.com/mahama-11/platform-frontend/pull/3`
- Branch: `test/pr-autonomy-live-webhook-1778159745`
- Change: docs-only low-risk test file.

Observed automation:
- PR open triggered webhook receiver.
- Receiver enriched payload with changed files and check runs.
- SelfCheck event route produced `pr_autonomy_decision`.
- Reporter wrote GitHub PR comment/status/labels.
- Initial state while CI was running: `WAITING_FOR_CHECKS`.
- After redelivered workflow/check event with CI success: `READY_FOR_HUMAN` because auto-merge is intentionally disabled.
- Final labels: `ai-reviewed`, `risk:low`, `ai-state:ready-for-human`.
- Final comment body starts with `## AI PR Autonomy Decision` and reports `READY_FOR_HUMAN`.

Cleanup:
- PR #3 closed after evidence capture.
- Test branch deleted.

## Safety observations
- Webhook secret stored only in `/root/.hermes/agentic-selfcheck-github-webhook.env` mode `0600` and GitHub webhook config; not committed.
- No token/secret printed in evidence.
- Receiver ignores self-generated `pull_request:labeled` / `unlabeled` to avoid automation loops.
- Auto-merge remains disabled by policy and service env.

## Verdict
PASS. The GitHub webhook -> SelfCheck PR autonomy -> GitHub reporter loop is live for the 4 V workspace repos, with conservative merge/repair gates.
