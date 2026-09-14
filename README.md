<h1 align="center">grape CLI</h1>

<p align="center">English | <a href="README.zh.md">中文</a></p>

<p align="center">
  <strong>Contract-driven CLI for the Grape Agentic DevOps platform — zero token exposure</strong>
  <br>
  Point it at any Grape server, and new commands appear automatically.
</p>

<p align="center">
  <a href="#what-is-grape-cli">What is grape CLI</a> ·
  <a href="#the-problem">The Problem</a> ·
  <a href="#core-features">Core Features</a> ·
  <a href="#install">Install</a> ·
  <a href="#configuration--token">Configuration & Token</a> ·
  <a href="#commands">Commands</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#development--testing">Development & Testing</a>
</p>

---

## What is grape CLI

Grape CLI is the command-line client for the [Grape](https://gitcode.com/grape-dev/grape) platform.
It reads the server's `/openapi.json`, auto-generates `grape <group> <verb>` commands, and runs
native `git` operations locally with credentials kept strictly in-process.

**In one sentence: add a server endpoint → re-fetch the contract → the CLI gains the command, no source changes.**

## The Problem

Interacting with a contract-driven API usually means hand-written `curl`, fragile scripts, and
tokens leaking into shell history:

| | Manual | grape CLI |
|-|--------|-----------|
| Call a new endpoint | Write `curl` + parse JSON by hand | `grape <group> <verb>` auto-generated from OpenAPI |
| Auth | Copy tokens into shell history / files | Token from one-shot args, env, or config — attached automatically |
| Run git against the platform | Persist remote credentials on disk | `grape git` injects creds in-process, never persisted |
| Server API changes | Update every client script | Re-fetch contract — CLI updates itself |

## Core Features

- **Contract-driven commands** — OpenAPI 3.x `operationId` → click command tree (`tasks_mine` → `grape tasks mine`)
- **Three auth channels** — Bearer / `PRIVATE-TOKEN` / `?access_token=`, injected automatically
- **Native git passthrough** — `grape git --repo owner/repo ...` with `GIT_CONFIG`-injected credentials
- **Built-in `tasks wait`** — poll a task until a terminal state (`completed` / `failed` / `cancelled`)
- **Machine-readable output** — `--json-out` for single-line JSON consumed by workers

## Install

Clone or download the CLI source first:

```bash
git clone https://gitcode.com/grape-dev/grape-cli.git
cd grape-cli

# From repo root (editable; recommended)
pip install -e .
# Or a dedicated venv (isolated from the system)
python3 -m venv /opt/grape-cli
/opt/grape-cli/bin/pip install -e /path/to/grape-cli
```

Verify with `grape --version`. Requires Python >= 3.10.

## Configuration & Token

Precedence (highest first):
`--token / --base-url / --timeout` (one-shot, process-only) > `GRAPE_SESSION_TOKEN` >
`GRAPE_API_TOKEN` / `GRAPE_BASE_URL` > `~/.grape/config.json`.

| Source | Example | Notes |
|--------|---------|-------|
| One-shot args (**recommended**) | `grape --token tk_xxx tasks mine`<br>`grape --base-url https://grape.example.com --grape-api-token grape_xxx skills list --json-out` | Never persisted; `--token` / `--grape-api-token` / `--grape_api_token` are synonyms; `--timeout` sets request timeout (default 30s) |
| Env vars | `export GRAPE_SESSION_TOKEN=tk_xxx` | `tk_` session token (task-level, auto-expires); `grape_` long-lived user key; `GRAPE_BASE_URL` default `http://localhost:8000` |
| Config file | `{ "base_url": "...", "token": "" }` in `~/.grape/config.json` | Persistent defaults; prefer env vars for token |

> Without a token the CLI prompts you to configure one.

## Commands

### Global

```bash
grape --help                  # contract groups + built-ins (git/refresh/commands)
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
- If neither the server's `/static/openapi.json` nor `/openapi.json` is reachable, the CLI falls back to a bundled contract snapshot. Contract fetch priority: `{server}/static/openapi.json` → `/openapi.json` → bundled (`grape refresh` shows the source).

### git (local execution, zero token exposure)

`grape git` is a **native git passthrough**. It auto-detects the repo — from the
`clone` URL argument, or from the current directory's `remote.origin.url` — exchanges
the session token for a short-lived platform credential in-process, and injects it via
`GIT_CONFIG` env vars: **never on the command line, never written to disk, invisible to
the agent**. Only gitcode.com hosts get credentials; on an exchange failure you get a
warning and git runs natively. `grape git --help` is identical to `git --help`.

```bash
grape git status                                   # local command (no credential needed)
grape git clone https://gitcode.com/owner/repo.git # repo from URL → credential injected
grape git pull
grape git push
grape git checkout -b feat/issue-7
grape git commit -m "fix: ..."
```

## Quick Start

```bash
# One-shot (no env vars required)
grape --base-url https://grape.example.com --token tk_xxx skills list --json-out

# Common setup, then explore
export GRAPE_BASE_URL=https://grape.example.com
export GRAPE_SESSION_TOKEN=tk_xxx    # or: export GRAPE_API_TOKEN=grape_xxx
grape commands | head -40
grape skills list --json-out
```

## Exit Codes

`0` success · `1` generic/config error · `2` usage error ·
`>=400` HTTP status passthrough (e.g. `401`) · `130` Ctrl+C.

## Security

- No create/revoke token subcommands (prevents self-escalation); user-level API keys come from the Web UI.
- Tokens never appear in output/errors; git credentials injected via `GIT_CONFIG` stay in-process.
- `tk_` session tokens auto-expire with the task/session; `grape_` user keys can be revoked.

## Development & Testing

```bash
pip install -e .[dev]
python -m pytest test/ -q
```

Test coverage: config precedence, HTTP client (auth/errors), contract loading & caching,
command generation, CLI end-to-end, and git passthrough (credential injection / exit codes).

## Contributing

1. **Open an Issue** — describe the problem or feature
2. **Fork & Develop** — work on a feature branch (`feat/`, `fix/`, `refactor/`, `docs/`, `chore/`)
3. **Add Tests** — include pytest tests for new behavior
4. **Submit a PR** — describe changes, test results, and linked Issue

## Feedback

- **GitCode Issues**: https://gitcode.com/grape-dev/grape-cli/issues
  - Bugs: include environment, repro steps, and logs
  - Feature suggestions: describe the use case and expected behavior