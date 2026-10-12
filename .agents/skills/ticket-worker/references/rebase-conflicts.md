# Rebase conflicts

Use this when `main` moved under your branch: the PR shows a conflict, or the
maintainer asks you to rebase. Work in the ticket's worktree.

1. Rebase:

   ```bash
   git fetch origin main && git rebase origin/main
   ```

2. For each conflicted file, do the first row that matches:

   |File|Action|
   |---|---|
   |`docs/openapi/openapi.json`|Take `main`'s version, then run `just openapi`.|
   |A migration|Delete your new migration, then run `just makemigrations`.|
   |`uv.lock`|Take `main`'s version, then run `uv lock`.|
   |`CHANGELOG.md`|Keep both entries under `## [Unreleased]`.|
   |A file in `owns`|Keep `main`'s change and your change. If they contradict, stop.|
   |Any other file|Run `git rebase --abort`, then follow the stop rules in `SKILL.md`.|

   Take `main`'s version of one file with `git checkout --ours <file>`.
   During a rebase, `--ours` is `main`.

3. Continue: `git add <file>` for each fixed file, then
   `git rebase --continue`.
4. Start a fresh log and run Verify and the gauntlet again, as in steps 5, 7
   and 8 of the loop in `SKILL.md`.
5. Push:

   ```bash
   git push --force-with-lease origin <branch>
   ```
