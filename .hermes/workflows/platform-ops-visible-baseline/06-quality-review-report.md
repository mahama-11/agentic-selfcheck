# Quality / Security Re-review — platform-ops-visible-baseline

Role: Quality/Security Reviewer
Timestamp: 2026-05-07T12:19:50+08:00
Review status: **APPROVED_FOR_QA**

## Scope reviewed

Inputs read:

- `05-spec-review-report.md`
- Previous `06-quality-review-report.md`
- `04-developer-summary.md`
- `09-repair-events.md`
- `reports/platform-ops-visible-baseline/platform-ops-visible-baseline-gate.json`

Code/gate areas spot-checked without editing product code:

- `/root/work/v/platform-backend/internal/migration`
- `/root/work/v/platform-backend/internal/modules/templateops`
- `/root/work/agentic-selfcheck/scripts/platform_ops_visible_baseline_gate.py`

## Validation performed in re-review

```bash
# Confirm unsafe refresh migration name is gone
search_files: refresh_ecommerce_visible_baseline under /root/work/v/platform-backend/internal/migration
```

Result: **0 matches**.

```bash
cd /root/work/v/platform-backend
/usr/local/go/bin/go test ./internal/modules/templateops ./internal/migration ./internal/modules/catalog ./internal/modules/access ./internal/modules/commercial ./internal/modules/devseed
```

Result: **PASS**.

```bash
cd /root/work/agentic-selfcheck
python3 -m py_compile scripts/platform_ops_visible_baseline_gate.py
python3 -m selfcheck validate --root .
python3 scripts/platform_ops_visible_baseline_gate.py --project v-workspace --feature platform-ops-visible-baseline --report /tmp/platform-ops-visible-baseline-rereview-gate.json
```

Results:

- `py_compile`: **PASS**
- `selfcheck validate`: **PASS: no issues**
- Gate rerun: **PASS**

Gate rerun evidence:

- `checks.template_ops_sync.status = 200`
- `checks.template_ops_sync.ok = true`
- `checks.template_ops_sync.upserted_total = 146`
- `expectations.template_sync_request_ok = true`
- `expectations.template_sync_upserted_non_empty = true`
- `expectations.template_ops_persisted_projection_visible = true`
- Catalog expectations for Ecommerce product/SKU/package/billable item/rate card/wallet asset/quota policy/offering are all true.

## Summary judgment

The developer repair closes the quality/security blockers that previously prevented handoff to QA.

The prior blocking issues were:

1. Gate masking a failed Template Ops sync HTTP 500 behind persisted rows.
2. Fresh/local Template Ops convergence risk.
3. Unsafe non-local/dev-gated commercial refresh migration.
4. Scope concern around access seed changes.

After re-review, the gate now proves a real sync request succeeds and reports non-empty upserts before passing, the sync endpoint is HTTP 200 with `upserted_total = 146`, persisted projection visibility is tracked separately, and the unsafe `refresh_ecommerce_visible_baseline` migration is absent from `internal/migration`.

Browser evidence is intentionally left for QA next. I am not blocking this re-review only because authenticated frontend screenshots for `/template-ops` and `/catalog` are not yet present; that is the next QA responsibility rather than a remaining implementation/gate-integrity blocker.

## Findings from previous review

### F1 — Gate masks a failed Template Ops sync as success

Previous severity: **High**
Current disposition: **Closed**

Evidence:

- Repaired gate uses distinct expectations:
  - `template_sync_request_ok`
  - `template_sync_upserted_non_empty`
  - `template_ops_persisted_projection_visible`
- Gate status is `PASS` only if all expectations are true.
- Rerun gate shows Template Ops sync HTTP **200**, `ok = true`, and `upserted_total = 146`.
- Gate notes explicitly state persisted projection visibility cannot mask sync failure.

Assessment: the gate semantics are now honest enough for QA handoff.

### F2 — Fresh local/dev Template Ops convergence is not established

