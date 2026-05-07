# Developer Summary — github-pr-autonomy-live-webhook

## Implemented

- Added deterministic live GitHub webhook receiver:
  - `scripts/github_pr_autonomy_webhook_server.py`
  - HMAC verification via `GITHUB_PR_AUTONOMY_WEBHOOK_SECRET`.
  - Supports `pull_request`, `workflow_run`, and `check_run` events.
  - Enriches raw GitHub payload with PR files and check-run/status snapshot before dispatch.
  - Runs `python3 -m selfcheck trigger --route github-pr-autonomy --source hermes-webhook`.
  - Runs `scripts/github_pr_autonomy_report.py --apply --labels` for GitHub write-back.
  - Ignores self-generated `pull_request:labeled` / `unlabeled` events to avoid automation loops.

- Hardened GitHub reporter:
  - `scripts/github_pr_autonomy_report.py`
  - Upserts one `## AI PR Autonomy Decision` comment instead of creating unbounded duplicate comments.
  - Writes commit status context `AI Review / PR Autonomy`.
  - Applies and reconciles managed labels: `ai-reviewed`, `ai-state:*`, `risk:*`, plus transient state labels.
  - Uses `gh issue edit` for labels to avoid `gh pr edit` GraphQL projectCards failure.
  - Keeps merge behind `--allow-merge` and policy decision `READY_TO_MERGE`.

- Added hook sync watchdog:
  - `scripts/github_pr_autonomy_sync_hooks.py`
  - Parses current Cloudflared trycloudflare URL from tunnel logs.
  - Upserts the same webhook URL/secret/events on the 4 V workspace repos.
  - Removes the failed direct-IP hook if present.

- Updated event dispatch helper and docs:
  - `scripts/event-dispatch.sh` now accepts `SOURCE` as the 4th arg.
  - `docs/event-callbacks.md` documents `hermes-webhook` source dispatch.

## Runtime configured outside repo

Secrets are not committed. Runtime config lives outside the repo:

- `/root/.hermes/agentic-selfcheck-github-webhook.env` mode `0600`.
- `agentic-selfcheck-github-webhook.service`: deterministic receiver on local port `8655`.
- `agentic-selfcheck-github-webhook-tunnel.service`: Cloudflared HTTPS tunnel.
- `agentic-selfcheck-github-webhook-sync.timer`: refreshes GitHub hooks every 5 minutes if tunnel URL changes.

## GitHub hooks configured

Active hooks configured on:

- `mahama-11/platform-backend`
- `mahama-11/ecommerce-backend`
- `mahama-11/platform-frontend`
- `mahama-11/ecommerce-frontend`

Events:

- `pull_request`
- `workflow_run`
- `check_run`

Latest verified URL:

- `https://karl-combo-dome-hub.trycloudflare.com/github-pr-autonomy`

## Live validation

Temporary validation PR:

- `https://github.com/mahama-11/platform-frontend/pull/3`

Observed states:

- PR opened while CI running -> `WAITING_FOR_CHECKS`.
- Workflow/check redelivery after CI success -> `READY_FOR_HUMAN`.

Observed GitHub write-back:

- AI PR Autonomy comment updated.
- Commit status written.
- Labels converged to `ai-reviewed`, `risk:low`, `ai-state:ready-for-human`.

Cleanup:

- PR #3 closed after evidence capture.
- Test branch deleted.

## Verification

Passed:

```bash
python3 -m py_compile scripts/github_pr_autonomy_webhook_server.py scripts/github_pr_autonomy_report.py scripts/github_pr_autonomy_sync_hooks.py
python3 scripts/github_pr_autonomy_policy_validate.py --root . --policy github-pr-autonomy-v-workspace
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root .
```

Runtime checks passed:

```text
GET http://127.0.0.1:8655/health -> 200
4/4 GitHub hook ping/delivery -> 200 OK
hook-sync timer -> active
latest sync report -> PASS
```

## Safety status

- Repair remains disabled by V policy.
- Auto-merge remains disabled by V policy and service env.
- High-risk PRs require human decision.
- Unknown repos/actions remain ignored/blocked by policy.
- Live loop is enabled for conservative comment/status/label governance only.
