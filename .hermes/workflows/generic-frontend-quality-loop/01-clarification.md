# Generic Frontend Quality Loop Clarification

User clarified:

- The frontend quality process must be generic, not V-specific.
- V is only the first concrete implementation/application.
- The process must apply to any frontend project in future.
- Besides consistency/standardization, the key problem is visual layout, interaction design, user experience, and product feel.
- User proposed: create high-fidelity design prototype first, iterate until aligned, then apply prototype to real project with high-fidelity replication while wiring real logic.

Action taken:

- Created generic document:
  - `docs/frontend-quality-loop.md`
- Updated V-specific document to point back to generic base:
  - `docs/v-frontend-quality-loop.md`

Position:

The user's proposed prototype-first process is the right direction for medium/high-risk frontend work and is aligned with mainstream design/engineering practice. It should be implemented as:

```text
brief -> prototype -> visual acceptance -> parity plan -> production implementation -> parity review -> runtime verification
```

Important nuance:

- Not every small UI patch needs high-fidelity prototype.
- But page/flow/product-critical/commercial-facing work should not start directly in production React.
- Prototype acceptance becomes the visual contract.
- Production implementation must pass prototype parity, not merely build/typecheck.
