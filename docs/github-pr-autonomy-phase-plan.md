# GitHub PR Autonomy Phase Plan

Status: implemented as safe control-plane scaffolding on `main`.

## Phase 1 — Policy / state machine
Implemented.

Artifacts:
- `schemas/pr-autonomy-policy.schema.json`
- `pr-autonomy-policies/github-pr-autonomy-v-workspace.yaml`
- `selfcheck/pr_autonomy.py`
- `scripts/github_pr_autonomy_policy_validate.py`

## Phase 2 — Webhook reporting
Implemented as CLI reporter scaffold.

Artifacts:
- `events/github-pr-autonomy.yaml`
- `scripts/github_pr_autonomy_report.py`

Behavior:
- GitHub/Hermes webhook payload can be normalized and evaluated.
- `selfcheck trigger` attaches `pr_autonomy_decision`.
- Reporter can post PR comments/statuses with `--apply`.
- Default mode is dry-run report generation.

## Phase 3 — AI review roles
Implemented as model routing/policy scaffold.

Artifacts:
- `schemas/role-model-routing.schema.json`
- `role-model-routing/default-role-model-routing.yaml`
- `scripts/role_model_routing_validate.py`
- `docs/role-model-routing.md`

Behavior:
- Deterministic roles use `minimax-cn / MiniMax-M2.7-highspeed`.
- Architecture/development/high-risk quality decisions stay on high-capability model.
- Secrets are outside repo.

## Phase 4 — Bounded repair
Implemented in policy decision layer.

Behavior:
- Repair is disabled in current V policy.
- If enabled later, dispatcher enforces attempt count, denied globs, allowed globs, and high-risk guard.
- Repair action is only `CREATE_REPAIR_DISPATCH`; actual agent execution must be a later executor/harness step.

## Phase 5 — Low-risk auto-merge
Implemented as gated reporter capability, disabled by policy.

Behavior:
- `scripts/github_pr_autonomy_report.py --apply --allow-merge` can merge only when dispatcher state is `READY_TO_MERGE` and planned action contains `MERGE_PR_PLANNED_ONLY`.
- Current policy keeps `auto_merge.enabled: false`, so clean PRs route to `READY_FOR_HUMAN`.
- Turning on auto-merge requires explicit policy edit after the system is stable.

## Early-stage exception
`agentic-selfcheck` itself is still early-stage and does not enforce PR autonomy gates yet. Changes may be merged directly until a stable formal version exists.
