# 01 Requirements — frontend-prototype-parity-gate

Status: PASS

## Goal
Implement the Prototype-to-Production Parity Gate tranche from `docs/plans/frontend-autonomy-long-lane.md`.

## Acceptance requirements
- Create strict parity report schema, gate script, smoke script, template, feature, and verifier.
- Require accepted/frozen prototype evidence (`prototype-freeze.json` and optional PASS freeze gate result) before parity can pass.
- Require real production screenshot PNG evidence under workflow `production-screenshots/` using strict PNG parsing, not header-only/JPEG/WebP acceptance.
- Fail closed on missing screenshots/report, malformed/extra fields, score below default 80 threshold, scores above schema maximum, unapproved material deviations, route/surface coverage gaps, visual parity bypass by contract-needed exceptions, and path traversal.
- Support documented contract-needed exceptions only for non-visual scope.
- Include positive C/D smoke cases and negative cases for missing freeze, missing production screenshot, below threshold, over-100 score, unapproved material deviation, D-risk non-human material deviation, coverage gap, malformed extra/nested fields, fake PNG, path traversal, and visual-bypass exception.
- Pass SelfCheck validate/audit/static verifier after independent reviews and repairs.
