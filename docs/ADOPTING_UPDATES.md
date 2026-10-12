# Adopting boilerplate updates

Use this guide to pull a newer boilerplate feature into an existing Django
Ninja backend. The backend can come from this boilerplate or from somewhere
else. `scripts/adopt.py` compares the backend with this repository one module
at a time, copies the missing files, and prints the wiring you add by hand.

To merge a whole release into a platform that tracks the boilerplate with git,
read [UPGRADING.md](../UPGRADING.md) instead.

## What the script does

- It copies the files of one module into the target. It never edits code that
  is already in the target.
- It refuses to overwrite a file that differs from the boilerplate, unless you
  pass `--force`. Even with `--force`, it refuses a file with uncommitted
  changes, so `git restore` can always undo the copy.
- It refuses a target that is not in a git work tree, that has no `manage.py`,
  or that is this repository.
- It never copies secrets. A module path that matches `.env*`, `*.pem`,
  `*.key` or `secrets*` stops the command. It skips `__pycache__`, `*.pyc` and
  `node_modules`.
- It prints the wiring as exact snippets: `INSTALLED_APPS`, URLs before the
  admin catch-all, the Unfold sidebar, justfile recipes, gauntlet gates,
  `pyproject.toml` package lists and dependencies.
- It records each adopted module in `<target>/.boilerplate.toml`. Commit that
  file. When it is absent, the target has never adopted a module.

## Modules

| Module | Since | Copies | Notes |
|---|---|---|---|
| `journeys` | Unreleased | `journeys/`, `scripts/check_journeys.py`, `docs/product/README.md`, the `journey-sync` skill | Writes a starter `docs/product/FEATURES.md` and journey `J-001` only when the target has none. Needs `pyyaml` and django-unfold. |
| `tickets` | Unreleased | `scripts/tickets.py`, `docs/tickets/README.md`, `docs/tickets/TEMPLATE.md`, `docs/AGENT_HANDOFF.md`, the `ticket-planner` and `ticket-worker` skills | Needs `pyyaml`. |
| `testing-policy` | 1.13.0 | `.omp/rules/ttsr-test-new-file.md`, `.omp/rules/ttsr-test-assertions.md` | Prints the "Testing policy" text from `AGENTS.md`. Paste it into the target `AGENTS.md` yourself; the script never writes it. |
| `atlas` | 1.11.0 | `atlas/`, the `system-design-atlas` skill | Follows [ATLAS_ADOPTION_PROMPT.md](ATLAS_ADOPTION_PROMPT.md). Needs django-unfold. |

`uv run python scripts/adopt.py list` prints the same list with file counts.

## Before you start

- Install `uv` and `git`.
- Commit or stash the work in the target. One module goes on one branch.
- Keep the boilerplate and the target side by side. This guide uses
  `~/dev/django-ninja-boilerplate` and `~/dev/my-api`. `--target` is the
  directory that holds the target's `manage.py`, also in a monorepo.

## Adopt a module

1. Clone or update the boilerplate next to the project:

   ```bash
   cd ~/dev
   git clone git@github.com:mattjaikaran/django-ninja-boilerplate.git
   # or, when you already have it:
   git -C django-ninja-boilerplate pull --ff-only
   cd django-ninja-boilerplate
   uv sync
   ```

2. Show what the target has adopted and what changed since:

   ```bash
   uv run python scripts/adopt.py status --target ../my-api
   ```

   Each module shows `not adopted`, `adopted` or `files differ`. When
   `.boilerplate.toml` records a version, the command prints every
   `CHANGELOG.md` section newer than it, `[Unreleased]` included. Without a
   record it lists the versions; pass `--since 1.12.0` to print the sections.

3. Read the changelog sections and pick one module.

4. Create a branch in the target:

   ```bash
   git -C ../my-api switch -c chore/adopt-journeys
   ```

5. Preview the copy and the wiring. The dry run writes nothing:

   ```bash
   uv run python scripts/adopt.py diff journeys --target ../my-api
   uv run python scripts/adopt.py apply journeys --target ../my-api --dry-run
   ```

