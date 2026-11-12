# Development MCP server

The development MCP server gives a coding agent read access to the running Django
project and to the repo's ticket and journey state. It is for local development
only. For the layer overview, see [AI_LAYER.md](AI_LAYER.md).

## Start the server

```bash
just mcp        # starts the mcp Compose service on 127.0.0.1:8001
just mcp-logs   # follow the server log
```

Connect an MCP client to `http://127.0.0.1:8001/sse` with the header
`Authorization: Bearer <DJANGO_MCP_AUTH_TOKEN>`.

`scripts/run_dev_mcp.py` is the launcher inside the container. It refuses to start
(exit 2) unless all of these hold:

- `DJANGO_SETTINGS_MODULE` is `api.settings.dev`.
- `DEBUG` is true.
- `DJANGO_MCP_AUTH_TOKEN` holds at least 32 characters. Set it in `.env`.

The server also rejects any `Host` header other than `localhost` or `127.0.0.1`.
That check blocks DNS rebinding from a browser on your machine.

## Tools

The server registers 16 tools: four project tools, and 12 tools from
django-ai-boost. The project tools come from `scripts/run_dev_mcp.py`:

| Tool | Source | What it returns |
|------|--------|-----------------|
| `tickets_next` | `scripts/tickets.py next` | Claimable small tickets |
| `tickets_show` | `scripts/tickets.py show` | One ticket and its claim blockers |
| `journeys_report` | `check_journeys` | Journey counts, errors, and gaps |
| `agent_status` | `scripts/agent_status.py --json` | Repo summary: git, tickets, journeys, OpenAPI |

The django-ai-boost tools give read access to the project: setting values, model
rows, the URL map, migrations, system checks, and recent logs. Their names are
`application_info`, `get_setting`, `list_models`, `database_schema`, `query_model`,
`list_urls`, `get_absolute_url`, `reverse_url`, `list_migrations`,
`list_management_commands`, `run_check`, and `read_recent_logs`.

The project tools claim tickets from local `agent/*` branches and `origin`
remote-tracking refs. They never contact the remote. Run `git fetch` first for
fresh claims. Claiming stays a shell action: `just tickets claim <id>`.

## Token cost

Most MCP clients load every connected tool definition into the model context at the
start of a session. Anthropic's engineering post on code execution with MCP
describes this cost and the alternatives:
[Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp).

This server adds 16 tool definitions. Measured on this repo, the `tools/list`
response is 9,430 bytes of JSON. That is a byte count, not a token count. This
repo does not measure tokens for it.

Use the shell for work the repo already scripts. Load the MCP server only for
Django introspection that a shell command cannot give:

| Need | Shell command |
|------|---------------|
| Repo, worktree, stack, and gauntlet state | `just agent-status`, `just agent-start` |
| Ticket queue and claims | `just tickets` |
| Journey and e2e status | `just check-journeys` |
| Gate results | `just gauntlet-quick` |

## Security

- Keep the server on `127.0.0.1`. The django-ai-boost tools expose setting values
  and model rows.
- Never run the server with `DEBUG` off or with a production settings module.
- Keep `DJANGO_MCP_AUTH_TOKEN` out of git. Only `.env.example` holds the empty
  placeholder.