Previous severity: **High**
Current disposition: **Closed at API/gate level**

Evidence:

- The acceptance gate performs a live sync call to `/api/v1/template-ops/sync?product_code=ecommerce&locale=zh`.
- The sync now succeeds and upserts 146 Ecommerce projections.
- The Template Ops catalog then returns 146 persisted Ecommerce projections with semantic fields.

Assessment: fresh browser confirmation still belongs to QA, but the runtime API convergence blocker is closed.

### F3 — Ecommerce commercial refresh migration is not local/dev-gated and may overwrite real data

Previous severity: **High**
Current disposition: **Closed for this slice**

Evidence:

- Search under `/root/work/v/platform-backend/internal/migration` found no `refresh_ecommerce_visible_baseline` references.
- `git diff -- internal/migration/migration.go` is empty in re-review, so the previously reviewed new migration entry is no longer present.
- Developer summary states the commercial visible baseline remains behind explicit local/dev startup config and `gin_mode: debug`.

Assessment: the production-safety blocker introduced by the refresh migration is closed. Forceful commercial baseline upsert behavior remains acceptable only in the explicit local/dev bootstrap path.

### F4 — Commercial seed idempotency overwrite semantics broader than count idempotency

Previous severity: **Medium**
Current disposition: **Accepted with local/dev constraint**

Assessment: the main risk was production-like execution through an unconditional migration. With that migration removed and bootstrap remaining debug/local-dev scoped, this is no longer a QA-blocking issue.

### F5 — Local/dev identity seed default weak admin password

Previous severity: **Medium**
Current disposition: **Accepted with caution / not blocking QA**

Assessment: this remains a local/dev operational hygiene concern. The gate report does not print password/token values, and this issue is not specific enough to block QA of the visible baseline. Keep default-password usage confined to local ignored config and prefer `PLATFORM_DEV_ADMIN_PASSWORD`.

### F6 — Tracked dev config contains development secrets and enables Ecommerce commercial baseline

Previous severity: **Medium**
Current disposition: **Accepted as non-production dev config / not blocking QA**

Assessment: no new evidence of real secret leakage was found in this repair. The relevant visible-baseline execution path remains gated by debug/local-dev behavior.

### F7 — Access permission seed changes broader than stated requirement

Previous severity: **Medium**
Current disposition: **Not a blocker for this repair handoff**

Assessment: developer states these changes are pre-existing/unrelated from the dev-seed-baseline work and were not broadened in this repair. I did not find a new repair-introduced access expansion that should block this platform-ops QA handoff. Keep this as a scope/documentation watch item for the owning dev-seed/access-control slice.

### F8 — Template Ops adapter route fix reasonable but live failure meant insufficient coverage

Previous severity: **Medium**
Current disposition: **Closed**

Evidence:

- Template Ops sync now returns HTTP 200 in the acceptance runtime.
- Service code includes a catalog-list fallback for unavailable detail endpoints, preventing individual detail gaps from failing the full convergence path.
- Template Ops package tests pass.

Assessment: sufficient for QA handoff.

## Residual risks / QA focus

These items should be carried into QA, but they do not block this quality/security re-review verdict:

1. **Browser evidence still required.** QA must log in through the Platform frontend and capture authenticated evidence that `/template-ops` shows Ecommerce templates and `/catalog` shows non-empty Ecommerce product/SKU/package/billable/rate-card data.
2. **Fallback detail payload quality.** The API convergence is acceptable, but QA should spot-check that list-fallback projections render useful names/images/metadata in the frontend and do not show raw/internal error details.
3. **Local default credential hygiene.** Ensure screenshots/logs do not expose passwords or tokens, and prefer environment-provided local admin password where possible.

## Verdict

**APPROVED_FOR_QA**

The developer repair closes the quality/security blockers sufficiently to proceed to QA. Final product acceptance still depends on QA browser verification and screenshot evidence for the authenticated Platform frontend paths required by the original requirement.
