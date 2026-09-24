# RTK configuration

## The problem

RTK rewrites noisy shell commands to keep agent context small. That is useful
for test runners and linters, but harmful for search:

- A rewritten `rg` can scan far more than intended and spike CPU.
- Trimming search output hides matches.

## The fix

Add this to `~/.config/rtk/config.toml` (create the file and directory if they do
not exist):

```toml
[hooks]
exclude_commands = ["rg", "grep", "ggrep"]
```

`exclude_commands` lists programs RTK must pass through untouched. `ggrep` is
listed because some macOS setups alias GNU grep to it.

This is a user-level file, outside the repository. It is documented here rather
than committed.

## Working around an unconfigured machine

`just search <pattern> [paths]` invokes `rg` in the form RTK does not rewrite.
Use it when you cannot change the RTK config.

## When exact output matters

Do not route these through RTK:

- Coverage and test totals you intend to quote.
- `ruff format --check` output.
- `docker compose config` output.
- Any diff you will compare byte-for-byte.

Run them plain so nothing is trimmed.

## Reference

- ripgrep: https://github.com/BurntSushi/ripgrep
- The `search` recipe is defined in the root `justfile`.
