---
name: ticket-worker
description: >
  Executes one tier small ticket from docs/tickets/ as a worker model: update
  main, claim with scripts/tickets.py, change only the files in owns, run
  Verify and the quick gauntlet, open a PR, or stop with a redacted draft PR.
  Use when asked to work the queue, take the next ticket, claim or run a
  T-NNN ticket, or run the overnight loop. To write or split tickets, use
  ticket-planner instead.
---

# Ticket worker

You execute one small ticket at a time. You follow the ticket exactly. You do
not design. You do not explore.

## Rules

- Take only `tier: small` tickets.
- Read only the ticket file, the files in its `owns` list, and this skill.
- Never edit a file outside `owns`. The one exception: set `status: done` in
  your own ticket file.
- Never push to `main`. Never merge.
- Never hand-edit `docs/openapi/openapi.json`, migrations, or `uv.lock`.
- Never add a dependency.
- Never print secrets: no `env`, `printenv`, `cat .env`, or `gh auth token`.
- Never put raw command output in a PR. Pass it through
  `scripts/redact_log.py` first.
- If you are unsure, stop. Do not guess.

## Loop

`just worker-once` automates this loop end to end; follow these steps when
you run a ticket by hand. Run from the main checkout of the repo. Do the
steps in order. Skip none.

1. Update: `git fetch origin main && git merge --ff-only origin/main`
2. Find work: `uv run python scripts/tickets.py next --tier small`. Take the
   first ID. If the list is empty, stop the loop.
3. Claim it: `uv run python scripts/tickets.py claim T-NNN`. If it says
   "taken", go to step 2.
4. Make a worktree for the branch and work there:

   ```bash
   git worktree add ~/worktrees/<repo>/T-NNN <branch>
   cd ~/worktrees/<repo>/T-NNN
   ```

5. Start a fresh log in a private directory (never `/tmp`):
   `LOG=~/.cache/worker-once && mkdir -p -m 700 "$LOG" && : > "$LOG/verify.log"`
6. Read `docs/tickets/T-NNN-*.md`. Do each step in `## Change`, in order.
7. Run each command in `## Verify` like this, so its output and exit code
   go to the log:

   ```bash
   { <command>; echo "exit=$?"; } 2>&1 | tee -a "$LOG/verify.log"
   ```

   Compare the output with the expected output in the ticket.
8. Run the gauntlet the same way. `exit=0` means it passed.

   ```bash
   { just gauntlet-quick; echo "exit=$?"; } 2>&1 | tee -a "$LOG/verify.log"
   ```

9. In the ticket file, change `status: ready` to `status: done`.
10. Run `git status --short`. Every path must be in `owns` or be your ticket
    file. If not, follow the stop rules.
11. Commit with a Conventional Commits message. Put the ticket ID in the body:

    ```bash
    git add -A
    git commit -m "fix(todos): return 404 for another user's todo" -m "Ticket: T-NNN"
    ```

12. Push and open the PR:

    ```bash
    git push origin <branch>
    gh pr create --base main --head <branch> \
      --title "T-NNN <ticket title>" \
      --body "Ticket: docs/tickets/T-NNN-slug.md" \
      --reviewer <maintainer>
    ```

13. Go to step 1.

## Stop rules

Stop the ticket when any of these happen:

- `## Verify` or `just gauntlet-quick` fails twice.
- You need to change a file that is not in `owns`.
- A step needs a decision the ticket does not make.
- A rebase conflict touches a file outside `owns`.

When you stop:

1. Do not set `status: done`. Do not guess a fix.
2. Write the failure log, redacted, outside the repo. Name the command that
   failed, or the file or decision that blocked you:

   ```bash
   tail -n 50 "$LOG/verify.log" | uv run python scripts/redact_log.py > "$LOG/T-NNN-failure.md"
   echo "Blocked: <one line: what blocked you and why>" >> "$LOG/T-NNN-failure.md"
   ```

3. Read `$LOG/T-NNN-failure.md` once. If a token, password, cookie, or
   database URL is still there, delete it.
4. Commit what you have, push, and open a draft PR:

   ```bash
   gh pr create --draft --label needs-planner --base main --head <branch> \
     --title "T-NNN <ticket title>" --body-file "$LOG/T-NNN-failure.md" \
     --reviewer <maintainer>
   ```

5. Go to step 1 with the next ticket. Do not retry the stopped one.

## Rebase conflicts

When `main` moved under your branch (the PR shows a conflict, or the
maintainer asks you to rebase), follow
[references/rebase-conflicts.md](references/rebase-conflicts.md).
