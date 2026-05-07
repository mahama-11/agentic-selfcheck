# Architecture Review

Role: Architect
Timestamp: 2026-05-07T02:58:08.386075Z

## Decision
Proceed with split seed ownership:
- Platform: common identity/org/RBAC/commercial primitives.
- Ecommerce: business template fixtures and product smoke semantics.

## Boundaries
- Platform may expose internal APIs/projections, but ecommerce must not depend on platform projection being populated for local business fixture smoke.
- Ecommerce can fallback to local fixture templates only when platform projection returns not found/empty; non-404 platform errors must surface.
- RBAC default permissions must follow least privilege.

## Risks to close before PASS
- List-only fallback produces fake green UI but detail/use/copy/favorite fail.
- Role seed only appends and never removes stale default grants.
- Dev admin seed can mutate password/admin state on every debug startup.
- Gate can false-pass if it checks only row counts and 200 status.

## Next handoff
Developer must close these risks and produce implementation evidence.
