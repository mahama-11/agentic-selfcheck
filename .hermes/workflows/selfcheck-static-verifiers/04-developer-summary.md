# Developer Summary

Role: developer

Changed files:
- `selfcheck/__main__.py`
- `schemas/feature.schema.json`
- `projects/v-ecommerce-worktree.yaml`
- `features/ecommerce-product-ai-pipeline.yaml`
- `README.md`

Implemented:
- Feature `target_services` schema/reference validation.
- Project/service-aware command rendering.
- Generic safe verifier execution for static/unit/evidence kinds.
- `--groups` and `--timeout` controls for `selfcheck run`.
- Per-verifier JSON reports under `reports/<feature>/<verifier>.json`.
- Active ecommerce worktree adapter for first real validation run.
