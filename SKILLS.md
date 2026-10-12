# Skills

Agent Skills live in `.agents/skills/`. The directory is harness-agnostic:
oh-my-pi, Android Studio, Replit, and other tools that implement the Agent
Skills specification discover it automatically and load a skill on demand.

| Skill | Description |
|---|---|
| [`django-ninja-dev`](.agents/skills/django-ninja-dev/SKILL.md) | Controller, schema, and service patterns for Django Ninja Extra. |
| [`docker-compose-profiles`](.agents/skills/docker-compose-profiles/SKILL.md) | One Compose file, the dev/test/prod/single profiles. |
| [`journey-sync`](.agents/skills/journey-sync/SKILL.md) | Keep features, journeys, and the frontend repo's `@J-NNN` Playwright tags in sync; the JOURNEYS gate. |
| [`rtk-ripgrep`](.agents/skills/rtk-ripgrep/SKILL.md) | Searching with ripgrep, and the RTK `exclude_commands` workaround. |
| [`system-design-atlas`](.agents/skills/system-design-atlas/SKILL.md) | The admin architecture map and how to regenerate it. |
| [`ticket-planner`](.agents/skills/ticket-planner/SKILL.md) | Clarify decisions, split work into vertical slices, and write small tickets for worker models; collision checks. |
| [`ticket-worker`](.agents/skills/ticket-worker/SKILL.md) | Strict loop for a worker model: claim, change owned files, verify, open a PR, or stop with a redacted draft PR. |

## How to add a skill

1. Create `.agents/skills/<skill-name>/SKILL.md`. The `name` must match the
   directory name: lowercase letters, numbers, and single hyphens, at most 64
   characters.
2. Add YAML frontmatter with `name` and `description`. The description has at
   most 1,024 characters. Write it in the third person: what the skill does,
   then when to use it. Put every trigger in the description, not in the body:
   the agent sees only the description until it loads the skill.
3. Keep `SKILL.md` under 500 lines: steps first, then the rules every run
   needs. Move material that only some runs need into `references/`, and link
   each file directly from `SKILL.md` (one level deep).
4. Put helper scripts in `scripts/`.
5. Add a row to the table above.
6. Test the trigger. Give an agent a prompt that needs the skill but does not
   name it, and a near-miss prompt that shares its keywords but needs another
   skill. The first must load the skill; the second must not.

Sources: [Agent Skills specification](https://agentskills.io/specification),
[Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices),
[`skill-creator`](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md).

## Format

```markdown
---
name: skill-name
description: >
  Does X and Y for Z. Use when ... or when the user mentions "x" or "y".
---

# Skill title

1. First step.
2. Second step. For the rare case, see [references/case.md](references/case.md).
```

The `description` is the routing signal. Write it for the agent that decides
whether to load the skill, not for a human browsing a list.
