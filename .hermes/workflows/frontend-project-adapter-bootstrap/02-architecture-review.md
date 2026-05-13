# Architecture Review: frontend-project-adapter-bootstrap

Verdict: ACCEPTED

## Architecture

The adapter layer is intentionally generic and project-local:

```text
SelfCheck generic frontend gates
-> project adapter manifest
-> persistent project rules / command registry
-> project-specific verification evidence
```

This avoids hardcoding V-specific paths into the generic frontend control-plane while making the rules actually consumable by Cursor/Claude/Playwright-style workflows.

## Safety boundaries

- `PROJECT_ADAPTER.yaml` is a contract, not credentials storage.
- Paths must stay inside the target project.
- Existing files fail without `--force`; no partial writes on preflight failure.
- Malformed YAML errors are summarized without echoing secret-like source content.
