# Architecture Review

Decision: add reference-aware critique as a generic control-plane layer between `visual-critique.json` and prototype acceptance.

Flow:

```text
Design Quality Pack -> Design Lanes -> visual-critique.json -> reference-aware-critique.json -> frontend_quality_gate.py -> implementation
```

Artifacts:

- `schemas/frontend-reference-aware-critique.schema.json`
- `scripts/frontend_reference_aware_critic.py`
- `scripts/frontend_reference_aware_critic_smoke.py`
- `features/frontend-reference-aware-visual-critic.yaml`
- `verifiers/frontend-reference-aware-visual-critic-gate.yaml`

The gate intentionally validates context alignment fields instead of trying to render/inspect images itself. Actual visual perception remains in the upstream visual critique runner; this layer prevents a visually passable but context-misaligned prototype from passing.
