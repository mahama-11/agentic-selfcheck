# API / Backend Feasibility Map

Map every major prototype-visible function before presenting it as a finished product capability.

| Visible user function | Existing frontend support | Existing backend/API/data support | Required adaptation / contract-needed | Prototype UI treatment |
|---|---|---|---|---|
| Fill concrete user function | Existing route/component/state | Existing endpoint/data model or none | contract-needed: explain required change | Hide / limited state / user-safe wording |

## Rules

- Do not show unsupported capability as completed user value.
- `contract-needed` belongs in this internal artifact only, not in product UI copy.
- If backend/API support is partial, describe the exact missing contract or adaptation.
- If the function is frontend-only, state why it is safe and what data it uses.

## Backend impact summary

Required:
- Existing endpoints reused:
- New/changed endpoints needed:
- Data model changes needed:
- Async/job/state-machine changes needed:
- Billing/quota/security/permission implications:
- Migration/compatibility implications:
