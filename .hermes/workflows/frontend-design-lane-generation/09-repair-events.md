# Repair Events

Status: CLOSED

## Repair 1 — Spec integration gaps

Blockers:

- Initializer lacked explicit lane dirs.
- Prototype gate did not enforce lane gate.
- Lane gate did not enforce Design Quality Pack prerequisite.
- Verifier was base-only.

Resolution:

- Added lane initialization, frontend quality gate integration, DQP prerequisite check, and smoke verifier.

## Repair 2 — Fake image fail-open

Blockers:

- Placeholder/decision regex could pass templates.
- Extension/header-only image checks were too weak.
- PNG parser missed no-IDAT, invalid scanline filter, and invalid IHDR method cases.
- JPEG/WebP structural fakes could pass if accepted.

Resolution:

- Restricted lane screenshot evidence to strict PNG.
- Added schema JSON parse, stricter decision/artifact checks, strict PNG parser, and negative fixtures.
- JPEG/WebP are now unsupported/fail-closed for lane screenshot evidence.

Final status: CLOSED after final verifier PASS.
