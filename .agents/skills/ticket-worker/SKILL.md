---
name: ticket-worker
description: >
  Use when you are a worker model executing a tier small ticket from
  docs/tickets/: claim it, change only the files it owns, run its Verify
  commands, and open a PR. Gives the strict loop and the stop rules. Use when
  the user mentions "work the queue", "next ticket", "claim", "T-NNN",
  "overnight loop", or "worker".
---

# Ticket worker

You execute one small ticket at a time. You follow the ticket exactly. You do
not design. You do not explore.

## When to use this skill

- You were asked to work the ticket queue
- You were given a ticket ID such as T-001

## Rules

- Take only `tier: small` tickets.
- Read only the ticket file and the files in its `owns` list.
- Never edit a file outside `owns`. The one exception: set `status: done` in
  your own ticket file.
- Never push to `main`. Never merge.
- Never hand-edit `docs/openapi/openapi.json`, migrations, or `uv.lock`.
- Never add a dependency.
- Never print secrets: no `env`, `printenv`, `cat .env`, or `gh auth token`.
- If you are unsure, stop. Do not guess.

## Loop

Run from the main checkout of the repo.

1. Update:

   ```bash
   git fetch origin main && git merge --ff-only origin/main
   ```

2. Find work:

   ```bash
   uv run python scripts/tickets.py next --tier small
   ```

   Take the first ID. If the list is empty, stop the loop.

3. Claim it:

   ```bash
   uv run python scripts/tickets.py claim T-NNN
   ```

   If it says "taken", go to step 2.

4. Make a worktree for the branch and work there:

   ```bash
   git worktree add ~/worktrees/<repo>/T-NNN <branch>
   cd ~/worktrees/<repo>/T-NNN
   ```

5. Read `docs/tickets/T-NNN-*.md`. Do each step in `## Change`, in order.
6. Run every command in `## Verify`. Compare with the expected output.
7. Run `just gauntlet-quick`.
8. In the ticket file, change `status: ready` to `status: done`.
9. Check that you changed only allowed files:

   ```bash
   git status --short
   ```

10. Commit with a Conventional Commits message. Put the ticket ID in the body.

    ```bash
    git add -A
    git commit -m "fix(todos): return 404 for another user's todo" -m "Ticket: T-NNN"
    ```

11. Push and open the PR:

    ```bash
    git push origin <branch>
    gh pr create --base main --head <branch> \
      --title "T-NNN <ticket title>" \
      --body "Ticket: docs/tickets/T-NNN-slug.md" \
      --reviewer <maintainer>
    ```

12. Go to step 1.

## Stop rules

Stop the ticket when any of these happen:

- `## Verify` or `just gauntlet-quick` fails twice.
- You need to change a file that is not in `owns`.
- A step needs a decision the ticket does not make.
- A rebase conflict touches a file outside `owns`.

When you stop:

1. Do not set `status: done`. Do not guess a fix.
2. Write the failure log to `/tmp/T-NNN-failure.md`, outside the repo: the
   command, the last 50 lines of its output, and one line on what blocked
   you. Delete any token, password, cookie, or database URL from it first.
3. Commit what you have, push, and open a draft PR:

   ```bash
   gh pr create --draft --label needs-planner --base main --head <branch> \
     --title "T-NNN <ticket title>" --body-file /tmp/T-NNN-failure.md \
     --reviewer <maintainer>
   ```

4. Go to step 1 with the next ticket. Do not retry the stopped one.

## Rebase conflicts

1. `git fetch origin main && git rebase origin/main`
2. Generated files: take `main`'s version, then regenerate.
   - `docs/openapi/openapi.json`: `just openapi`
   - migrations: delete your new migration, then `just makemigrations`
   - `uv.lock`: `uv lock`
3. `CHANGELOG.md`: keep both entries under `## [Unreleased]`.
4. Any other file outside `owns`: `git rebase --abort`, then follow the stop
   rules.
5. Run Verify and `just gauntlet-quick` again, then
   `git push --force-with-lease origin <branch>`.
