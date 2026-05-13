# Architecture Review

Decision: model design lanes as a generic SelfCheck control-plane primitive, not V-specific product code.

Layering:

- `templates/frontend/design-lane-generation/*`: reusable artifact contract.
- `schemas/frontend-design-lane.schema.json`: structured future interchange contract.
- `scripts/frontend_design_lane_gate.py`: executable static/workflow gate.
- `features/frontend-design-lane-generation.yaml` + verifier: SelfCheck integration.
- `scripts/init_frontend_workflow.py`: scaffolds the lane surface for C/D frontend tasks.

Dependency direction: Design Quality Pack -> Design Lane Generation -> Visual Critique/Prototype Gate -> Production Parity.
