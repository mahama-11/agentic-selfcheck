# 09 Repair Events — frontend-prototype-parity-gate

## Repair 1: workflow evidence
Reviewer: independent spec review
Status: repaired

Problem:
- Required tranche workflow evidence directory was missing.

Fix:
- Created `.hermes/workflows/frontend-prototype-parity-gate/` evidence files.

## Repair 2: score upper bound
Reviewer: independent quality/security review
Status: repaired

Problem:
- Gate enforced minimum score but not schema maximum 100.

Fix:
- Gate now rejects `overall_parity_score > 100` and `comparisons[].parity_score > 100`.
- Smoke suite now includes `bad-over-100-score` negative case.
