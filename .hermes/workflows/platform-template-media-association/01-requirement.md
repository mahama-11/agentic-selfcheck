# Requirement — platform-template-media-association

## Goal

Close or precisely explain the `missingAssetCount: 173` gap from `platform-template-mastering` by resolving Ecommerce template example image paths into Platform prepared asset imports and Template Ops asset bindings.

Target direction:

```text
local example images / material references
  -> prepared asset manifest with resolvable sourcePath
  -> Platform asset storage import
  -> Template Ops template asset bindings / preview-ready metadata
  -> Ecommerce consumes Platform-published template metadata with associated example/cover assets where available
```

## Scope

- Discover where Ecommerce template example images currently live, if present.
- Repair path resolution if images exist but exporter uses wrong root/layout.
- Preserve stable `sourceRef`, `assetRef`, `template_ref`, and storage file names.
- Import prepared assets through Platform API/service path; do not copy files into DB manually.
- Make media gaps explicit if files are genuinely absent.
- Add SelfCheck evidence/gate for asset manifest readiness/import result.

## Non-goals

- CDN/public hosting policy.
- Full rich media lifecycle/moderation/replacement workflow.
- Manual image generation or sourcing if files are absent.
- Renaming `template_projections` schema.
- Production import automation.

## Acceptance

PASS only if one of these is true with evidence:

1. **Asset association PASS**
   - Manifest source paths resolve for existing local images.
   - Prepared asset import succeeds for expected available images.
   - Template Ops preview/detail exposes associated asset records/bindings.
   - SelfCheck gate validates counts and no hidden missing assets.

2. **Asset source BLOCKED_WITH_EVIDENCE**
   - Local image files are demonstrably absent.
   - Code/gate accurately reports missing files and the exact expected paths/source refs.
   - No false PASS claiming media association.

## Safety

- No secrets/passwords/tokens in reports.
- Do not use production media or credentials.
- Avoid destructive file/database operations.
- Generated artifacts must be reproducible.
