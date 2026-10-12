# .context

Worked examples for any LLM or tool that does not read `AGENTS.md` and
`.agents/skills/` on its own.

| File | Use |
|---|---|
| `EXAMPLES.md` | Vertical slices: CRUD resource, relationships, background task, rate limiting |

Rules live in `AGENTS.md`. Layer details (exceptions, `CRUDService`, base
schemas, test fixtures) live in
`.agents/skills/django-ninja-dev/references/layer-reference.md`. Wrong vs.
right code lives in `.omp/rules/django-ninja-anti-patterns.md`.

For a tool without skills support, give it `AGENTS.md` as the system prompt
and `EXAMPLES.md` for the feature type you are building.
