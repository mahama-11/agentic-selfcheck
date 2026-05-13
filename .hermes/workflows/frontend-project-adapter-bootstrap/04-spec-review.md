# Spec Review

Initial spec review returned BLOCK due to incomplete schema enforcement and partial writes on failed init.

Repair status: addressed in `repair-001.md`.

Post-repair expected coverage:
- adapter config schema version and policy consts fail closed;
- missing commands/rules still fail closed;
- path traversal still fails closed;
- no-force conflicts preflight and produce no partial adapter files;
- malformed YAML reports sanitized line/column without echoing source content.
