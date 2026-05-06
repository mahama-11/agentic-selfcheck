# SelfCheck Static Verifier Execution

Role: orchestrator
Request: Continue from v0 bootstrap and make the system start proving real project checks instead of only dry-run planning.

Scope:
- Add safe command rendering for project adapter verifier commands.
- Allow bounded execution for static/unit/evidence verifier kinds.
- Emit JSON evidence reports under `reports/<feature>/`.
- Use Agent Ecommerce worktree as first real validation adapter for static frontend checks.

Non-goals:
- Do not execute API/browser smoke placeholders as PASS.
- Do not auto-approve release or product quality.
