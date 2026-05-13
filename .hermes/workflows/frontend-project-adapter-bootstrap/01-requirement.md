# Requirement: frontend-project-adapter-bootstrap

Status: ACTIVE

## User intent

The user explicitly asked that the overall frontend autonomy system continue landing instead of stopping after each step. This tranche makes the generic frontend quality control-plane consumable by real projects via project-local adapters and persistent rules.

## Scope

- Generic adapter initializer for arbitrary frontend project roots.
- Persistent project files: `PROJECT_ADAPTER.yaml`, Cursor frontend rule, Claude frontend section, Playwright/command registry.
- Fail-closed checks for overwrite safety, malformed config, missing required commands/rules, path traversal, and force semantics.
- SelfCheck feature/verifier/smoke integration.

## Non-goals

- Do not fill project-specific credentials or secrets.
- Do not auto-run destructive project migrations.
- Do not claim a project has real Storybook/Playwright if the adapter only records command contracts.

## Acceptance

- `scripts/frontend_project_adapter_init.py` can initialize and check a temp project.
- Existing human-authored files are not overwritten without `--force`.
- `--force` has explicit, tested semantics.
- `PROJECT_ADAPTER.yaml` validates against schema.
- Smoke covers positive and negative cases.
- SelfCheck validate/audit/run pass.
