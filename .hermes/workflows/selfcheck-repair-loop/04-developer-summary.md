# Developer Summary

Role: developer

Changed:
- Added `schemas/repair-policy.schema.json`.
- Added `repair-policies/default-repair-policy.yaml`.
- Added optional `repair_policy` to feature schema and wired current features to default policy.
- Added `selfcheck loop` command.
- Added loop state/report/dispatch artifact generation.
- Added `docs/repair-loop.md`.
- Added `features/selfcheck-repair-loop.yaml`.

Key behavior:
- PASS resets loop state.
- Failure creates `.hermes/dispatch/<feature>/...-<owner>.md`.
- Repeated same failure or attempts exhaustion returns BLOCKED.
