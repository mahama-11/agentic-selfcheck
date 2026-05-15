# Project Context

## Existing product background

Describe what product/project this frontend belongs to. Do not start from a blank-canvas design unless this is truly a new product.

Required:
- Product purpose:
- Target users:
- Current business workflow:
- Where this increment fits in the existing workflow:
- What must remain true after the increment:

## Current implementation state

Record the current reality before prototype/design generation.

Required:
- Existing routes/pages affected:
- Existing components/layouts/shells to preserve:
- Existing service/API/data contracts:
- Existing states already implemented:
- Known missing capabilities, marked `contract-needed`:

## Current visual and interaction baseline

Record the project’s current visual system and interaction patterns.

Required:
- Theme / color / typography / spacing direction:
- Navigation shell and page chrome:
- Existing cards/tables/drawers/modals/steppers patterns:
- Reference screenshots from the live/current product:
- What visual style must not be broken:

## Prototype maturity goal and assessment

Declare the intended maturity goal and then assess the actual output honestly:

```yaml
prototype_maturity_goal: stage_4
current_maturity_assessment: stage_2 # stage_1 | stage_2 | stage_3 | stage_4
```

Stage definitions:
- `stage_1`: reviewable prototype exists.
- `stage_2`: prototype is grounded in business/project context.
- `stage_3`: stage_2 + coherent interaction/user-journey closure.
- `stage_4`: stage_3 + API/backend/data feasibility mapping for every major function.

Important rule:
- This is not a plan to produce four separate prototype versions.
- Serious C/D frontend prototypes should aim for `stage_4` in one pass.
- If the actual output falls short, record the current stage and gaps to stage_4.

Current maturity assessment:
- Goal:
- Actual current stage:
- Evidence:
- Gaps to stage_4:

## Target increment goal

Connect the new requirement to the existing product.

Required:
- New user job:
- New or changed user flow:
- Required route/surface coverage:
- Required state coverage:
- Success definition:

## Business logic and interaction backbone

Before visual layout generation, extract the product workflow skeleton. Do not simplify the UI by deleting business logic; simplify by progressively revealing it.

Required:
- Core business objects involved:
- End-to-end user flow, from entry to final saved/exported result:
- Step-by-step interaction model:
- Required progressive disclosure surfaces: modal / drawer / tab / stepper / selection / detail page:
- Critical states: empty / loading / parsing / selected / failed / retry / saved / synced:
- What complexity is hidden by default but still reachable:

## System feasibility map

For every major visible function, map whether the existing project can support it today.

Required table fields:
- Visible user function:
- Existing frontend route/component/state support:
- Existing backend/API/data support:
- Missing contract or required adaptation, marked `contract-needed`:
- Risk if prototype shows it but implementation cannot support it:

## User-facing product UI boundary

Internal review concepts must stay in internal docs, not in the product UI.

Forbidden in user-facing prototype UI:
- V1 / V2 / V3 / Stage labels used as user-visible product copy;
- `contract-needed`, backend/API gap, gate, verifier, coverage, maturity, selfcheck;
- model/provider/GPU/TFlops/inference-engine implementation details;
- internal bug/status wording such as “暴露问题”, “当前成熟度”, “评审通过”.

Required:
- Translate internal state into user language:
  - `contract-needed` -> omit from UI; document internally.
  - parsing job -> 正在分析素材.
  - intent spec -> 生成方向.
  - prompt plan -> 生成方案.
  - variant group -> 候选图组.
  - final asset -> 已保存图片.
- If a capability is not actually supported, either hide it from user UI or present it as a clearly limited product state; do not fake completion.

## Prototype grounding rule

The prototype must be grounded in the existing product context. It may improve visual/interaction quality, but it must not become a detached standalone concept or “虚空打靶” demo.
