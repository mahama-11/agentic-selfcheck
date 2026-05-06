# Developer Summary

Role: developer

Changed:
- Added `selfcheck dispatch consume`.
- Added dispatch run directory support under `.hermes/dispatch-runs/`.
- Added explicit executor command support with env vars and no shell.
- Added automatic affected-group SelfCheck rerun and verified completion.
- Added `docs/dispatch-consume-runner.md` and `features/selfcheck-dispatch-consume-runner.yaml`.
- Added `scripts/test_dispatch_executor.py` for lifecycle QA.

Files:
- `selfcheck/__main__.py`
- `.gitignore`
- `scripts/test_dispatch_executor.py`
- `docs/dispatch-consume-runner.md`
- `features/selfcheck-dispatch-consume-runner.yaml`
