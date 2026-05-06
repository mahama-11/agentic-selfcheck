# Developer Summary

Role: developer

Changed:
- Added dispatch artifact parser and lifecycle helpers to `selfcheck/__main__.py`.
- Added `selfcheck dispatch list|plan|claim|complete|cancel`.
- Added `docs/dispatch-runner.md`.
- Added `features/selfcheck-dispatch-runner.yaml`.

Behavior:
- `list` shows open/claimed dispatches.
- `plan` emits JSON with a delegate_task-ready prompt.
- `claim` and `complete` write sidecar metadata.
- Closed dispatches are hidden unless `--include-closed` is used.
