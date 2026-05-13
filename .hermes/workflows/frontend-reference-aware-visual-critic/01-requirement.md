# Requirement: frontend-reference-aware-visual-critic

## Scope

Land the next frontend AI quality-loop slice: visual critique must be checked against the upstream Design Quality Pack, not only standalone screenshots.

## Acceptance

- Add reference-aware critique schema and validator/materializer.
- Validator requires Design Quality Pack prerequisite and passable `visual-critique.json` source.
- Validator checks references used, aesthetic alignment, anti-pattern violations, token/component fit, project rule alignment, thresholds, and fail-closed status.
- Prototype quality gate requires `reference-aware-critique.json` before acceptance.
- SelfCheck feature/verifier runs positive and negative smoke cases.

## Non-goals

- No live vision API invocation in this slice.
- No production frontend changes.
- No JPEG/WebP screenshot decoder work.
