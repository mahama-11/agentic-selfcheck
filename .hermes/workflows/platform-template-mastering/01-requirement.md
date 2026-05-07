# Requirement — platform-template-mastering

## Goal
Move Agent Ecommerce template governance toward the intended architecture:

- Platform owns template metadata / template versions / publishing state / operations console governance.
- Ecommerce consumes published platform templates for business runtime flows.
- Existing local material-analysis pipeline (assets → structured JSON/CSV → import) must be discovered and reused if present.
- If CSV/JSON template fixtures already exist, prefer importing them into Platform rather than re-syncing from Ecommerce local seed.

## Immediate discovery questions

1. Are there existing CSV/JSON structured template files in `/root/work/v`?
2. Are there scripts that parse local material/images/docs into structured CSV/JSON?
3. Does Platform backend already expose admin/internal import endpoints for template metadata?
4. Does Ecommerce backend already contain importer/seed logic that can be inverted or reused?
5. What media/image references are included, and which parts must be deferred to a later media-association slice?

## Target architecture direction

Current accepted baseline:

- `platform-ops-visible-baseline` made Platform Template Ops visible through Ecommerce → Platform projection sync.

Next target:

- Platform template metadata becomes the authoritative source.
- Ecommerce local seed remains only fallback/bootstrap during transition.
- Platform imports structured template source files using stable template codes/refs.
- Ecommerce runtime reads published templates from Platform and stores only product/business usage state.

## Non-goals for first step

- Do not solve all media/file storage associations in this slice.
- Do not copy production secrets or real private media.
- Do not remove Ecommerce fallback until Platform import + runtime consumption is proven.

## Acceptance for discovery stage

- Produce evidence inventory of CSV/JSON/material files.
- Produce evidence inventory of Platform import APIs and Ecommerce seed/parser code.
- Decide whether existing CSV can be directly imported now.
- Define next implementation slice and gate.
