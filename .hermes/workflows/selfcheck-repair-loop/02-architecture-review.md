# Architecture Review

Role: architect
Verdict: APPROVE_WITH_NOTES

Decision:
- SelfCheck remains control-plane/verifier, not implementer.
- `repair-policies/default-repair-policy.yaml` defines owner mapping, max attempts, same-failure limit, forbidden actions, and escalation reasons.
- `selfcheck loop` performs bounded run/classify/dispatch/report behavior.
- Dispatch artifacts are owner assignments, not approvals.

Risk boundary:
- The CLI cannot directly spawn Hermes subagents; it emits dispatch artifacts that the orchestrator/Hermes runtime can turn into delegate_task calls.
