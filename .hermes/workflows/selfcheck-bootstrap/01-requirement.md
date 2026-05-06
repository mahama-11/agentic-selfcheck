# Agentic SelfCheck Bootstrap Workflow

Role: orchestrator
Inputs read:
- User request: build a reusable self-consistency / acceptance system; use /root/work/v as validation field; target L3/L3.5.
- Skills: enterprise-product-engineering, enterprise-role-orchestration, v-workspace-engineering, writing-plans, subagent-driven-development, webhook-subscriptions.

Decisions:
- Create a separate project at `/root/work/agentic-selfcheck` instead of embedding governance inside `/root/work/v`.
- Treat `/root/work/v` as first project adapter, not as the product boundary of the system.
- v0 focuses on schema validation, reference integrity, verifier planning, evidence-gate audit, and loop definitions.

Target:
- L3: machine-enforced acceptance gates.
- L3.5: lightweight loop/hook definitions for workflow-health, ci-repair, and requirement-drift.

Non-goals:
- Replace coding agents or CI.
- Auto-approve release decisions.
- Execute non-dry-run project verifiers before adapters are hardened.
