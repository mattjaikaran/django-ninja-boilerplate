# Agent handoff

This guide explains how a large planner model and smaller worker models share
work on this repository. The planner writes specs, journeys and tickets. A
worker executes small tickets and opens pull requests. The maintainer reviews
and merges.

Related files:

- [`docs/tickets/README.md`](tickets/README.md): ticket format, lifecycle,
  collision rules, hot files.
- [`docs/tickets/TEMPLATE.md`](tickets/TEMPLATE.md): a copyable ticket.
- `AGENTS.md` sections 13 and 14: journeys and work modes.
- Skills: `ticket-planner`, `ticket-worker`, `journey-sync` (see
  [`SKILLS.md`](../SKILLS.md)).

Statements marked **Recommendation** are suggested practice, not repo rules.

## Work modes

|Mode|Who|Pushes to `main`|How work lands|
|---|---|---|---|
|Solo|The maintainer and the planner model|Yes|Direct commits that follow Conventional Commits and pass `just gauntlet-quick`.|
|Worker|A worker model|Never|A branch `agent/T-NNN-*` and a PR from the bot account. The maintainer reviews and merges.|

A worker model never pushes to `main`, even when branch protection would
allow it.

## Roles

### Planner

The planner is the largest model you have access to. It:

- Writes and updates `docs/product/FEATURES.md` and
  `docs/product/journeys/J-NNN-*.md`.
