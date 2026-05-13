# Repair Event 002 — Template preflight hardening

A post-repair quality review found one remaining partial-side-effect risk: if the source `PROJECT_ADAPTER.yaml` template itself was schema-invalid, init could copy files and only fail after post-write validation.

Repair landed:
- `preflight_init()` now parses and validates the source adapter template against `schemas/frontend-project-adapter.schema.json` before writing any project files;
- template command values are checked for concrete non-placeholder strings during preflight;
- smoke now includes `bad-corrupt-template-no-partial-writes`, which temporarily corrupts the source template and verifies init fails before any target file is written.
