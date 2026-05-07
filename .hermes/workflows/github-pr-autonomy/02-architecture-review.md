# Architecture Review: GitHub PR Autonomy

Role: Architect

## Decision
Implement the PR automation as a generic, deterministic policy engine with project-specific policy/adapters.

```text
GitHub webhook
→ normalized PR event
→ policy lookup
→ PR snapshot/risk classification
→ deterministic state transition
→ planned review/repair/report/merge actions
→ terminal state
```

AI review is an input to the governance loop, not the authority that directly decides merge safety. Merge safety is decided by policy + CI + latest SHA + risk class + verifier status.

## Generic core owns
- Event normalization.
- Policy schema validation.
- State machine and terminal state rules.
- Risk taxonomy and file-pattern classification.
- Idempotent dry-run action planning.
- Bounded repair accounting.
- Generic GitHub reporting action contract.
- Safe defaults: no live side effects unless explicitly enabled.

## Project policy owns
- Repo allowlist.
- Base branch restrictions.
- Required GitHub checks.
- File risk patterns.
- SelfCheck feature/verifier mapping.
- Runtime gate mapping.
- Repair allow/deny globs and attempt limits.
- Auto-merge eligibility thresholds.
- Human decision boundaries.

## Default state machine

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
→ READY_TO_MERGE | READY_FOR_HUMAN
→ MERGED only in a later explicitly enabled phase
```

## Terminal conditions

### PASS
Allowed only when latest head SHA is evaluated, policy matches, PR is open/non-draft, required checks pass, required verifiers pass or are planned as satisfied, risk is not high, and no blocking issue remains.

### PASS_WITH_NOTES
All required gates pass, only non-blocking findings remain, risk is not high, and notes are reported.

### NEEDS_HUMAN
Required for high-risk files, security/migration/prod-config, ambiguous policy, disabled auto-merge, public API/data model/product decisions, or repair beyond policy scope.

### BLOCKED
Required for invalid policy, unknown required action, missing PR snapshot, failed checks without repair path, missing/stale evidence, or exhausted repair attempts.

### IGNORED
Allowed for stale/duplicate/irrelevant events, intentionally unlisted repos, closed PRs that require no final report.

### MERGED
Future-only. Requires PASS plus explicit `auto_merge.enabled=true`, latest-SHA recheck, eligible risk class, satisfied branch protection, allowed merge method, and no human-required condition.

## Safety defaults

```yaml
dry_run: true
auto_merge.enabled: false
repair.enabled: false by default
high_risk_requires_human: true
unknown_repo: ignored
unknown_action: blocked
max_repair_attempts: 1
```

## Rollout phases
1. Policy/schema/dispatcher dry-run.
2. Advisory PR comments/status.
3. Required AI review check.
4. Bounded repair loop on allowlisted files.
5. Low-risk auto-merge after explicit policy flip.

## Architecture verdict
APPROVE for scaffold implementation with auto-merge disabled. The V workspace should be represented only as a policy instance and optional adapter mapping, not hardcoded into the generic PR autonomy state machine.
