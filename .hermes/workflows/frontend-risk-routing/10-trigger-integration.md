# Trigger Integration Addendum

## Goal

Make V frontend file changes trigger the frontend risk router automatically through the existing event system.

## Changes

- `scripts/v_continuous_governance_trigger.py`
  - Added frontend path/suffix detection.
  - Emits `v.governance.changed.frontend` for V frontend files.
- `events/v-frontend-risk-routing-changed.yaml`
  - Routes frontend-change events to `frontend-risk-routing` static gate.

## Verification

PASS:

```bash
python3 -m py_compile scripts/v_continuous_governance_trigger.py
python3 -m selfcheck validate --root .
scripts/v_continuous_governance_trigger.py --repo-root /root/work/v --changed-file ecommerce-frontend/src/pages/ProductCenter.tsx --source local --dry-run --timeout 120
scripts/v_continuous_governance_trigger.py --repo-root /root/work/v --changed-file ecommerce-frontend/src/pages/ProductCenter.tsx --source local --timeout 120
```

## Evidence

The real trigger emitted and passed:

- `v.governance.changed.code` → `v-project-code-health-governance`
- `v.governance.changed.frontend` → `frontend-risk-routing`
