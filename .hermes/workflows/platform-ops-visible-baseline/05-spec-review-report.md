# Spec Review Report — platform-ops-visible-baseline

Role: Spec Reviewer re-review
Timestamp: 2026-05-07T04:18:57Z
Verdict: **PROCEED_TO_QA**

## Scope Reviewed

Re-reviewed the developer repair and current gate evidence for the prior spec blockers. Inputs read:

- `/root/work/agentic-selfcheck/.hermes/workflows/platform-ops-visible-baseline/05-spec-review-report.md` — prior spec review / request-changes findings
- `/root/work/agentic-selfcheck/.hermes/workflows/platform-ops-visible-baseline/06-quality-review-report.md`
- `/root/work/agentic-selfcheck/.hermes/workflows/platform-ops-visible-baseline/04-developer-summary.md`
- `/root/work/agentic-selfcheck/.hermes/workflows/platform-ops-visible-baseline/09-repair-events.md`
- `/root/work/agentic-selfcheck/reports/platform-ops-visible-baseline/platform-ops-visible-baseline-gate.json`

I did not edit product code.

## Re-review Summary

The developer repair closes the spec blockers that previously prevented advancement to QA.

The prior blocking issue was that Template Ops visibility was being accepted through already-persisted projections while the live sync endpoint returned HTTP 500, and the gate mislabeled that condition as successful sync. The repaired gate now reports an honest successful runtime convergence path:

```json
"template_ops_sync": {
  "status": 200,
  "ok": true,
  "upserted_total": 146
}
```

The expectations are now split correctly:

- `template_sync_request_ok: true`
- `template_sync_upserted_non_empty: true`
- `template_ops_persisted_projection_visible: true`

This addresses the original acceptance concern that a failed sync could be hidden by persisted projection rows. The gate now requires the sync request itself to succeed and to upsert non-empty Template Ops data, while tracking persisted projection visibility separately.

Browser evidence is still not present, but the repair dispatch explicitly left browser evidence for the QA stage. Since the API/spec implementation blockers are now resolved and browser verification is the next owned stage, missing screenshots should no longer block handoff to QA.

## Positive Findings After Repair

- **Template Ops runtime convergence is now proven at API gate level.** The gate report is `PASS` and shows `template_ops_sync.status = 200`, `ok = true`, and `upserted_total = 146`.
- **Gate honesty issue is closed.** A failed sync can no longer be masked by persisted rows under a misleading `template_sync_ok` expectation. Sync request success, non-empty sync upserts, and persisted projection visibility are separate expectations.
- **Template Ops visible data is non-empty and semantic.** The gate reports 146 Ecommerce template projections and `template_ops_projection_fields = true`.
- **Catalog & Assets baseline remains present.** The gate reports:
  - Ecommerce product exists.
  - SKUs: 5.
  - Packages: 5.
  - Billable items: 1 (`ecommerce.image.generate`).
  - Rate cards: 6 with both `sku` and `billable_item` target types.
  - Wallet assets: 4.
  - Quota policies: 5.
  - Offerings payload present.
- **Unsafe refresh migration concern is addressed in the developer summary.** The new `202605070001 refresh_ecommerce_visible_baseline` migration was removed; the commercial visible baseline remains a local/dev startup seed behind explicit config and `gin_mode: debug`.
- **Fresh orchestrator verification is green.** Provided verification states:
  - Go tests PASS for `templateops`, `migration`, `catalog`, `access`, `commercial`, and `devseed`.
  - SelfCheck validate PASS.
  - Gate rerun PASS.

## Remaining QA-Owned Verification

The following requirement items still need QA/browser evidence before final release acceptance:

- Platform frontend login works at `http://127.0.0.1:5173/login`.
- Authenticated `/template-ops` shows Ecommerce templates, not an empty state.
- Authenticated `/catalog` shows Agent Ecommerce product and non-empty SKU/Package/BillableItem/RateCard data.
- Browser screenshots/evidence are captured for Template Ops and Catalog & Assets visible data.

These remain required for final acceptance, but they are not a pre-QA spec implementation blocker because QA owns this browser evidence stage next.

## Requirement Coverage Matrix

| Requirement / Acceptance | Status | Notes |
| --- | --- | --- |
| Platform frontend login works at `/login` | QA pending | Browser evidence not yet captured; QA owns this next. |
| `/template-ops` shows Ecommerce templates | API met; QA pending | Gate shows sync HTTP 200, 146 upserts, and 146 persisted Ecommerce projections. Frontend screenshot pending. |
| `/catalog` shows Agent Ecommerce commercial data | API met; QA pending | Gate confirms semantic commercial counts/content. Frontend screenshot pending. |
| Semantic API gate asserts counts/content | Met | Gate status PASS with honest sync and separate persisted projection expectations. |
| Browser QA screenshots for Template Ops + Catalog | QA pending | Explicitly deferred to QA by repair dispatch. |
| SelfCheck validate/audit passes after implementation | Met for implementation handoff | Fresh orchestrator verification reports SelfCheck validate PASS and gate rerun PASS. |
| Layering: Platform owns projections/catalog primitives; Ecommerce owns template truth | Met enough for QA | Sync path derives projections from Ecommerce template catalog seed; commercial data remains Platform primitive baseline data. |

## Verdict

**PROCEED_TO_QA**

The developer repair closes the pre-QA spec blockers: live Template Ops sync now succeeds with non-empty upserts, the gate no longer masks sync failures, and the unsafe refresh migration concern has been addressed. Browser evidence remains mandatory for final acceptance, but it is correctly deferred to QA rather than blocking this spec implementation handoff.
