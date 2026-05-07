# GitHub PR Autonomy

This document defines the generic PR autonomy flow used by Agentic SelfCheck and the V workspace policy instance.

## Generic vs project-specific

The PR autonomy engine is generic. It owns event normalization, policy validation, state transitions, risk classification, terminal conditions, and planned actions.

Project policy is specific. It owns repo allowlists, required checks, file risk patterns, verifier mappings, repair allowances, and merge eligibility.

For V workspace, the current policy instance is:

```text
pr-autonomy-policies/github-pr-autonomy-v-workspace.yaml
```

## Trigger

GitHub sends `pull_request` events to Hermes webhook. Hermes routes them to SelfCheck:

```text
GitHub pull_request opened/synchronize/reopened/ready_for_review
→ Hermes webhook
→ selfcheck PR autonomy dispatcher
→ policy dry-run/action planning
→ future GitHub comment/check/repair/merge reporter
```

Initial implementation is policy/dry-run only. It does not install live webhooks, write secrets, or merge PRs.

## Default conditions

```text
dry_run: true
auto_merge: disabled
unknown_repo: ignored
unknown_action: blocked
high_risk_requires_human: true
repair: disabled unless repo policy explicitly enables it
max_repair_attempts: 1
```

## State machine

```text
RECEIVED
→ NORMALIZED
→ POLICY_MATCHED | IGNORED | BLOCKED
→ SNAPSHOT_LOADED
→ RISK_CLASSIFIED
→ WAITING_FOR_CHECKS | AI_REVIEW_PENDING | NEEDS_HUMAN
→ AI_REVIEWED
→ VERIFYING
→ PASS | PASS_WITH_NOTES | NEEDS_REPAIR | NEEDS_HUMAN | BLOCKED
→ READY_FOR_HUMAN | READY_TO_MERGE
→ MERGED only when explicitly enabled in a later phase
```

## Terminal states

```text
PASS             all required gates pass, latest SHA verified, non-high risk
PASS_WITH_NOTES  gates pass with non-blocking findings
READY_FOR_HUMAN  gates pass, but policy requires human merge/approval
NEEDS_HUMAN      risk/policy/product decision requires human judgement
BLOCKED          invalid policy, failed checks without repair, missing evidence, exhausted attempts
IGNORED          irrelevant/stale/closed/unlisted event
MERGED           future phase only
```

## Risk policy

High-risk PRs must not be auto-repaired or auto-merged. High-risk patterns include:

```text
.github/workflows/**
**/migration/**
**/migrations/**
**/auth/**
**/access/**
**/rbac/**
**/billing/**
**/commercial/**
**/payment/**
**/config.prod*
**/.env*
**/*secret*
**/*credential*
```

Project policies may add more patterns.

## Repair behavior

Repair is bounded and disabled by default.

If enabled later:

```text
failed verifier/check
→ classify repairability
→ create repair dispatch
→ developer/repair agent pushes fix
→ rerun exact failed gate
→ final verifier decides PASS/BLOCKED
```

Repair must not modify denied/high-risk files without explicit human approval.

## Merge behavior

Auto-merge is disabled by default. Future auto-merge requires all of:

```text
latest SHA still matches verified SHA
required GitHub checks pass
required SelfCheck verifiers pass
risk is allowed by policy
no human-required condition
branch protection permits merge
merge method allowed by policy
```

## Current V workspace policy

Repos covered:

```text
mahama-11/platform-backend
mahama-11/ecommerce-backend
mahama-11/platform-frontend
mahama-11/ecommerce-frontend
```

Each repo maps to its current baseline CI check and relevant SelfCheck feature groups. The policy is intentionally conservative: PRs that pass checks become `READY_FOR_HUMAN`, not auto-merged.

## Local validation

```bash
python3 scripts/github_pr_autonomy_policy_validate.py --root . --policy github-pr-autonomy-v-workspace
python3 scripts/github_pr_autonomy_report.py --root . --policy github-pr-autonomy-v-workspace --payload-file /tmp/github-pr-event.json
python3 -m selfcheck run --root . --feature github-pr-autonomy --groups static --timeout 300
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root .
```
