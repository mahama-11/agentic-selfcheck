# Quality / Security Review — github-pr-autonomy-live-webhook

Status: **PASS** for the current conservative live-webhook rollout.

Scope reviewed: `/root/work/agentic-selfcheck` live webhook receiver, reporter, PR autonomy policy, runtime service assumptions, secret handling, loop prevention, repair/merge gates, and GitHub hook exposure.

Important boundary: this PASS does **not** approve enabling autonomous repair or auto-merge. Those remain **BLOCKED** until the risks below are addressed or explicitly accepted.

## Evidence checked

- Implementation files:
  - `scripts/github_pr_autonomy_webhook_server.py`
  - `scripts/github_pr_autonomy_report.py`
  - `selfcheck/pr_autonomy.py`
  - `pr-autonomy-policies/github-pr-autonomy-v-workspace.yaml`
- Workflow evidence:
  - `.hermes/workflows/github-pr-autonomy-live-webhook/01-requirement.md`
  - `.hermes/workflows/github-pr-autonomy-live-webhook/02-architecture-review.md`
  - `.hermes/workflows/github-pr-autonomy-live-webhook/04-developer-summary.md`
  - `.hermes/workflows/github-pr-autonomy-live-webhook/07-qa-report.md`
- Runtime checks performed:
  - `python3 -m selfcheck validate --root .` → `PASS: no issues`
  - `python3 scripts/github_pr_autonomy_policy_validate.py --root . --policy github-pr-autonomy-v-workspace` → `PASS`
  - local health `GET http://127.0.0.1:8655/health` → `200 ok`
  - unsigned local POST to webhook → `401 signature mismatch`
  - systemd service `agentic-selfcheck-github-webhook.service` → active
  - tunnel service `agentic-selfcheck-github-webhook-tunnel.service` → active/running
  - env file metadata only: `/root/.hermes/agentic-selfcheck-github-webhook.env` mode `0600`, `root:root`
  - GitHub hook API summary for 4 V repos: all active, `insecure_ssl=0`, events include `pull_request`, `workflow_run`, `check_run`, last response `200 OK`
- Additional generated evidence:
  - `reports/github-pr-autonomy-live-webhook/quality-policy-validate.json`

## Positive findings

1. **Webhook authentication is mandatory.** The receiver refuses startup without `GITHUB_PR_AUTONOMY_WEBHOOK_SECRET`, validates `X-Hub-Signature-256` with HMAC SHA-256, and uses `hmac.compare_digest`. Unsigned requests were rejected with `401`.
2. **Secrets are not committed in reviewed source.** Repo content search found no obvious GitHub tokens/private keys/webhook secret values. The local env file is outside the repo and mode `0600`.
3. **Repo allowlist and conservative policy are active.** Policy covers only the 4 `mahama-11` V repos; unknown repos are ignored, unsupported PR actions are blocked unless filtered at receiver boundary.
4. **Raw GitHub events are enriched before dispatch/reporting.** Receiver fetches PR files and check/status data, enabling risk classification and required-check gating instead of relying on incomplete raw webhook payloads.
5. **Loop prevention exists for label churn.** `pull_request:labeled` and `pull_request:unlabeled` are ignored at the receiver boundary; the configured hook events do not include `issue_comment` or `status`, reducing self-trigger loops from comments/statuses.
6. **Repair and merge are off by default.** Policy has `repair.enabled: false` for all repos and global/repo auto-merge disabled. Service env has `allow_merge=false` in the observed listening config; reporter only merges with `--allow-merge` and a `READY_TO_MERGE` decision.
7. **Reporter writeback is mostly idempotent.** It upserts the marker comment, writes a deterministic status context, and reconciles managed labels.
8. **GitHub hook surface matches acceptance.** Four repo hooks are active with JSON content type, SSL verification enabled, and events `pull_request`, `workflow_run`, `check_run`.

## Concrete risks / required follow-up

### R1 — Public webhook DoS and resource exhaustion risk

- Receiver has no maximum `Content-Length`, request body limit, rate limit, timeout policy, or delivery deduplication.
- A validly signed or repeated large request can consume memory/disk and trigger expensive `gh api`, `selfcheck trigger`, reporter, and GitHub writeback operations.
- Because the endpoint is exposed through a public Cloudflared Quick Tunnel, HMAC protects authenticity but not availability.

