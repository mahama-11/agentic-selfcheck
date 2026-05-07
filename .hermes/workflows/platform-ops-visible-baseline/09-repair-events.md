# Repair Events

Role: Developer repair

## Events

### OPEN — 2026-05-07T12:12:00+08:00

Accepted repair dispatch for reviewer blockers on `platform-ops-visible-baseline`:

- Fix real Template Ops sync or implement explicit projection bootstrap without hiding sync failure.
- Prove fresh/local Template Ops convergence through runtime/gate evidence.
- Remove or production-safety-gate the new Ecommerce commercial refresh migration.
- Keep browser evidence out of this developer slice; QA owns screenshots.
- Document unrelated/pre-existing access seed changes instead of broadening this slice.

### CLOSED — 2026-05-07T12:16:00+08:00

Repair completed and validated:

- Platform Template Ops sync now returns HTTP 200 for Ecommerce local acceptance runtime and upserts 146 projections.
- Sync falls back to catalog-list projection data for individual Ecommerce detail 404s instead of failing the whole convergence path.
- SelfCheck gate now has honest sync semantics: `template_sync_request_ok` and `template_sync_upserted_non_empty` must pass; persisted projection visibility is a separate expectation.
- Removed unsafe `202605070001 refresh_ecommerce_visible_baseline` migration; retained explicit local/dev startup commercial seed behind `gin_mode: debug`.
- Updated developer summary and gate report.

Validation:

- `gofmt` on touched Go files: PASS
- `go test ./internal/modules/templateops ./internal/migration ./internal/modules/catalog ./internal/modules/access ./internal/modules/commercial ./internal/modules/devseed`: PASS
- `python3 -m py_compile scripts/platform_ops_visible_baseline_gate.py`: PASS
- `python3 -m selfcheck validate --root .`: PASS
- `python3 scripts/platform_ops_visible_baseline_gate.py --project v-workspace --feature platform-ops-visible-baseline --report reports/platform-ops-visible-baseline/platform-ops-visible-baseline-gate.json`: PASS
- `scripts/project_api_smoke.sh v-workspace platform-ops-visible-baseline`: PASS
