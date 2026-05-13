# Requirement: frontend-prototype-freeze

Implement a deterministic prototype freeze / implementation contract gate for C/D-risk frontend workflows.

Required behavior:
- Freeze payload is strict JSON with schema version, risk, workflow, selected lane, accepted prototype, frozen screenshots, mappings, deviations, and approval.
- Previous prototype acceptance artifacts must exist before freeze.
- Selected lane and frozen PNG screenshot evidence must resolve to real files.
- Component and API/state mappings must be explicit or marked `contract_needed` with rationale.
- Material deviations require approved status and rationale.
- D-risk requires `human_approved`; C-risk allows `accepted` or `human_approved`.
