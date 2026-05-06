# V Workspace Requirement SelfCheck Integration

This document connects `/root/work/v` requirement delivery to the external Agentic SelfCheck control plane at `/root/work/agentic-selfcheck`.

## Goal

For non-trivial v workspace requirements, do not rely only on chat summaries or implementer self-report.

```text
requirement chat
→ feature acceptance contract
→ isolated branch/worktree implementation
→ SelfCheck trigger/loop
→ verifier evidence
→ dispatch repair if failing
→ rerun SelfCheck
→ verified PASS/PASS_WITH_NOTES/BLOCKED
```

## Current integrated target

```text
Project adapter: projects/v-ecommerce-worktree.yaml
Primary feature: features/ecommerce-product-ai-pipeline.yaml
Event route: events/changed-v-ecommerce-requirement.yaml
Gate script: scripts/v-requirement-gate.sh
```

This targets the active Agent Ecommerce V1 worktree first, because it already has real static/API/browser/evidence verifiers.

## Requirement gate command

```bash
cd /root/work/agentic-selfcheck
scripts/v-requirement-gate.sh ecommerce-product-ai-pipeline static,api,browser,evidence requirement.changed.v.ecommerce-product-ai-pipeline
```

With an explicit executor/Hermes runner:

```bash
SELFCHECK_EXECUTOR_COMMAND='<explicit owner executor command>' \
  scripts/v-requirement-gate.sh ecommerce-product-ai-pipeline static,api,browser,evidence requirement.changed.v.ecommerce-product-ai-pipeline
```

## Status meaning

```text
0  PASS or PASS_WITH_NOTES: required gate passed; inspect latest loop report for exact status.
2  NEEDS_REPAIR: SelfCheck generated dispatch artifacts for owner roles.
3  BLOCKED: repeated failure, exhausted attempts, or human boundary.
```

## Boundary

- SelfCheck is not embedded into `/root/work/v`; it remains a reusable external control plane.
- `/root/work/v` remains a multi-repo workspace; adapters point to the relevant repo/worktree.
- Browser/API smoke currently prove readiness/login surface, not full authenticated Product Detail AI Pipeline E2E.
- For new v requirements, add/adjust a feature contract before implementation rather than redefining success after coding.
