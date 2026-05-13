<!-- agentic-selfcheck:frontend-project-adapter:start -->
## Frontend Quality Adapter

This project uses the Agentic SelfCheck frontend quality lane for C/D-risk UI work.

Required behavior:
1. Read `PROJECT_ADAPTER.yaml` before changing frontend code.
2. Use `.cursor/rules/frontend-design.mdc` as persistent design rules.
3. Use `PLAYWRIGHT_COMMANDS.md` for local build, Storybook, and browser evidence commands.
4. Require prototype freeze evidence before production implementation when a workflow is classified C/D risk.
5. Do not overwrite human-authored frontend rules or command files unless an explicit force operation is being performed.
6. Record screenshots, review reports, and verification output under `.hermes/workflows/<workflow-id>/`.
<!-- agentic-selfcheck:frontend-project-adapter:end -->
