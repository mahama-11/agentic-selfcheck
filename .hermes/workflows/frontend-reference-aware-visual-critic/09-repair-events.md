# Repair Events

Status: CLOSED

## Repair 1 — Runtime/schema mismatch

Blocker:

- Schema was stricter than the script, but script did not enforce nested shape deeply.

Resolution:

- Added nested runtime checks for extra/missing fields and exact list/scalar types.
- Scores must be JSON numbers.
- Added malformed-payload, extra-nested-field, and string-score negative smoke cases.

Status: CLOSED after quality APPROVED.
