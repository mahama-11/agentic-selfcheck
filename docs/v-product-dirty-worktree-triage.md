# V Product Dirty Worktree Triage

Generated for staged control-plane optimization. This document is not a claim that product changes are complete; it is a batching map for the next engineering passes.

## Current product-side state

```text
ecommerce-frontend: clean
ecommerce-backend: 5 dirty
platform-backend: 5 dirty
platform-frontend: 1 dirty
menu-backend: clean
menu-frontend: 1 dirty (.env deleted)
kyc-backend / kyc-frontend: git safe.directory issue blocks reliable status
crossplanet backend worktree: 5 dirty
crossplanet frontend worktree: 9 dirty
ecommerce-v1-listing-immutability frontend worktree: 8 dirty
```

## Batch A — release/runtime risk, existing gates can evaluate

Repos:
- `/root/work/v/ecommerce-backend`
- `/root/work/v/platform-backend`

Observed dirty surfaces:
- `ecommerce-backend/internal/modules/visualworkflow/service.go`
- `ecommerce-backend/internal/modules/visualworkflow/service_test.go`
- `ecommerce-backend/docs/PROD_DEPLOY_RUNBOOK.md`
- `ecommerce-backend/tools/prod/ecommerce-deploy.sh`
- `ecommerce-backend/Dockerfile.local-binary`
- `platform-backend/internal/modules/runtime/provider_minimax_image.go`
- `platform-backend/internal/modules/runtime/provider_minimax_image_test.go`
- `platform-backend/Dockerfile`
- `platform-backend/docs/PROD_DEPLOY_RUNBOOK.md`
- `platform-backend/tools/prod/platform-deploy.sh`

Existing gate coverage:
- `ecommerce-v2-prep-sandbox-lowlevel`
- `ecommerce-critical-journey-release-gate`
- Working-tree watchdog has already classified these signatures as previously passed.

Next pass:
1. Review diffs for prod deploy/config preservation and runtime provider behavior.
2. Rerun the two Ecommerce gates from the intended roots.
3. If prod deployment is involved, do not deploy without explicit approval.
4. Commit product work separately from SelfCheck control-plane changes.

## Batch B — platform/menu environment hygiene

Repos:
- `/root/work/v/platform-frontend`
- `/root/work/v/menu-frontend`

Observed dirty surfaces:
- `platform-frontend/package.json`
- `menu-frontend/.env` deleted

Current gate coverage:
- Selector reports `NO_BUSINESS_GATES` for both.

Risk:
- `package.json` may affect build/runtime/tooling but is not currently mapped.
- `.env` deletion can be intentional cleanup or accidental environment breakage; do not auto-restore or delete without inspection.

Next pass:
1. Inspect diffs and determine whether changes are tooling-only or runtime-affecting.
2. Add selector advisory/blocking rule for platform frontend package/runtime changes if needed.
3. Decide `.env` policy: ignored local file vs committed template vs accidental deletion.

## Batch C — CrossPlanet/List Strategy draft worktrees

Repos:
- `/root/work/v-worktrees/crossplanet-listing-strategy-backend`
- `/root/work/v-worktrees/crossplanet-listing-strategy-frontend`

Observed dirty surfaces:
- Backend productcore/model/migration/template repository changes.
- Frontend product detail, batch listing, account templates/downloads, services/types changes.

Current gate coverage:
- Draft CrossPlanet gates are quarantined, not mainline blocking.

Known blockers before promotion:
- Verifier commands/scripts permissions.
- Mixed root/evidence path handling.
- False-negative API struct inspection.
- Browser copy checks too brittle/i18n-sensitive.
- Product worktrees not committed with matching evidence.

Next pass:
1. Fix gate scripts first, not product code first.
2. Align project root and evidence root.
3. Re-review product diffs after gate passes.
4. Only then promote selector rules.

## Batch D — Ecommerce V1 listing immutability worktree

Repo:
- `/root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-frontend`

Observed dirty surfaces:
- i18n, product detail, image runtime service, product service/types, Vite config, lockfile.

Current gate coverage:
- Not part of current mainline selector.

Next pass:
1. Clarify whether this worktree is still active or stale.
2. If active, define feature contract before committing.
3. If stale, archive or reset after confirmation.

## Batch E — KYC repository discovery

Repos:
- `/root/work/v/kyc-backend`
- `/root/work/v/kyc-frontend`

Issue:
- Git reports dubious ownership; reliable status is unavailable until safe.directory/ownership is resolved.

Next pass:
1. Inspect ownership and decide whether to add safe.directory.
2. Only after reliable status, design KYC gates.

## Immediate recommendation

Next actionable engineering batch should be Batch A, because it has real runtime/release risk and existing gates. Batch B is a small hygiene/routing fix. Batch C should remain quarantined until its gates are repaired.
