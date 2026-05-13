# Requirement: Frontend Design Quality Pack Gate

## User intent

用户确认需要系统吸收外部 AI 前端方案的优点，不要 MVP，不要一次性口头规划，而要合理分层并开始工程化落地。

本 slice 聚焦路线图的第一步：在 AI 生成高保真原型之前，先建立 Design Quality Pack 前置门禁。

## Why this matters

外部方案共识：AI 前端质量不是靠模型自由发挥保证，而是靠：

```text
reference/context
+ design system/tokens/components
+ persistent rules
+ multi-lane generation
+ screenshot critique
+ visual regression
```

当前我们已有生成后的 critique/scorecard/gate，但生成前约束仍不足。Design Quality Pack 负责把审美、一致性、专业性的上游输入结构化。

## Scope

Create generic, project-agnostic control-plane assets:

- Design Quality Pack templates.
- JSON schema.
- Python gate script.
- SelfCheck feature and verifier.
- Integration with frontend workflow initializer.
- Positive and negative smoke workflows.

## Required Design Quality Pack artifacts

- `REFERENCE_PACK.md`
- `AESTHETIC_DIRECTION.md`
- `ANTI_PATTERNS.md`
- `DESIGN_TOKENS_MAP.md`
- `COMPONENT_INVENTORY.md`
- `REFERENCE_SCREENSHOTS.md`
- `PROJECT_FRONTEND_RULES.md`

## Gate rules

For C-risk frontend work:

- All artifacts exist and are non-empty.
- At least 2 reference entries.
- At least 1 anti-pattern.
- Tokens/components are either declared or explicitly marked `contract_needed`.
- Project rules exist.

For D-risk frontend work:

- All C rules.
- At least 3 reference entries.
- At least 3 anti-patterns.
- At least 2 real reference screenshot images or explicit `external_reference_only` waiver with rationale.
- Human/design review boundary must be declared.

## Non-goals

- Do not force a specific SaaS like Figma/v0/Lovable.
- Do not require every tiny UI change to use this heavy flow.
- Do not generate production UI in this slice.

## Acceptance criteria

- `python3 -m selfcheck validate --root .` PASS.
- `frontend_design_quality_pack_gate.py` base check PASS.
- Good C sample PASS.
- Good D sample PASS.
- Bad missing references FAIL.
- Bad missing anti-patterns for D FAIL.
- SelfCheck feature run PASS.