Required mitigation before higher-trust rollout:
- enforce a body size limit;
- reject unsupported event types before enrichment/work;
- add delivery-id dedupe/replay window;
- add per-repo/PR concurrency lock or queue;
- add rate limiting at tunnel/proxy or service boundary.

### R2 — Service runs as root with broad local/GitHub authority

- systemd unit runs the Python receiver as root from `/root/work/agentic-selfcheck` and uses root’s `gh` auth context.
- Compromise of the receiver process would likely expose repo write/admin capabilities available to `gh`, local reports, and root-owned files.

Required mitigation:
- run under a dedicated least-privilege user;
- use a minimally scoped GitHub token/app installation limited to required repos and permissions;
- harden the systemd unit (`NoNewPrivileges`, `ProtectSystem`, `PrivateTmp`, restricted write paths, etc.).

### R3 — Quick Tunnel URL is operational but fragile

- Hook URL is a `trycloudflare.com` quick tunnel. This is acceptable for live validation evidence, but is not a stable production assumption unless the tunnel lifecycle and URL persistence are externally managed.

Required mitigation:
- use a named/stable tunnel or managed ingress URL;
- monitor hook delivery failures and rotate/reconfigure hooks if URL changes.

### R4 — Merge gate is safe only because policy/service currently disable merge

Current state is safe: policy auto-merge is disabled and observed service has `allow_merge=false`.

However, if future operators enable policy auto-merge and pass `--allow-merge`, reporter merge checks are incomplete:
- does not re-fetch PR immediately before merge to confirm latest head SHA still equals decision SHA;
- does not independently verify GitHub required checks at merge time;
- does not enforce `merge.require_human_approval` from policy;
- does not block merge when `decision.dry_run` is still `true`;
- does not verify branch protection / review state / SelfCheck feature gates immediately before `gh pr merge`.

Conclusion: **auto-merge enablement is BLOCKED** until these gates are implemented and tested.

### R5 — Repair execution is policy-blocked, but live executor boundary is not implemented

- Current policy safely disables repair for all repos.
- Decision engine can plan `CREATE_REPAIR_DISPATCH` in test-mutated policy, but this implementation does not provide an end-to-end safe repair executor with branch push, bounded attempts persistence, and verification-loop ownership.

Conclusion: **autonomous repair enablement is BLOCKED** until a separate least-privilege repair executor and attempt ledger are implemented.

### R6 — Duplicate and concurrent deliveries can cause noisy or inconsistent writeback

- No delivery-id dedupe or PR-level serialization exists.
- Concurrent `workflow_run` / `check_run` deliveries can race comment upsert and label reconciliation.
- This is not currently destructive, but can create API churn, stale labels, or transient incorrect PR presentation.

Required mitigation:
- persist processed `X-GitHub-Delivery` IDs;
- serialize per repo/PR/head SHA;
- prefer latest-SHA-only report writes.

### R7 — Closed PRs still receive reporter side effects

- The receiver enriches closed PR events and reporter may write `IGNORED` comments/status/labels to a closed PR.
- This is safe from a merge perspective, but undesirable noise and can mutate historical evidence after closure.

Recommended mitigation:
- ignore `pull_request:closed` at receiver boundary or run trigger-only without GitHub writeback for closed PRs.

### R8 — Evidence retention is broader than necessary

- Raw/enriched payload evidence is redacted by key-name heuristics, but enriched files retain large GitHub API payloads and public user/repo metadata.
- No retention/rotation policy is visible for `reports/github-pr-autonomy-live-webhook/events`.

Required mitigation:
- store minimal normalized fields needed for audit;
- add retention/rotation;
- redact signature/header material if headers are ever persisted.

## PASS/BLOCKED decision

- **PASS:** current live webhook loop for comment/status/label writeback under conservative policy: authenticated, allowlisted, observable, no repair, no auto-merge.
- **BLOCKED:** enabling autonomous repair.
- **BLOCKED:** enabling autonomous merge.
- **BLOCKED for production hardening:** relying on current root-run public quick-tunnel service without body limits, dedupe, rate limiting, and least-privilege runtime.

## Final reviewer conclusion

The implementation satisfies the safe validation phase of the requirement: GitHub hooks reach a live receiver, signatures are enforced, payloads are enriched, SelfCheck decisions are generated, GitHub writeback works, and destructive actions remain off. The main residual risk is operational hardening rather than immediate policy bypass. Keep repair/merge disabled until the explicit BLOCKED items above are closed.
