# Design Lane Orchestration

Use after the Design Quality Pack gate passes and before high-fidelity prototype acceptance.

## Lane policy

- risk: C|D
- required_lane_count: 1 for C, 2+ for D
- shared_design_quality_pack: ./REFERENCE_PACK.md, ./AESTHETIC_DIRECTION.md, ./ANTI_PATTERNS.md, ./DESIGN_TOKENS_MAP.md, ./COMPONENT_INVENTORY.md, ./PROJECT_FRONTEND_RULES.md

## Required lane directions

| Lane | Direction | Purpose | Status | Artifact | Screenshot | Notes |
|---|---|---|---|---|---|---|
| lane-a | conservative | safest project-fit baseline | pending | design-lanes/lane-a/PROTOTYPE_ARTIFACT.md | design-lanes/lane-a/screenshots/ | design-lanes/lane-a/LANE_NOTES.md |
| lane-b | strong-fit | strongest product/context fit | pending | design-lanes/lane-b/PROTOTYPE_ARTIFACT.md | design-lanes/lane-b/screenshots/ | design-lanes/lane-b/LANE_NOTES.md |
| lane-c | divergent | bolder exploration; optional unless D-risk needs a third option | pending | design-lanes/lane-c/PROTOTYPE_ARTIFACT.md | design-lanes/lane-c/screenshots/ | design-lanes/lane-c/LANE_NOTES.md |

## Selection rule

Do not proceed to prototype acceptance until lane comparison explains why the selected lane best satisfies the Design Quality Pack and why rejected lanes were rejected.
