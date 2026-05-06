# Architecture Review

Role: architect
Verdict: APPROVE

Design decisions:
- Keep `/root/work/v` adapter for general workspace; add separate `v-ecommerce-worktree` adapter for active isolated validation.
- Resolve commands from `{project.root}`, `{service.path}`, `{service.commands.*}`, and `{feature.id}` templates.
- Only execute safe kinds by default: static, unit, evidence.
- API/browser verifiers remain harness-required and are skipped by the generic runner unless separately wired.
- Every verifier run writes a JSON evidence artifact.

Risk controls:
- Shell execution is bounded by explicit `--groups` and timeout.
- Browser/API placeholders cannot be mistaken for PASS.
