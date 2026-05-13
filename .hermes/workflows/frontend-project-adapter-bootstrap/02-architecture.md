# Architecture — Frontend Project Adapter Bootstrap

`frontend_project_adapter_init.py` is a stdio/CLI harness with three deterministic modes:

1. `--base-check`: verifies repository templates and schema exist and are parseable.
2. default init: copies adapter templates into a target `--project-root`, creating `.cursor/rules/frontend-design.mdc`, `PROJECT_ADAPTER.yaml`, `CLAUDE_FRONTEND_SECTION.md`, `PLAYWRIGHT_COMMANDS.md`, and a managed `CLAUDE.md` section.
3. `--check`: validates an initialized project adapter and required rule/command files.

Safety model:
- all configured paths must be relative and must not contain `..` traversal;
- existing target files fail without `--force`;
- `CLAUDE.md` is only modified with `--force`, using managed markers when possible;
- command registry requires concrete command strings for install/dev/build/typecheck/lint/test/storybook/playwright.
