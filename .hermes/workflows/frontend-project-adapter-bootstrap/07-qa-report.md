# QA Report: frontend-project-adapter-bootstrap

Verdict: PASS (static/control-plane QA)

## Evidence

- Py compile PASS.
- Adapter smoke PASS.
- SelfCheck validate PASS.
- SelfCheck audit for `frontend-project-adapter` PASS.
- SelfCheck static run PASS.

## Smoke coverage

The smoke runner covers:

- base-check
- good init/check
- overwrite refusal without force
- force replacement semantics
- existing `CLAUDE.md` refusal without force
- managed Claude section with force
- malformed config redaction
- schema version failure
- required policy value failure
- corrupt source template no partial writes
- missing required command
- missing required rule file
- path traversal

Verdict: PASS.
