# grape CLI

Agentic DevOps command-line tool: **contract-driven command generation** + `git` local
passthrough (platform token never leaves the process; zero exposure).

- Reads the server's `/openapi.json` (OpenAPI 3.x) and automatically generates
  `grape <group> <verb>` commands.
- **Add a new server endpoint → re-fetch the contract → the CLI gains the new command
  automatically, no CLI source changes required.**
- Authentication reuses the grape token (Bearer by default) from config / environment
  variables, attached automatically.

---

## Install

```bash
# From source (repo root, editable)
pip install -e .             # editable: changes take effect immediately (recommended on servers)

# Or a dedicated venv (isolated from the system environment)
python3 -m venv /opt/grape-cli
/opt/grape-cli/bin/pip install -e /path/to/grape-cli
ln -sf /opt/grape-cli/bin/grape /usr/local/bin/grape
```

Verify with `grape --version`.

---

## Configuration & token

Precedence (highest first):

```
CLI one-shot args (--token / --base-url / --timeout) > GRAPE_SESSION_TOKEN > GRAPE_API_TOKEN / GRAPE_BASE_URL > ~/.grape/config.json
```

| Method | Example | Notes |
|--------|---------|-------|
| One-shot args (**recommended for single calls**) | `grape --token tk_xxx tasks mine`<br>`grape --base-url https://grape.example.com --grape-api-token grape_xxx skills list --json-out`<br>`grape --timeout 120 tasks wait --task-id 56` | Process-only, never persisted; `--token` / `--grape-api-token` / `--grape_api_token` are synonyms; `--timeout` sets the request timeout (default 30s) |
| Environment variables | `export GRAPE_SESSION_TOKEN=tk_xxx` | Task-level priority |
| Config file | `base_url` / `token` in `~/.grape/config.json` | Persistent defaults |

| Environment variable | Meaning | When to use |
|----------------------|---------|-------------|
| `GRAPE_SESSION_TOKEN` | Task-scoped **session token** (prefix `tk_`) | Inside worker/chat agents: auto-injected per task, zero config, expires when the task ends |
| `GRAPE_API_TOKEN` | User-level **long-lived API key** (prefix `grape_`) | Standalone / third-party integrations; generated in the Web UI "API Tokens" |
| `GRAPE_BASE_URL` | Server base URL (default `http://localhost:8000`) | Point to production, e.g. `https://grape.example.com` |

`~/.grape/config.json` example:

```json
{
  "base_url": "https://grape.example.com",
  "token": ""          // prefer injecting the token via environment variables
}
```

> Without a token the CLI asks you to configure one; set
> `export GRAPE_SESSION_TOKEN=...` or `export GRAPE_API_TOKEN=...` and retry.

---

## Commands

### Global

```bash
grape --help                  # top-level help: command groups + built-ins (git/api/refresh/commands)
grape commands [pattern]      # list all contract commands; pipe to filter: grape commands | grep issue
grape refresh                 # force re-fetch the latest OpenAPI contract and cache it
grape --version               # CLI version

# Long waits
grape tasks wait --task-id 56 --timeout 120 --interval 3   # poll a task until terminal (completed/failed/cancelled)
grape --timeout 300 tasks mine                             # request timeout ceiling (default 30s; git unaffected)
```

### Contract-driven commands (automatic)

Shape: `grape <group> <verb> [--options...]`, derived from `operationId`.

```bash
grape tasks mine --status active --json-out        # GET  /api/tasks/mine?status=active
grape tasks create --json '{"repo_key":"o/r","title":"x","description":"y"}'
grape skills list --json-out
grape scenes list
grape git-repo issues list --owner o --repo r --state open --json-out
grape git-repo pulls merge --owner o --repo r --number 7
```

Parameter mapping:

- `query` / `path` parameters → `--<name>`
- `requestBody` → `--json '<JSON string>'`
- `--json-out`: single-line machine-readable JSON (for workers; pretty-printed otherwise)

Discover commands: `grape <group> --help` for a group's verbs, `grape <group> <verb> --help` for its arguments.

### git (local execution, zero token exposure)

`grape git` is a **native git passthrough**: the token is fetched in-process via
`/git-credential` and injected with the `GIT_CONFIG` env vars — **never on the command
line, never written to disk, invisible to the agent**.

```bash
grape git --repo owner/repo status
grape git --repo owner/repo log --oneline -5
grape git --repo owner/repo checkout -b feat/issue-7
grape git --repo owner/repo commit -m "fix: ..."
grape git --repo owner/repo push feat/issue-7
# Without --repo: run git directly in the current directory
grape git status
```

### api (generic fallback)

For endpoints not covered by the contract or special cases:

```bash
grape api GET /api/scenes
grape api POST /api/tasks/create -d '{"repo_key":"o/r","title":"x"}'
```

---

## Quick start

```bash
# 1) One-shot call (no environment variables required)
grape --base-url https://grape.example.com --token tk_xxx skills list --json-out
grape --base-url https://grape.example.com --grape-api-token grape_xxx tasks mine --status active

# 2) Common setup (set once, reuse many times): point at production + a working token
export GRAPE_BASE_URL=https://grape.example.com
export GRAPE_SESSION_TOKEN=tk_xxx    # or: export GRAPE_API_TOKEN=grape_xxx

# 3) See what commands exist
grape commands | head -40
grape git-repo issues list --help

# 4) Run a read-only command
grape skills list --json-out
grape tasks mine --status active
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Success |
| `1`  | Generic / config error (missing token, network, timeout, …) |
| `2`  | Click usage error |
| `>=400` | HTTP status passthrough (e.g. `401`) |
| `130` | Interrupted by Ctrl+C |

---

## Security

- The CLI does **not** provide create/revoke token subcommands (prevents self-escalation);
  user-level API keys are generated in the Web UI.
- Tokens never appear in command output or error messages (git credentials injected via
  `GIT_CONFIG` stay in-process too).
- `tk_` session tokens expire automatically with the task/session; `grape_` user keys can be revoked.

---

## Project layout

```
src/
├── __init__.py          # version
├── __main__.py          # python -m src
├── cli.py               # click entrypoint (contract group + built-ins)
├── client.py            # HTTP client (auth, timeout, error mapping)
├── config.py            # config resolution: args > env > ~/.grape/config.json
├── contracts.py         # OpenAPI contract loading / caching
├── registry.py          # contract -> click command tree (operationId-driven)
└── commands/
    ├── api.py           # grape api <method> <path> fallback
    └── git.py           # grape git local passthrough with in-process credentials
```