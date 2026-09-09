# grape CLI

Agentic DevOps CLI: **contract-driven command generation** + `git` local passthrough
(platform token never leaves the process; zero exposure).

- Reads the server's `/openapi.json` (OpenAPI 3.x) and auto-generates `grape <group> <verb>` commands.
- **Add a server endpoint → re-fetch the contract → the CLI gains the command automatically, no source changes.**
- Auth reuses the grape token (Bearer by default) from config / env, attached automatically.

---

## Install

```bash
pip install -e .                               # from repo root (editable; recommended)
/opt/grape-cli/bin/pip install -e /path/to/grape-cli   # or a dedicated venv
```

Verify with `grape --version`.

---

## Configuration & token

Precedence (highest first):
`--token / --base-url / --timeout` (one-shot, process-only) > `GRAPE_SESSION_TOKEN` >
`GRAPE_API_TOKEN` / `GRAPE_BASE_URL` > `~/.grape/config.json`.

| Source | Example | Notes |
|--------|---------|-------|
| One-shot args (**recommended**) | `grape --token tk_xxx tasks mine`<br>`grape --base-url https://grape.example.com --grape-api-token grape_xxx skills list --json-out` | Never persisted; `--token` / `--grape-api-token` / `--grape_api_token` are synonyms; `--timeout` sets request timeout (default 30s) |
| Env vars | `export GRAPE_SESSION_TOKEN=tk_xxx` | `tk_` session token (task-level, auto-expires); `grape_` long-lived user key; `GRAPE_BASE_URL` default `http://localhost:8000` |
| Config file | `{ "base_url": "...", "token": "" }` in `~/.grape/config.json` | Persistent defaults; prefer env vars for token |

> Without a token the CLI prompts you to configure one.

---

## Commands

### Global

```bash
grape --help                  # contract groups + built-ins (git/api/refresh/commands)
grape commands [pattern]      # list contract commands; pipe to filter: grape commands | grep issue
grape refresh                 # force re-fetch the latest OpenAPI contract and cache it
grape tasks wait --task-id 56 --timeout 120 --interval 3   # poll until terminal state
grape --timeout 300 tasks mine                             # request timeout (default 30s; git unaffected)
```

### Contract-driven commands (automatic)

Shape: `grape <group> <verb> [--options...]`, derived from `operationId`:

```bash
grape tasks mine --status active --json-out        # GET  /api/tasks/mine?status=active
grape tasks create --json '{"repo_key":"o/r","title":"x","description":"y"}'
grape git-repo issues list --owner o --repo r --state open --json-out
```

- `query` / `path` params → `--<name>`; `requestBody` → `--json '<JSON>'`; `--json-out` → single-line machine-readable JSON.
- Discover: `grape <group> --help` / `grape <group> <verb> --help`.

### git (local execution, zero token exposure)

`grape git` is a **native git passthrough**: the token is fetched in-process via
`/git-credential` and injected with `GIT_CONFIG` env vars — never on the command line,
never written to disk, invisible to the agent.

```bash
grape git --repo owner/repo status
grape git --repo owner/repo checkout -b feat/issue-7
grape git --repo owner/repo commit -m "fix: ..."
grape git --repo owner/repo push feat/issue-7
grape git status                # without --repo: run git in the current directory
```

### api (generic fallback)

For endpoints not covered by the contract:

```bash
grape api GET /api/scenes
grape api POST /api/tasks/create -d '{"repo_key":"o/r","title":"x"}'
```

---

## Quick start

```bash
# One-shot (no env vars required)
grape --base-url https://grape.example.com --token tk_xxx skills list --json-out

# Common setup, then explore
export GRAPE_BASE_URL=https://grape.example.com
export GRAPE_SESSION_TOKEN=tk_xxx    # or: export GRAPE_API_TOKEN=grape_xxx
grape commands | head -40
grape skills list --json-out
```

---

## Exit codes

`0` success · `1` generic/config error · `2` usage error ·
`>=400` HTTP status passthrough (e.g. `401`) · `130` Ctrl+C.

---

## Security

- No create/revoke token subcommands (prevents self-escalation); user-level API keys come from the Web UI.
- Tokens never appear in output/errors; git credentials injected via `GIT_CONFIG` stay in-process.
- `tk_` session tokens auto-expire with the task/session; `grape_` user keys can be revoked.