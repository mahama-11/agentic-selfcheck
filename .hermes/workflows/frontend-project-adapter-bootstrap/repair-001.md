# Repair Event 001 — Review BLOCK remediation

Spec and quality/security reviewers blocked the first implementation on three issues:

1. `--check` validated only a subset of `schemas/frontend-project-adapter.schema.json`.
2. failed no-force init could leave partial generated files before discovering a later conflict.
3. malformed YAML parser messages could echo source snippets containing secret-like values.

Repairs landed:
- added JSON Schema validation through `jsonschema.Draft202012Validator` in `frontend_project_adapter_init.py`;
- added preflight conflict/path/template validation before any writes;
- sanitized YAML parse errors to line/column only;
- extended smoke with schema version, required policy value, no-partial-write, and redacted malformed-config cases.
