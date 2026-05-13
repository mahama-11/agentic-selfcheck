# Frontend Command Registry

Keep these commands concrete for the current project. Replace the defaults with package-manager specific commands during adapter setup.

| Purpose | Command |
| --- | --- |
| Install dependencies | `npm install` |
| Development server | `npm run dev` |
| Production build | `npm run build` |
| Typecheck | `npm run typecheck` |
| Lint | `npm run lint` |
| Unit/component tests | `npm test` |
| Storybook | `npm run storybook` |
| Playwright/browser evidence | `npx playwright test` |

Evidence expectations:
- Store screenshots/manifests under `.hermes/workflows/<workflow-id>/` or a path listed in `PROJECT_ADAPTER.yaml`.
- Browser evidence commands must be runnable without credentials for deterministic static gates.
- If a command is intentionally unavailable, record a human-owned exception in the workflow rather than deleting the command key.
