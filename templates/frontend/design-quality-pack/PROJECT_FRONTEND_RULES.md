# Project Frontend Rules

## Persistent agent rules

These rules must be copied/adapted into project-specific durable rule files where possible:

- `CLAUDE.md` frontend section
- `.cursor/rules/frontend-design.mdc`
- project docs / agent rules

## Rules

- C/D-risk frontend work must not enter implementation before prototype gate PASS.
- Existing-product frontend increments must start with `PROJECT_CONTEXT.md`: background, current state, style/route/API constraints, live/current screenshots, and target goal before prototype generation.
- Prototypes for existing products must be grounded in the current product shell and workflow; no standalone “虚空打靶” demos unless the task is explicitly a new-product exploration.
- Use existing design tokens and components first.
- Do not introduce raw colors, new shadows, new spacing scales, or new component primitives without approval.
- Use real copy and realistic data; avoid lorem ipsum and fake capabilities.
- Generate screenshots for desktop and relevant responsive widths.
- Compare production implementation to accepted prototype screenshots.
- Document accepted deviations.

## Human review boundary

For D-risk work, human/product sign-off is required before production implementation.

```yaml
human_review_boundary: required_for_D
```
