# Requirement Origin Trace

## Source-of-truth documents

| ID | Source | Location / URL | Role | Status |
|---|---|---|---|---|
| R1 | Fill source document name | Fill path or URL | primary | active |

## Requirement sections / anchors

For C/D-risk existing-product prototypes, every source section or anchor screenshot that affects the user journey must be traced before visual generation.

| Anchor ID | Source section / image | Requirement intent | User-facing surface | Must preserve | Status |
|---|---|---|---|---|---|
| A1 | Fill section/image | Fill requirement intent | Fill page/surface | Fill content/flow/state/action | planned |

Status values:

```text
planned | covered | partial | intentionally_separate | out_of_scope_with_reason
```

## Multi-surface target map

Do not collapse a multi-page requirement into one pretty dashboard. Define the landing surfaces first, then fill them progressively.

| Surface | Source anchors | User job | Layout skeleton | Required states | Prototype artifact / route | Status |
|---|---|---|---|---|---|---|
| Surface 1 | A1 | Fill user job | Fill skeleton | loading / empty / active / error / success | Fill route/file | planned |

## Loss prevention rule

Before producing the next prototype version, compare it against the previous accepted/strong parts:

| Previous asset / version | What it got right | Must not regress in next version | Regression check |
|---|---|---|---|
| Fill previous prototype/doc | Fill preserved quality | Fill non-regression rule | pending |

## Coverage delta log

Every new prototype version must say what it adds and what it must not remove.

| Prototype version | Added coverage | Removed / weakened coverage | Decision | Repair needed |
|---|---|---|---|---|
| v1 | Fill | Fill | continue / reject / repair | Fill |

## Acceptance rule

A prototype lane cannot be presented as a complete candidate unless:

- each primary source section/image has a `covered`, `partial`, or explicit `out_of_scope_with_reason` status;
- each required user-facing surface has an artifact/route or is explicitly deferred with rationale;
- the lane has no unexplained regression from previously accepted skeleton/content/visual direction;
- internal review/feasibility details stay out of user UI but remain available in internal artifacts.
