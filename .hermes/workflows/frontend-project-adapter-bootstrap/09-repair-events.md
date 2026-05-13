# Repair Events

## frontend-project-adapter quality blocker repair

- Hardened `scripts/frontend_project_adapter_init.py` preflight for generated target parent conflicts (for example `.cursor` as a regular file) before any project writes occur.
- Added best-effort transactional rollback around initialization writes so failed initialization restores/re removes generated targets instead of leaving partial output.
- Replaced raw `jsonschema` validation messages with field-path plus generic reason messages to avoid leaking invalid instance values such as secret-like tokens, absolute paths, `Bearer` values, API keys, or passwords.
- Updated `scripts/frontend_project_adapter_smoke.py` coverage for:
  - `.cursor` parent path conflict with no partial generated files.
  - Schema violation using a secret-like absolute path with stdout redaction assertions.
  - Corrupt template preflight against a temporary copied SelfCheck root, verifying the source checkout template remains unchanged.

Status: CLOSED
