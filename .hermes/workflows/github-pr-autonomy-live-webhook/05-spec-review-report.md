# Spec Review Report — github-pr-autonomy-live-webhook

Status: **PASS**

## Review scope

Reviewed requirement, architecture/developer/QA/repair evidence under `.hermes/workflows/github-pr-autonomy-live-webhook/`, plus relevant implementation files:

- `scripts/github_pr_autonomy_webhook_server.py`
- `scripts/github_pr_autonomy_report.py`
- supporting policy evidence from `pr-autonomy-policies/github-pr-autonomy-v-workspace.yaml` and dispatcher behavior in `selfcheck/pr_autonomy.py`

No implementation files were edited.

## Acceptance coverage

| Requirement acceptance item | Coverage | Evidence |
|---|---:|---|
| Webhook/gateway route exists and health check passes, with no false live claim | PASS | `07-qa-report.md` reports local service and Cloudflared tunnel active; reviewer rechecked `GET http://127.0.0.1:8655/health` -> `200 {"status":"ok","service":"github-pr-autonomy-webhook"}`. `github_pr_autonomy_webhook_server.py` implements `/health`, signed POST endpoints, event enrichment, trigger + reporter orchestration. |
| 4 V workspace GitHub webhooks created/updated for PR and workflow/check events | PASS | `07-qa-report.md` lists active hooks for `platform-backend`, `ecommerce-backend`, `platform-frontend`, `ecommerce-frontend`, each with `check_run`, `pull_request`, `workflow_run` and ping `200 OK`. |
| Test PR/event produces `pr_autonomy_decision` | PASS | `07-qa-report.md` records live PR #3 flow; `reports/events/github.pull_request-1778160111.json` contains `pr_autonomy_decision` with repo/PR/SHA/state. Webhook server writes enriched payloads with `changed_files`, `check_runs`, `head_sha`, labels. |
| Reporter writes comment/status/labels and supports dry-run/apply-safe | PASS | `github_pr_autonomy_report.py` implements marker comment upsert, commit status, label ensure/reconcile, dry-run default, `--apply` side-effect gate, and `--allow-merge` gate. Evidence includes `reports/github-pr-autonomy-live-webhook/manual-label-upsert-test.json` and live report JSON with `comment_upsert`, `status`, and label actions exit code 0. |
| CI failed routes to bounded repair when policy allows; otherwise block/needs-human | PASS | `selfcheck/pr_autonomy.py` has failed-check branch returning `NEEDS_REPAIR` + `CREATE_REPAIR_DISPATCH` only when repo repair is enabled, attempts remain, files are allowed, and risk is not high; current V policy has repair disabled, so failed checks block conservatively. This matches rollout safety scope. |
| CI success + AI/SelfCheck PASS + policy allow before merge; auto-merge may remain disabled but gate is verifiable | PASS | Current V policy has `auto_merge.enabled: false` and per-repo `auto_merge_enabled: false`, producing `READY_FOR_HUMAN`; reporter only executes merge when `--apply --allow-merge`, state `READY_TO_MERGE`, and `MERGE_PR_PLANNED_ONLY` are all present. QA live PR reached `READY_FOR_HUMAN` after CI success as expected. |
| SelfCheck validate/audit and feature gates pass | PASS | Reviewer re-ran `python3 -m selfcheck validate --root .` -> `PASS: no issues`; `python3 -m selfcheck audit --root . --feature github-pr-autonomy --strict-missing` -> `PASS: no issues`. |
| Secret handling and redaction | PASS | Webhook server requires `GITHUB_PR_AUTONOMY_WEBHOOK_SECRET`, verifies HMAC SHA-256, and redacts keys containing secret/token/password/authorization/api_key/key before writing JSON. QA notes secret stored outside repo in `0600` env file and no token/secret printed. |

## Notes / residual risks

- Evidence for live hooks is summarized in `07-qa-report.md` rather than the originally proposed named artifacts such as `hermes-route-health.json` and `github-hooks.json`. This is acceptable for spec review because concrete hook IDs, event sets, ping status, live PR URL, and runtime health are recorded, but final verification may prefer adding stable machine-readable summary artifacts.
- The implementation uses a dedicated deterministic webhook server plus Cloudflared tunnel. This satisfies the ingress/health behavior in the acceptance evidence, though it is not a generic Hermes gateway config file.
- `check_suite` is not explicitly handled by `github_pr_autonomy_webhook_server.py`; configured hooks use `check_run`, `pull_request`, and `workflow_run`, which covers the acceptance wording for workflow/check-related triggers.
- Auto-merge and repair execution remain intentionally disabled in the V rollout. The policy/reporter gates are verifiable; no destructive action is enabled by default.

## Verdict

**PASS.** The delivered scope covers the live GitHub webhook -> enriched SelfCheck PR autonomy decision -> GitHub reporter feedback loop for the four V workspace repositories, with conservative repair/merge gates and secret redaction. No blocking spec gaps were found for this rollout.
