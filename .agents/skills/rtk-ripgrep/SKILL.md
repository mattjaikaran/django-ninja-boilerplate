---
name: rtk-ripgrep
description: >
  Use when searching the codebase, or when a ripgrep/grep command behaves oddly
  or spikes CPU. Covers the `just search` recipe and the RTK exclude_commands
  workaround. Use when the user mentions "search", "ripgrep", "rg", "grep",
  "find in files", or "rtk".
---

# Search with ripgrep, not grep

Use `rg` (ripgrep) for every search. It respects `.gitignore`, so it skips
`.venv`, `node_modules`, `htmlcov`, and build output. Recursive `grep` scans all
of those.

## When to use this skill

- Finding code across the repo
- A search is slow or returns nothing
- RTK rewrites a search command

## Prefer the tools, then the recipe

The agent harness has `grep` and `glob` tools. Use them first. From a shell, use
the recipe:

```bash
just search "TODO"
```

which runs:

```bash
rg --smart-case <pattern> <paths>
```

## RTK compatibility

This machine routes shell output through RTK. RTK can rewrite `rg` and `grep`
calls, which spikes CPU and can change results. Exclude them in
`~/.config/rtk/config.toml`:

```toml
[hooks]
exclude_commands = ["rg", "grep", "ggrep"]
```

Until that is in place, route searches through `just search`, which RTK leaves
alone.

## Rules

- Never use `grep -r`. Use `rg`.
- Do not add `grep` to `just` recipes or scripts.
- Exact-output checks (byte-for-byte diffs, test totals) must bypass RTK
  entirely so the output is not trimmed.

See `references/rtk-config.md` for the full config and the rationale.