6. Apply the module:

   ```bash
   uv run python scripts/adopt.py apply journeys --target ../my-api
   ```

7. Do every printed wiring step in the target.
8. Run the target's own gates: its tests, linter, type checker and, when it
   has one, its gauntlet. Each module prints its own verify commands.
9. Commit the files, the wiring and `.boilerplate.toml`, and open one pull
   request per module.

## Resolve a conflict

`apply` stops and lists the files that differ when the target already has its
own version of a module file. Nothing is written. Then:

1. Show the changes. Lines with `-` are in the target, lines with `+` come
   from the boilerplate:

   ```bash
   uv run python scripts/adopt.py diff journeys --target ../my-api --patch
   ```

2. Choose one:
   - Keep the target version. Port the boilerplate changes you want by hand.
   - Take the boilerplate version. Commit the target first, then run
     `apply journeys --target ../my-api --force`. Review with `git diff` and
     restore any file with `git restore <path>`.

## The `.boilerplate.toml` file

```toml
# Written by django-ninja-boilerplate scripts/adopt.py. Commit this file.
# boilerplate_version: the boilerplate VERSION at the last apply.
# [modules.<name>]: one table per adopted module.

boilerplate_version = "1.13.0"
boilerplate_commit = "9c5a827"
updated = "2026-10-12"

[modules.journeys]
adopted = "2026-10-12"
boilerplate_version = "1.13.0"
version = "Unreleased"
```

- `boilerplate_version` is the boilerplate `VERSION` at the last `apply`.
  `status` prints the changelog sections newer than it.
- `[modules.<name>].version` is the changelog version of the module that was
  copied. `status` says so when the boilerplate has a newer one.
- The script rewrites the file on each `apply`. Do not add other keys.

## Prompt for an agent in the target repository

Copy this message and send it to the coding agent that works in the target
repository. Replace the module name and the paths.

---

Adopt the `journeys` module from django-ninja-boilerplate into this backend.
The boilerplate checkout is at `../django-ninja-boilerplate`. Run its
`scripts/adopt.py` from that checkout; do not copy files any other way.

1. Run `git status`. If the tree is dirty, stop and tell me.
2. Create the branch `chore/adopt-journeys`.
3. In `../django-ninja-boilerplate`, run
   `uv run python scripts/adopt.py status --target <this repo>`. Summarize the
   module states and the changelog sections that concern this module.
4. Run `uv run python scripts/adopt.py apply journeys --target <this repo> --dry-run`.
5. If it says "Refusing to apply", stop. Run
   `uv run python scripts/adopt.py diff journeys --target <this repo> --patch`
   and show me each differing file with a recommendation: keep ours, take
   theirs, or merge by hand. Do not pass `--force` unless I say so.
6. Otherwise run the same command without `--dry-run`.
7. Do each printed wiring step in this repository. Adapt names to this
   project (settings module, root urlconf, admin URL prefix, user model). If a
   step does not fit this project, stop and ask me. Never paste secrets.
8. Run this repository's own gates: tests, linter, type checker and the
   module's verify commands. Fix only what the adoption broke.
9. Commit the copied files, the wiring and `.boilerplate.toml` with
   `chore: adopt journeys from django-ninja-boilerplate`. Do not push.
10. Report the files copied, the wiring done, the gate results, and any step
    you skipped and why.

---

## Related guides

- [ATLAS_ADOPTION_PROMPT.md](ATLAS_ADOPTION_PROMPT.md): the full atlas wiring,
  the dashboard and the renderer rules.
- [ADOPTION_PROMPT.md](ADOPTION_PROMPT.md) and
  [PORTABLE_GAUNTLET.md](PORTABLE_GAUNTLET.md): install the gauntlet that the
  printed gate snippets plug into.
- [product/README.md](product/README.md): the journey and feature format.
- [tickets/README.md](tickets/README.md) and
  [AGENT_HANDOFF.md](AGENT_HANDOFF.md): the ticket loop.
