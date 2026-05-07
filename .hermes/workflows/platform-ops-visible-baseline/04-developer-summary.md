# Developer Summary — platform-ops-visible-baseline

## Completed

- Repaired the live Template Ops convergence path for Ecommerce sync. `/api/v1/template-ops/sync?product_code=ecommerce&locale=zh` now succeeds in the local acceptance runtime and upserts 146 Ecommerce projections.
- Made Template Ops sync resilient to product-side detail gaps: the Platform sync still projects every listed Ecommerce template from the catalog list payload, and stores a documented `catalog_list_fallback` detail payload when an individual product detail endpoint is unavailable.
- Made the SelfCheck gate honest: `template_sync_request_ok` is true only for a successful HTTP sync request, `template_sync_upserted_non_empty` proves non-empty runtime convergence, and persisted projection visibility is tracked separately as `template_ops_persisted_projection_visible`. A failed sync can no longer be hidden by pre-existing rows.
- Removed the new unsafe `202605070001 refresh_ecommerce_visible_baseline` migration so synthetic Ecommerce commercial pricing rows are not re-written by a fresh migration in production-like environments. The Ecommerce commercial visible baseline remains a local/dev startup seed behind explicit `bootstrap.commercial.visible_baselines` and `gin_mode: debug`.
- Kept browser evidence out of this developer repair slice per dispatch; QA will handle authenticated frontend screenshot evidence for `/template-ops` and `/catalog`.

## Reviewer blockers addressed

1. **Template Ops sync HTTP 500 / gate honesty** — CLOSED. Runtime sync now returns HTTP 200 with `upserted_total: 146`; gate status depends on the sync HTTP result and non-empty sync result, not on persisted rows alone.
2. **Fresh/local Template Ops convergence proof** — CLOSED at API/gate level. The gate performs a real sync before assertions and records non-empty upserts, proving the projection path can populate rows from the Ecommerce template catalog seed during runtime.
3. **Production-safe commercial seed behavior** — CLOSED for the newly introduced refresh migration. The non-local/dev-gated refresh migration was removed; local/dev explicit config remains the accepted bootstrap path.
4. **Browser evidence missing** — NOT CLAIMED. Deferred to QA as requested.
5. **Access permission seed changes** — DOCUMENTED. These were pre-existing/unrelated changes from the dev-seed-baseline work and were not broadened in this repair.

## Runtime-visible baseline verified

The local Platform API gate now reports:

- Template Ops sync: HTTP 200, upserted 146 Ecommerce projections.
- Template projection catalog: 146 Ecommerce rows with semantic projection fields.
- Ecommerce product exists.
- SKUs: 5
- Packages: 5
- Billable items: 1 (`ecommerce.image.generate`)
- Rate cards: 6 with both `sku` and `billable_item` target types.
- Wallet assets: 4
- Quota policies: 5
- Offerings payload present.

## Validation run

From `/root/work/v/platform-backend`:

```bash
/usr/local/go/bin/gofmt -w internal/modules/templateops/service.go internal/modules/templateops/service_test.go internal/migration/migration.go internal/modules/commercial/ecommerce_visible_baseline.go internal/modules/commercial/bootstrap.go
/usr/local/go/bin/go test ./internal/modules/templateops ./internal/migration ./internal/modules/catalog ./internal/modules/access ./internal/modules/commercial ./internal/modules/devseed
```

Result: PASS.

From `/root/work/agentic-selfcheck`:

```bash
python3 -m py_compile scripts/platform_ops_visible_baseline_gate.py
python3 -m selfcheck validate --root .
python3 scripts/platform_ops_visible_baseline_gate.py --project v-workspace --feature platform-ops-visible-baseline --report reports/platform-ops-visible-baseline/platform-ops-visible-baseline-gate.json
scripts/project_api_smoke.sh v-workspace platform-ops-visible-baseline
```

Result: PASS.

## Notes

- The repaired gate report is at `reports/platform-ops-visible-baseline/platform-ops-visible-baseline-gate.json` and shows `template_ops_sync.status = 200`, `template_ops_sync.ok = true`, and `template_ops_sync.upserted_total = 146`.
- No passwords or tokens were printed in gate output.
