# V Automation Gap Closure Implementation Plan

> **For Hermes:** execute in batched checkpoints; do not report after every small edit unless a human decision, credential, destructive action, or production deploy is required.

**Goal:** Close the remaining gap between scripted QA and automatic hook/watchdog-driven quality governance for V's complex product worktrees.

**Architecture:** Keep SelfCheck generic. V-specific business mapping lives in project adapters, selector config, feature contracts, and worktree batch classifiers. Immature product slices stay quarantined until their gates pass in the same run from the intended roots.

**Tech Stack:** Agentic SelfCheck, Python verifier scripts, Hermes cron/watchdog, Go backend tests, React/Vite frontend typecheck/build.

---

## Slice 1: Product worktree batch status becomes default control-plane signal

Type: AFK
Blocked by: none
User stories / behavior covered:
- Operator sees CrossPlanet and V1 Listing quarantine status in the top-level status projection without manually running a separate script.
- Quarantined product slices produce `PASS_WITH_NOTES`, not a misleading clean `PASS`.

Acceptance criteria:
- `scripts/v_control_plane_status.py` includes `product_worktree_batches` in JSON and Markdown.
- `scripts/v_control_plane_status_smoke.py` asserts the batch section exists and quarantine surfaces as notes.
- `v-control-plane-status` feature references `scripts/v_product_worktree_batch_status.py` and `docs/v-product-worktree-batch-status.md`.

Verifier command:
```bash
cd /root/work/agentic-selfcheck
python3 -m selfcheck loop --root . --feature v-control-plane-status --groups static --timeout 300
```

Evidence path:
- `reports/v-control-plane-status/latest.json`
- `reports/v-control-plane-status/latest.md`

需要郭凯决策: false

---

## Slice 2: V1 Listing/Export dedicated gate

Type: AFK first pass, HITL before merge
Blocked by: product owner merge approval for the quarantined worktree
User stories / behavior covered:
- V1 listing immutability changes are no longer anonymous dirty files.
- Any future listing/export diff maps to a dedicated SelfCheck feature before merge.

Acceptance criteria for first pass:
- Add `ecommerce-v1-listing-export-gate` feature contract.
- Add static verifier that runs from `/root/work/v-worktrees/ecommerce-v1-listing-immutability` and fails closed if backend/frontend roots are missing, if generated lockfile drift is present without explicit adoption, or if required contract files are absent.
- Add selector rule mapping listing/export/productcore/imageRuntime changed files to the new gate.

Future acceptance criteria before merge:
- Backend tests for productcore, imageruntime, migration, templatecenter pass in same run.
- Frontend typecheck/build pass in same run.
- Evidence proves immutable listing version semantics and export/download compatibility.

Verifier command:
```bash
cd /root/work/agentic-selfcheck
python3 -m selfcheck loop --root . --feature ecommerce-v1-listing-export-gate --groups static --timeout 300
```

Evidence path:
- `reports/ecommerce-v1-listing-export-gate/static.json`

需要郭凯决策: true before merging quarantined product worktrees

---

## Slice 3: CrossPlanet gate repair before product merge

Type: AFK first pass, HITL before merge
Blocked by: repaired gate scripts replacing archived hardcoded-root drafts
User stories / behavior covered:
- CrossPlanet/List Strategy worktrees remain visible but cannot slip into mainline under stale/false evidence.
- Gate scripts prove same-run backend/frontend verification from explicit roots.

Acceptance criteria for first pass:
- Add `crossplanet-listing-strategy-gate-repair` feature contract.
- Add static verifier that asserts archived draft gates are not registered as blocking gates and that current CrossPlanet worktrees are quarantined.
- Document repair requirements: no hardcoded root, no stale report dependency, durable browser behavior assertions, generated evidence classification, same-run backend/frontend checks.

Future acceptance criteria before merge:
- Replace archived draft scripts with adapter-root-aware scripts.
- Backend productcore/repository/migration tests pass.
- Frontend typecheck/build pass.
- Browser/API evidence verifies user-visible listing strategy behavior, not internal copy strings.

Verifier command:
```bash
cd /root/work/agentic-selfcheck
python3 -m selfcheck loop --root . --feature crossplanet-listing-strategy-gate-repair --groups static --timeout 300
```

Evidence path:
- `reports/crossplanet-listing-strategy-gate-repair/static.json`

需要郭凯决策: true before merging quarantined product worktrees

---

## Slice 4: Cron delivery and RepairTask hygiene follow-up

Type: AFK unless delivery remains broken
Blocked by: next scheduled delivery or manual cron run
User stories / behavior covered:
- Automation is not just running; the operator can see it ran.
- Historical delivery failures become an explicit status note or RepairTask, not silent uncertainty.

Acceptance criteria:
- Re-run or wait for `V 2h lightweight RepairTask executor` after Hermes Feishu fallback fix.
- If `last_delivery_error` persists, create/keep a delivery-health RepairTask.
- Weekly job remains noted until its next scheduled run or manual run verifies delivery.

Verifier command:
```bash
cd /root/work/agentic-selfcheck
scripts/v_control_plane_status.py --selfcheck-root . --v-root /root/work/v --format json
```

Evidence path:
- `reports/v-control-plane-status/latest.json`

需要郭凯决策: false unless external Feishu permissions fail
