# Skills

Agent Skills live in `.agents/skills/`. The directory is harness-agnostic:
oh-my-pi, Android Studio, Replit, and other tools that implement the Agent
Skills specification discover it automatically and load a skill on demand.

| Skill | Description |
|---|---|
| [`django-ninja-dev`](.agents/skills/django-ninja-dev/SKILL.md) | Controller, schema, and service patterns for Django Ninja Extra. |
| [`docker-compose-profiles`](.agents/skills/docker-compose-profiles/SKILL.md) | One Compose file, the dev/test/prod/single profiles. |
| [`rtk-ripgrep`](.agents/skills/rtk-ripgrep/SKILL.md) | Searching with ripgrep, and the RTK `exclude_commands` workaround. |
| [`system-design-atlas`](.agents/skills/system-design-atlas/SKILL.md) | The admin architecture map and how to regenerate it. |

## How to add a skill

1. Create `.agents/skills/<skill-name>/SKILL.md`.
2. Add YAML frontmatter with `name` and a `description` that states when to use
   the skill and lists its trigger words.
3. Keep `SKILL.md` under 500 lines. Move detail into `references/`.
4. Put helper scripts in `scripts/`.
5. Add a row to the table above.
6. Test it by asking an agent to use the skill by name.

## Format

```markdown
---
name: skill-name
description: >
  Use when ... Provides ... Use when the user mentions "x", "y", "z".
---

# Skill title

## When to use this skill

- ...
```

The `description` is the routing signal. Write it for the agent that decides
whether to load the skill, not for a human browsing a list.
