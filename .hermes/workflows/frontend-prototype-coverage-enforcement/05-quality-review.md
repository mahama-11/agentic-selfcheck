# Quality Review

Role: Quality Reviewer

## Initial result

REQUEST_CHANGES.

## Issues found

1. Coverage was under-enforced: one COMPLETE row could hide another DRAFT/missing row.
2. Coverage row artifact/screenshot paths were not checked per row.
3. Placeholder detection could be bypassed with TBD/DRAFT/PARTIAL or over-triggered on generic `<`.
4. Absolute workflow paths outside `--root` were not rejected.

## Fixes applied

- Every surface/interaction row now requires status `COMPLETE`, `PASS`, or `DONE`.
- Local artifact/screenshot/evidence paths must exist under the workflow directory.
- Screenshot paths must be local image files; artifact URLs may be HTTP(S).
- Placeholder/incomplete token detection now includes TODO/TBD/PLACEHOLDER/N/A/MISSING/BLOCKED/DRAFT/PARTIAL/INCOMPLETE.
- `--workflow` is resolved and must stay under `--root`.
- Smoke cases added for incomplete extra row, missing row screenshot, and path traversal.

## Re-test

PASS:

- `python3 -m py_compile scripts/frontend_quality_gate.py scripts/frontend_quality_gate_smoke.py`
- `scripts/frontend_quality_gate_smoke.py --root . --format text`
- `python3 -m selfcheck validate --root .`
- `python3 -m selfcheck run --root . --feature frontend-prototype-gate --groups static --timeout 120`
