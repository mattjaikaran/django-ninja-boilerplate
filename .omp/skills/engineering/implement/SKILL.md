---
name: implement
description: Implement work based on a spec or tickets using TDD where possible. Chains: grill → plan → tdd → typecheck → test → code-review → gauntlet.
disable-model-invocation: true
---

Implement the work described by the user.

## Workflow

1. **Grill** — run `/grill-me` to align on scope, architecture, schemas, auth, testing seams
2. **TDD** — write failing test, implement, repeat in vertical slices
3. **Typecheck** — run `mypy` after each file
4. **Test** — run the single test file after each cycle, full suite at end
5. **Code Review** — run `/code-review` to verify standards + spec
6. **Gauntlet** — run `just gauntlet-quick` before declaring done

## During implementation

- Follow `AGENTS.md` section 08 for every layer
- Copy the closest slice from `.context/EXAMPLES.md`; look up layer details in
  `.agents/skills/django-ninja-dev/references/layer-reference.md`

## Done when

- [ ] Gauntlet passes (`just gauntlet-quick`)
- [ ] Convention checker passes (0 violations)
- [ ] Tests pass with coverage above threshold
- [ ] Typecheck passes
- [ ] Commit follows conventional format
