# Requirements — Frontend Project Adapter Bootstrap

- Create a generic adapter initializer for arbitrary frontend project roots.
- Generate persistent frontend rules, a project adapter manifest, Claude frontend section, and command registry templates.
- Refuse to overwrite existing human-authored/generated files unless `--force` is supplied.
- Validate malformed adapter YAML, missing required commands/rules, path traversal, and force behavior fail closed.
- Integrate as SelfCheck feature/verifier with deterministic static smoke coverage.
