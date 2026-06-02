# V Product Worktree Batch Status

This checkpoint records the post-Batch-A cleanup posture for the remaining product-side worktrees. It is intentionally a batching map, not a merge approval.

Generated helper:

```bash
cd /root/work/agentic-selfcheck
scripts/v_product_worktree_batch_status.py --format text
```

## Batch B — environment/dependency noise

Status: PASS.

Current state:

- `/root/work/v/platform-frontend`: clean after committing the explicit `typecheck` script.
- `/root/work/v/menu-frontend`: clean after restoring the deleted tracked `.env`.
- `/root/work/v/kyc-backend`: clean after adding global git `safe.directory` for inspection.
- `/root/work/v/kyc-frontend`: clean after adding global git `safe.directory` for inspection.

Decision:

- Environment noise is cleared.
- No product behavior should be inferred from this batch.
- Future dependency/tooling changes must run project-native verification before commit.

## Batch C — CrossPlanet/List Strategy

Status: QUARANTINED.

Current state:

- `/root/work/v-worktrees/crossplanet-listing-strategy-backend`: 5 dirty files.
- `/root/work/v-worktrees/crossplanet-listing-strategy-frontend`: 9 dirty files.
- Existing SelfCheck draft remains archived under `/root/.hermes/archive/agentic-selfcheck-crossplanet-draft-20260522-200831`.

Decision:

- Do not merge CrossPlanet product worktrees yet.
- Do not register the archived CrossPlanet gates as blocking gates until they are repaired.
- Required repairs before merge consideration:
  1. gate scripts must avoid hardcoded false roots and accept explicit project/worktree roots;
  2. verifier commands must not depend on stale report files as proof of current pass;
  3. browser/copy checks must assert durable user-facing behavior, not brittle internal strings;
  4. evidence checks must distinguish required governance evidence from generated/transient workflow files;
  5. backend and frontend worktrees must pass their own tests/typecheck/build in the same run.

## Batch D — Ecommerce V1 listing immutability

Status: QUARANTINED / ACTIVE LARGE SLICE.

Current state:

- Backend worktree has 11 dirty files across migration, models, image runtime, productcore, templatecenter, repository, router, and docs.
- Frontend worktree has 8 dirty files across product detail UI, image runtime/product services, product types, i18n, Vite config, and a generated `pnpm-lock.yaml`.

Decision:

- Treat this as an active large product slice, not as cleanup noise.
- Do not fold it into unrelated platform/ecommerce runtime work.
- Required next step is a dedicated listing/export gate, covering:
  - immutable listing version semantics;
  - productcore create/update/read compatibility;
  - image runtime linkage;
  - frontend product detail contract;
  - i18n copy and build/typecheck;
  - no generated package-manager lockfile drift unless intentionally adopting pnpm.

## Batch E — control-plane hygiene entry

Current known notes:

- `v-control-plane-status` remains `PASS_WITH_NOTES`.
- Notes are expected from active RepairTask backlog and historical Feishu delivery errors.
- Product dirty worktrees are now explicitly classified rather than being treated as anonymous noise.

Next hygiene target:

- Use `scripts/v_product_worktree_batch_status.py` in status summaries so Batch C/D quarantine remains visible but does not block unrelated clean batches.
