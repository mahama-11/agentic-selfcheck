# Product Surface Language Rules

Internal governance, engineering uncertainty, and implementation details must not leak into user-facing prototype UI.

## Forbidden user-visible terms

Do not show these or close variants as product copy:

- V1 / V2 / V3 as internal version labels
- Stage
- contract-needed
- backend gap / API gap
- gate / verifier / coverage / selfcheck
- model provider
- GPU / TFlops / inference engine implementation detail
- Test001 / Test002 / Test003
- Execution Sandbox
- Reactive Decision Tree
- Dual-Track Extraction
- internal review status such as “评审通过”, “当前成熟度”, “暴露问题”

## Translation rules

| Internal concept | User-facing language |
|---|---|
| contract-needed | Hide, or show a limited product state without internal wording |
| backend job pending | 正在处理 / 正在分析 / 请稍后 |
| API unavailable | 暂不可用 / 稍后重试 |
| intent spec | 生成方向 |
| prompt plan | 生成方案 |
| variant group | 候选方案 |
| final asset | 已保存结果 |

## Requirement

Every prototype artifact must be scanned for forbidden internal language before user review.
