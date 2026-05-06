# Architecture Review

Role: architect

Findings:
- The system must be project-agnostic; project-specific paths/ports/commands belong in `projects/*.yaml` adapters.
- Acceptance should be layered: invariants → capabilities → features → verifiers → evidence → loops.
- The first version should be file/schema based so it can run locally, in CI, or from Hermes cron/webhooks.

Architecture:
- `schemas/*.schema.json` define allowed governance file shapes.
- `invariants/*.yaml` define durable cross-project truths.
- `capabilities/*.yaml` define reusable capability contracts and required verifiers.
- `features/*.yaml` define versioned feature acceptance specs.
- `verifiers/*.yaml` define commands/evidence requirements.
- `loops/*.yaml` define safe loop behavior and escalation boundaries.
- `selfcheck` CLI validates references and audits evidence.

Risks:
- Non-dry-run verifier execution needs templating/adapter resolution before safe rollout.
- Browser/API verifier placeholders must not be treated as PASS.
