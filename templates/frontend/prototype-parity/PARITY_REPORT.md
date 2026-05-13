# Prototype-to-Production Parity Report

Use this template when production implementation claims parity with an accepted/frozen frontend prototype.
The executable gate consumes `frontend-parity-report.json`; this Markdown file is the human-readable companion.

## Required evidence

- `prototype-freeze.json` from the accepted/frozen prototype workflow.
- Optional freeze gate result, usually `frozen-prototype/prototype-freeze-gate-result.json`, with `status: PASS`.
- Strict real PNG production screenshots under `production-screenshots/`.
- One coverage entry and one comparison entry for every frozen prototype screenshot/surface.

## Threshold

- Default minimum parity score: `80` for C/D-risk frontend work.
- D-risk material deviations require `human_approved` deviation approval and top-level approval.
- `contract_needed` exceptions may document non-visual follow-up contracts only; they cannot bypass visual parity evidence.

## JSON skeleton

```json
{
  "schema_version": "1.0",
  "risk": "C",
  "workflow": "frontend-workflow-name",
  "prototype_freeze_evidence": {
    "path": "prototype-freeze.json",
    "gate_result_path": "frozen-prototype/prototype-freeze-gate-result.json",
    "status": "PASS"
  },
  "threshold": {
    "minimum_score": 80,
    "scoring_basis": "Structured parity assessment from accepted prototype screenshots to production screenshots."
  },
  "overall_parity_score": 90,
  "verdict": "PASS",
  "coverage": [
    {
      "route": "/",
      "surface": "home",
      "prototype_screen": "home",
      "production_screenshot": "production-screenshots/home.png",
      "status": "covered"
    }
  ],
  "comparisons": [
    {
      "route": "/",
      "surface": "home",
      "prototype_screen": "home",
      "prototype_screenshot": "prototype-screenshots/home.png",
      "production_screenshot": "production-screenshots/home.png",
      "parity_score": 90,
      "status": "pass",
      "notes": "Layout, spacing, hierarchy, color, typography, and primary interactions preserve the frozen prototype intent."
    }
  ],
  "deviations": [],
  "contract_needed_exceptions": [],
  "approval": {
    "owner": "product-design",
    "status": "accepted",
    "rationale": "Production preserves the frozen prototype intent above threshold.",
    "date": "YYYY-MM-DD"
  }
}
```
