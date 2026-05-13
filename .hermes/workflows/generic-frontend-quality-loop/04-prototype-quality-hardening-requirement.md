# Requirement: Prototype Quality Hardening

## User correction

用户明确指出：

- Agent 自己生成 HTML 原型的劣势可能大于优势。
- 原型质量必须被保证，因为原型质量很大程度上决定后续真实实现质量。
- 原型阶段应提高质量和约束，目的是减少后续返工。
- 不要 MVP，不要最小版本，要工程化落地。

## Engineering interpretation

The previous baseline proved the loop, but it is not sufficient as a production-quality generic frontend control process.

The generic frontend high-fidelity prototype process must be upgraded from:

```text
single-agent HTML prototype + screenshots + basic gate
```

to:

```text
context pack
-> multi-agent / multi-tool design lanes
-> independent design critique
-> explicit scoring rubric
-> variant comparison
-> human acceptance boundary
-> prototype freeze
-> production parity contract
-> visual regression/runtime evidence
```

## Required hardening

1. C/D frontend work must not rely on one generic agent-generated HTML artifact as the only design source.
2. D risk must require multiple variants and explicit comparison.
3. C risk should require at least one high-quality prototype plus critique; D requires at least two independent directions.
4. Prototype acceptance must include a quality score/rubric, not just existence of files.
5. Low-scoring prototypes must fail the gate even if screenshots exist.
6. Production implementation must not begin until prototype quality gate passes.
7. Concrete project adapters must map this generic process to real tools: Figma/v0/Lovable/Bolt/Storybook/Chromatic/Playwright as available.

## Non-goals

- Do not force every tiny UI patch into this heavy flow.
- Do not require a specific external SaaS for all projects.
- Do not pretend AI visual judgment fully replaces human taste; human acceptance remains a boundary for D-risk work.
