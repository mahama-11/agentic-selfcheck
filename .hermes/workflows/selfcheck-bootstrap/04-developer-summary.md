# Developer Summary

Role: developer

Implemented:
- Created `/root/work/agentic-selfcheck` project.
- Added README and Python package metadata.
- Added JSON Schemas for invariant/capability/project/feature/verifier/loop.
- Added reusable invariants and capabilities.
- Added `/root/work/v` project adapter.
- Added initial ecommerce feature acceptance sample.
- Added verifier registry and loop registry.
- Added `python3 -m selfcheck` CLI with `validate`, `plan`, `run --dry-run`, and `audit`.
- Added shell wrappers for pre-final gate and workflow-health loop.

Important behavior:
- `validate` fails on schema/reference errors.
- `audit` warns on missing required evidence.
- `run` is dry-run only in v0; non-dry-run intentionally exits until adapters are hardened.
