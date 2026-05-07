# Requirement: GitHub PR Autonomy

Role: Orchestrator

## User intent
Implement方案B：GitHub webhook triggers a generic AI PR review/autonomy flow. The system should define default conditions, terminal conditions, state machine, and safe merge/repair behavior.

## Core question resolved
This must be a generic process engine with project-specific policy/adapters.

- Generic core: event normalization, state machine, risk classification, role gates, terminal conditions, GitHub reporting contract, bounded repair/merge actions.
- Project specialization: repository allowlist, required checks, file risk patterns, product-specific verifier mappings, local runtime gates, auto-merge thresholds.

## Scope for this slice
- Add policy/config schema for PR autonomy.
- Add V workspace policy instance for mahama-11 repos.
- Add a deterministic dispatcher scaffold that accepts normalized GitHub PR events and computes next state/actions without calling LLMs yet.
- Add documentation for webhook wiring and state machine.
- Add tests/validation so the policy is machine-checkable.

## Non-goals for this slice
- Do not enable live auto-merge yet.
- Do not install GitHub webhooks with secrets in this commit.
- Do not run long AI reviewer agents from CI.
- Do not store tokens, webhook secrets, private keys, or credentials.

## Acceptance
- `python3 -m selfcheck validate --root .` passes.
- `python3 -m selfcheck audit --root .` passes.
- New policy validates with tests.
- Dispatcher dry-run can classify representative events into terminal/next actions.
- Documentation states default conditions, termination conditions, and generic-vs-project specialization boundary.

## Safety boundaries
- Auto-merge defaults disabled.
- Any high-risk/security/migration/prod-config classification requires human decision.
- Repair loops are bounded.
- Unknown repo/event/action must no-op with BLOCKED/ignored status.
- Dry-run must not report PASS as executed action.