- Writes tickets in `docs/tickets/` and keeps `tickets.py check` green.
- Takes `tier: large` tickets itself, or splits them into small ones.
- Reviews worker PRs and turns each rejection into a lesson (see
  [How this guide evolves](#how-this-guide-evolves)).

### Worker

The worker is a local model. Examples: a Qwen 27B class model on a GPU box or
a Mac mini, or a larger local model on a Mac Studio. It:

- Executes `tier: small` tickets only.
- Reads the ticket and the files in `owns`. Nothing else is required.
- Edits only files in `owns`, plus `status: done` in its own ticket file.
- Opens a PR as the bot user. It never merges.

A worker does not make design decisions. When a ticket needs one, the ticket
is wrong: the worker stops and flags it (see the stop rules below).

## Handoff when the planner runs out of limits

The planner usually runs on a subscription with usage limits. Before it hits
the limit, it leaves a queue that workers can drain without it.

Planner checklist before handoff:

- [ ] At least one ticket per worker for the expected session is `tier: small`
      and `status: ready`.
- [ ] Each ready small ticket names exact paths in `owns`, exact signatures or
      snippets in `## Change`, and commands with expected output in
      `## Verify`.
- [ ] Tickets that must run in order have `depends_on` set.
- [ ] `uv run python scripts/tickets.py check` exits 0. It blocks collisions.
- [ ] `uv run python scripts/tickets.py next --tier small` lists the tickets
      you expect.
- [ ] Ticket files are committed and pushed to `origin/main`. Workers claim
      from `origin/main`.
- [ ] Open questions are in `status: blocked` tickets, not in ready ones.

## Machines

**Recommendation:** run workers on an always-on machine, such as a Mac mini,
that runs a [Herdr](https://herdr.dev) server.

- Herdr runs as a persistent server (`herdr server`). Attach from another
  machine through SSH with `herdr --remote <host>`. Sessions on the server
  keep running after you detach.
- Use one git worktree per ticket, for example
  `~/worktrees/<repo>/T-NNN`. Each worker then has its own checkout and
  branch, and two workers never share a working tree.

```bash
git -C ~/src/<repo> worktree add ~/worktrees/<repo>/T-001 agent/T-001-prune-centrifugo-tests
```

`herdr worktree create` can also create and open a worktree from inside Herdr.

Remove the worktree after the PR merges:

```bash
git -C ~/src/<repo> worktree remove ~/worktrees/<repo>/T-001
```

## Overnight loop

`scripts/worker_once.py` runs one iteration of the loop. Run it from a main
checkout of the repo (`~/src/<repo>` here). It:

1. Fast-forwards the main checkout to `origin/main`, then takes the first
   claimable `tier: small` ticket, or the one you pass with
   `--ticket T-NNN`.
2. Claims it with the atomic push from `scripts/tickets.py`.
3. Creates the worktree `${WORKER_WORKTREES:-~/worktrees/<repo>}/T-NNN` on
   the ticket branch.
4. Runs the worker agent in the worktree with a prompt that points to the
   ticket and the `ticket-worker` skill. The agent commits but does not
   push. Logs go to a per-ticket directory `$WORKER_LOG_DIR/T-NNN/`
   (default `~/.cache/worker-once`, mode 700, never `/tmp`), so parallel
   Herdr panes never share a log: the agent output to `T-NNN/agent.log`.
5. Runs each fenced block under the ticket's `## Verify` and
   `$WORKER_GAUNTLET_CMD` (default `just gauntlet-quick`). Output goes to
   `T-NNN/verify.log` (reset each run)
   with `exit=` markers. On the first failure, it runs the agent once more
   with the redacted log and "fix only what fails, within owns", then runs
   Verify again.
6. On success, checks that the diff since the merge base stays within
   `owns` and the ticket file, commits leftover changes, pushes, and opens
   a PR.
7. On an agent error, a second Verify failure, or an `owns` violation,
   follows the stop rules below: it restores the ticket file from
   `origin/main`, writes a redacted `T-NNN/failure.md`, and opens a
   draft PR labeled `needs-planner`.

Set these variables on the worker machine:

|Variable|Default|Purpose|
|---|---|---|
|`WORKER_AGENT_CMD`|none (required)|Agent command, for example `claude -p`, `omp -p`, or `opencode run`. The script appends the prompt.|
|`WORKER_TIMEOUT`|`3600`|Agent timeout in seconds.|
|`WORKER_WORKTREES`|`~/worktrees/<repo>`|Parent directory for worktrees.|
|`WORKER_REVIEWER`|unset|Passed as `--reviewer`. Omitted when unset.|
|`WORKER_GAUNTLET_CMD`|`just gauntlet-quick`|Gate run after the ticket's Verify blocks.|
|`WORKER_LOG_DIR`|`~/.cache/worker-once`|Private log root; each ticket gets its own subdirectory.|

Preview the plan first. `--dry-run` prints every command and changes
nothing:

```bash
uv run python scripts/worker_once.py --dry-run
```

Exit codes: `0` PR opened or dry run, `1` stopped with a draft PR, `2`
nothing to do or setup error. To drain the queue, for example in a Herdr
pane, loop until exit `2`:

```bash
while uv run python scripts/worker_once.py || [ $? -eq 1 ]; do :; done
```

### Stop rules

- A ticket that fails `## Verify` or the gauntlet twice gets a **draft** PR
  labeled `needs-planner`. Put a redacted failure log in the PR body (see
  [Secrets and sensitive data](#secrets-and-sensitive-data)). Do not guess a
  fix, and do not set `status: done`.

  ```bash
  gh pr create --draft --label needs-planner --base main --head <branch> \
    --title "T-NNN <ticket title>" --body-file ~/.cache/worker-once/T-NNN/failure.md \
    --reviewer <maintainer>
  ```

- A ticket that needs a file outside `owns`: stop, open the same draft PR,
  and say which file and why.
- A ticket whose `## Change` needs a design decision: stop, same draft PR.
- After a stop, move to the next ticket. Do not retry the stopped one.

## Bot GitHub user

Workers open PRs from a separate GitHub account, so every worker change is
visible and reviewable.

1. Create a separate GitHub account for the bot. Add it to the repository as a
   collaborator with write access, so it can push `agent/*` branches.
2. Signed in as the bot, create a fine-grained personal access token that
   only has access to this repository. Grant `Contents: Read and write` and
   `Pull requests: Read and write`. See
   [Managing your personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).
3. Sign `gh` in as the bot on the worker machine only:
   `gh auth login --with-token < bot-token.txt`, then delete the file. `gh`
   keeps the token in the system credential store unless you pass
   `--insecure-storage` ([gh auth login](https://cli.github.com/manual/gh_auth_login)).
   Do not export `GH_TOKEN` from a shell profile: every process, including
   the agent, can read it. Set an expiry date on the token. Never sign in as
   the bot on your own machine.
4. Protect `main`: require a pull request with one approval before merging.
   Allow administrators to bypass, so you can still push to `main` in solo
   mode. See
   [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
5. Pass `--reviewer <maintainer>` to `gh pr create` so the PR requests your
   review ([gh pr create](https://cli.github.com/manual/gh_pr_create)).
6. Create the stop-rule label once:
   `gh label create needs-planner --description "Worker stopped; planner must fix the ticket"`.
   `gh pr create --label` fails when the label does not exist.

The bot cannot approve its own PR, so the one-approval rule means a human
reviews every worker change.

## Secrets and sensitive data

This guide and the ticket files contain no secrets, host names, or account
names. Keep it that way: `<host>` and `<maintainer>` stay placeholders in
committed files. Put real values in your local shell or `gh` config.

- **Worker `.env`.** Generate it on the worker machine with
  `just setup-env`. Do not copy your own `.env` to it. Use development
  values only; a worker machine never holds production credentials.
- **Tickets.** Name environment variables (`STRIPE_SECRET_KEY`), never their
  values. The planner must not paste a key, token, or connection string into
  a ticket.
- **Agent commands.** A worker must not run `env`, `printenv`, `cat .env`,
  or `gh auth token`, and must not echo a variable that holds a credential.
  Add these to the worker harness deny list if it has one.
- **Failure logs.** Before a log goes into a PR body, keep only the failing
  command and its last 50 lines, and pass them through
  `scripts/redact_log.py`. It replaces the values of secret keys in `.env`,
  bearer tokens, credentials in URLs, and GitHub, Stripe and JWT tokens:
  `tail -n 50 ~/.cache/worker-once/T-NNN/verify.log | uv run python scripts/redact_log.py > ~/.cache/worker-once/T-NNN/failure.md`.
  Read the result once before you post it. A PR on a public repository is
  public.
- **Remote access.** Reach the worker machine over SSH with key
  authentication. Do not write its address or user name in this repository.
- **Leak response.** If a secret reaches a commit or a PR, revoke it first,
  then remove it from the branch. Deleting the text does not un-leak it.

## Hermes kanban mirror

**Recommendation:** if you use [Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban),
mirror ready tickets to its kanban board so you can watch the queue. The
ticket file stays the source of truth.

```bash
hermes kanban init
hermes kanban create "T-001 Prune mock-only tests from core/tests/test_centrifugo.py" \
  --body "Ticket: docs/tickets/T-001-prune-centrifugo-tests.md" \
  --assignee <profile>
hermes kanban list
```

The card body references the ticket file. Do not copy the ticket body into the
card. The `agent/T-NNN-*` branch, not the card, is the claim.

## How this guide evolves

- After each rejected PR, the planner adds the lesson to the
  "When to add to this section" part of `AGENTS.md`: what not to do, what to do
  instead, and why. One line per rule.
- When a small model fails a ticket, the planner tightens
  `docs/tickets/TEMPLATE.md` (for example a stricter `## Change` example) and
  rewrites the ticket. Do not lower the bar for `tier: small`.
- When a step in the overnight loop changes, update this file in the same
  commit.

## Merge conflict playbook

A worker rebases its branch when `main` moved under it.

1. `git fetch origin main && git rebase origin/main`
2. For generated files, take `main`'s version and regenerate. Never hand-merge
   them.

   |File|Regenerate with|
   |---|---|
   |`docs/openapi/openapi.json`|`just openapi`|
   |`<app>/migrations/`|Delete this branch's new migration, then `just makemigrations`|
   |`uv.lock`|`uv lock`|

3. `CHANGELOG.md`: keep both entries under `## [Unreleased]`. It is append
   only.
4. If a conflict touches a file outside the ticket's `owns`, stop. Run
   `git rebase --abort`, open or update a draft PR labeled `needs-planner`, and
   name the file.
5. Run the `## Verify` commands and `just gauntlet-quick` again, then
   `git push --force-with-lease origin <branch>`.
