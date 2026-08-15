# deepsec security scanning

[deepsec](https://github.com/vercel-labs/deepsec) is an agent-powered
vulnerability scanner from Vercel Labs. It runs as an `npx` CLI in your own
infrastructure: a fast regex pattern scan finds candidate sites, then a
coding agent investigates them and writes findings with recommended fixes.

The boilerplate ships the plumbing — Makefile targets, this guide, and a
CI workflow example — so you can adopt deepsec without wiring anything by
hand. deepsec is not a Python dependency; it runs from Node on demand.

## How it works

| Stage | Command | What it does |
| ----- | ------- | ------------ |
| Init | `make deepsec-init` | Interactive setup: pick a model and a budget. Creates the `.deepsec/` folder. |
| Scan | `make deepsec-scan` | Regex matchers find candidate sites. Fast, free, no AI. |
| Review | `make deepsec-review` | AI investigates candidates and writes findings. |
| Report | `make deepsec-report` | Export findings as markdown into `./findings`. |
| Re-check | `make deepsec-revalidate` | Re-check existing findings against git history. |

The scan state lives in `.deepsec/` at the repo root. If a run is
interrupted, re-run the same command; it continues where it left off.

## First scan

```bash
make deepsec-init          # interactive: model + spending cap
make deepsec-init -- --max-cost-usd 50 --max-duration 2h   # cap the run
make deepsec-scan
make deepsec-review
make deepsec-report        # findings land in ./findings/
```

`npx deepsec init` asks how to pay for model usage. Use your own
OpenAI/Anthropic key, or the Vercel AI Gateway. With a direct key:

```bash
npx deepsec init --model-auth direct --ai-provider openai --ai-api-key-env OPENAI_API_KEY
```

deepsec only stores the *name* of the environment variable that holds your
key, never the key itself.

## CI

Deepsec reviews can be gated on pull requests with `process --diff`, which
scans and investigates only the files changed in a diff. It needs model
credentials in CI, so the workflow is opt-in:

```yaml
# .github/workflows/security-scan.yml (example)
name: Deepsec security scan
on:
  pull_request:
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: npx deepsec init --model-auth direct --ai-provider openai \
              --ai-api-key-env OPENAI_API_KEY --max-cost-usd 25
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      - run: npx deepsec scan
      - run: npx deepsec process --diff
      - run: npx deepsec export --format md-dir --out ./findings
      - uses: actions/upload-artifact@v4
        with:
          name: deepsec-findings
          path: ./findings
```

## Cost and scope

Deepsec uses top models at maximum thinking levels. A full scan of a large
codebase can cost hundreds of dollars. Cap every run:

```bash
npx deepsec init --max-cost-usd 100 --max-duration 2h
```

The boilerplate already ships complementary static checks that run free in
CI: `make check-all` runs the gauntlet (ruff, mypy, ty, architecture and
convention checks), and `make security-check` runs Django's
`check --deploy` for production settings misconfigurations. Treat deepsec
as the deep, occasional audit on top of those.

## Security model

deepsec runs as a coding agent with shell access to the machine it runs on.
It is designed for trusted inputs (your source code). For large monorepos
you can fan work across Vercel Sandbox microVMs, which keeps model
credentials host-side. See the
[deepsec docs](https://github.com/vercel-labs/deepsec) for details.
