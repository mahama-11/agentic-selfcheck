# External Research: AI Frontend Prototype Quality Assurance

## Purpose

用户要求搜索互联网方案，特别是 AI 做前端项目时，如何保证原型的审美、一致性、专业性。

## Sources reviewed

- v0 Docs: https://v0.dev/docs
- v0 Screenshots workflow: https://v0.dev/docs/screenshots
- v0 Figma workflow: https://v0.dev/docs/figma
- v0 Design Systems: https://v0.dev/docs/design-systems
- Lovable best practices: https://docs.lovable.dev/tips-tricks/best-practice.md
- Lovable design guidance: https://docs.lovable.dev/features/design-guidance.md
- Lovable design systems: https://docs.lovable.dev/features/design-systems.md
- Lovable design templates: https://docs.lovable.dev/features/business/design-templates.md
- Figma Dev Mode MCP: https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Dev-Mode-MCP-Server
- Figma Code Connect: https://help.figma.com/hc/en-us/articles/23920389749655-Code-Connect
- Style Dictionary design tokens: https://styledictionary.com/info/tokens/
- Storybook visual testing: https://storybook.js.org/docs/writing-tests/visual-testing.md
- Chromatic Storybook visual tests: https://www.chromatic.com/docs/storybook/
- Playwright visual comparisons: https://playwright.dev/docs/test-snapshots
- Cursor rules: https://cursor.com/docs/rules
- Claude Code best practices: https://docs.anthropic.com/en/docs/claude-code/best-practices.md

## Main finding

AI frontend quality is not guaranteed by asking the model to “make it beautiful”. Mature workflows use constraints and feedback loops:

```text
reference/context
+ design system/tokens/components
+ persistent agent rules
+ multi-lane generation
+ screenshots/visual critique
+ visual regression
+ human acceptance for high-risk work
```

## Patterns

### 1. AI must not start from blank context

Tools such as v0 and Lovable emphasize screenshots, Figma, design systems, project knowledge, mockups, wireframes, and existing UI guidance.

Implication:

```text
Every C/D prototype task needs a Reference Pack and Design Quality Pack before generation.
```

### 2. Multiple design lanes raise quality ceiling

Lovable design guidance uses multiple lightweight HTML directions before full implementation.

Implication:

```text
D-risk work should require multiple independent lanes and explicit comparison.
```

### 3. Design systems are quality infrastructure

Lovable design systems, Figma Code Connect, Figma MCP, Style Dictionary, Storybook and Chromatic all move quality from taste into reusable constraints.

Implication:

```text
Prototype generation must know project tokens/components/templates; otherwise AI invents inconsistent UI.
```

### 4. Persistent rules beat one-off prompts

Cursor rules and CLAUDE.md encode durable project rules.

Implication:

```text
Generic frontend rules should be generated into project adapter rules, not only kept as docs.
```

### 5. Screenshots and visual regression make visual quality auditable

Storybook, Chromatic and Playwright use screenshots/baselines to catch drift.

Implication:

```text
Prototype quality gate should produce and preserve screenshot baselines, then production implementation must compare against them.
```

### 6. AI visual review must be structured

Claude Code best practices recommend screenshoting results, comparing to targets, listing differences, and fixing.

Implication:

```text
Our visual-critique.json + scorecard direction is aligned with external best practices, but should be tied to reference screenshots and target/actual comparison.
```

## Required next improvements to our control plane

1. Add `REFERENCE_PACK.md` template.
2. Add `DESIGN_QUALITY_PACK.md` or split into:
   - `DESIGN_TOKENS_MAP.md`
   - `COMPONENT_INVENTORY.md`
   - `AESTHETIC_DIRECTION.md`
   - `ANTI_PATTERNS.md`
   - `REFERENCE_SCREENSHOTS.md`
3. Add project-level persistent rules template:
   - `.cursor/rules/frontend-design.mdc`
   - `CLAUDE.md` frontend section
   - optional Lovable/v0 knowledge instructions.
4. Strengthen D-risk lane generation:
   - conservative lane;
   - strong-fit lane;
   - divergent lane.
5. Extend `visual-critique.json` to include comparison against references, not just standalone evaluation.
6. Add visual baseline artifact:
   - prototype baseline screenshots;
   - production screenshots;
   - prototype-vs-production parity report.
7. For concrete projects, connect Storybook/Chromatic/Playwright where available.

## Conclusion

The external consensus matches our direction but implies one missing upstream layer:

```text
Design Quality Pack before prototype generation.
```

Without this, critique/gate can reject bad work, but generation still starts underconstrained. The next engineering step should be to add that upstream pack and make it required for C/D tasks.
