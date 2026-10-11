<h1 align="center">grape CLI</h1>

<p align="center">English | <a href="README.zh.md">中文</a></p>

<p align="center">
  <strong>Contract-driven CLI for the Grape Agentic DevOps platform — zero token exposure</strong>
  <br>
  Point it at any Grape server — new commands appear automatically.
</p>

<p align="center">
  <a href="#what-is-grape-cli">What is grape CLI</a> ·
  <a href="#the-problem">The Problem</a> ·
  <a href="#core-features">Core Features</a> ·
  <a href="#install">Install</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#configuration--token">Configuration & Token</a> ·
  <a href="#commands">Commands</a> ·
  <a href="#exit-codes">Exit Codes</a> ·
  <a href="#security">Security</a> ·
  <a href="#development--testing">Development & Testing</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

## What is grape CLI

Grape CLI is the command-line client for the [Grape](https://gitcode.com/grape-dev/grape) platform.
It reads the server's OpenAPI contract, auto-generates `grape <group> <verb>` commands, and runs
native `git` operations locally with credentials kept strictly in-process.

**In one sentence: add a server endpoint → re-fetch the contract → the CLI gains the command, no source changes.**

## The Problem

Interacting with a contract-driven API usually means hand-written `curl`, fragile scripts, and
tokens leaking into shell history:

| | Manual | grape CLI |
|-|--------|-----------|
| Call a new endpoint | Write `curl` + parse JSON by hand | `grape <group> <verb>` auto-generated from OpenAPI |
| Auth | Copy tokens into shell history / files | Token from one-shot args, env, or config — attached automatically |
| Run git against the platform | Persist remote credentials on disk | `grape git` injects credentials in-process, never persisted |
| Server API changes | Update every client script | Re-fetch contract — CLI updates itself |

## Core Features

- **Contract-driven commands** — OpenAPI 3.x `operationId` becomes a command tree (`tasks_current` → `grape tasks current`); the command set mirrors the connected server.
- **Automatic auth injection** — Bearer token attached by default (client also supports `PRIVATE-TOKEN` / `?access_token=` channels).
- **Native git passthrough** — `grape git` runs real `git`, auto-detects the repo, and injects a short-lived credential via `GIT_CONFIG` env vars — never on the command line, never on disk.
- **Built-in `tasks wait`** — poll a task until a terminal state (`completed` / `failed` / `cancelled`).
- **Machine-readable output** — `--json-out` emits single-line JSON for workers and scripts.
- **Mode-aware command sets** — `GRAPE_CLI_MODE` (WORKER / USER / ALL) filters commands by token scope (dual / session-only / user-only).

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

## Configuration & Token

Precedence (highest first):
`--token / --base-url / --timeout` (one-shot, process-only) > `GRAPE_SESSION_TOKEN` >
`GRAPE_API_TOKEN` / `GRAPE_BASE_URL` > `~/.grape/config.json`.

| Source | Example | Notes |
|--------|---------|-------|
| One-shot args (**recommended**) | `grape --token tk_xxx tasks current`<br>`grape --base-url https://grape.example.com --grape-api-token grape_xxx skills list --json-out` | Never persisted; `--token` / `--grape-api-token` / `--grape_api_token` are synonyms; `--timeout` sets the request timeout (default 30s, git unaffected) |
| Env vars | `export GRAPE_SESSION_TOKEN=tk_xxx` | `tk_` session token (task-level, auto-expires); `grape_` long-lived user key; `GRAPE_BASE_URL` (fallback `GRAPE_SERVER_URL`), default `http://localhost:8000`; `GRAPE_CLI_MODE=WORKER\|USER\|ALL` (default ALL) |
| Config file | `{ "base_url": "...", "token": "" }` in `~/.grape/config.json` | Persistent defaults; prefer env vars for tokens |

- In `GRAPE_CLI_MODE=USER`, `GRAPE_API_TOKEN` takes priority over `GRAPE_SESSION_TOKEN`.
- Without a token, commands fail with a message telling you how to configure one.

## Commands

### Global

```bash
grape --version / -v          # version
grape --help                  # contract groups + built-ins (git/refresh/commands)
grape commands [pattern]      # list contract commands; pipe to filter: grape commands | grep issue
grape refresh                 # force-fetch the newest OpenAPI contract and refresh the cache
grape tasks wait --task-id 56 --timeout 120 --interval 3   # poll a task until terminal state
grape --timeout 300 tasks current                          # request timeout (default 30s; git unaffected)
```

### Contract-driven commands (automatic)

Shape: `grape <group> <verb> [--options...]`, derived from `operationId`:

```bash
grape tasks current --json-out
grape tasks complete --json '{"result_text":"done","next_step":"a2a_issue"}'
grape issues list --owner o --repo r --json-out
grape git-repo issues list --owner o --repo r --state open --json-out
grape git-repo contents --owner o --repo r --path README.md --raw   # base64-decoded file text
grape skills upload --file skill.zip --scope user --agent_type coding
```

- `query` / `path` params → `--<name>`; `requestBody` → `--json '<JSON>'`; `--json-out` → single-line machine-readable JSON.
- Long bodies: `--json @file.json` reads from a file, `--json @-` reads from stdin (no shell escaping).
- Multipart endpoints (uploads) use `--file <path>` plus form-field options; `git-repo contents --raw` decodes a file to raw text.
- `--json` bodies are validated against the contract — unknown fields / missing required fields fail fast and print the allowed field list.
- Discover: `grape <group> --help` (verbs) then `grape <group> <verb> --help` (params, body fields, examples). Unknown verbs get a `Did you mean ...` suggestion.
- Contract source priority: `{server}/static/openapi.json` → `{server}/openapi.json` → bundled snapshot. Fetched contracts are cached in `~/.grape/openapi-<version>.json`; `grape refresh` bypasses the cache and prints the source.

The exact groups/verbs mirror the connected server's contract — run `grape commands` to see what is live.

### git (local execution, zero token exposure)

`grape git` is a **native git passthrough**. It auto-detects the repo — from the
`clone` URL argument, or from the current directory's `remote.origin.url` — exchanges
the session token for a short-lived platform credential in-process, and injects it via
`GIT_CONFIG` env vars: **never on the command line, never written to disk, invisible to
the agent**. Only gitcode.com hosts get credentials; on an exchange failure you get a
warning and git runs natively. `grape git --help` is identical to `git --help`.

```bash
grape git status                                   # local command (no credential needed)
grape git clone https://gitcode.com/owner/repo.git # repo parsed from URL → credential injected
grape git pull                                     # repo parsed from remote.origin.url
grape git push
grape git checkout -b feat/issue-7
grape git commit -m "fix: ..."
```

### Token scopes & GRAPE_CLI_MODE

Each contract operation carries a token scope: `dual`, `session_only`, or `user_only`.

- `session_only` (e.g. repo workspace / git-credential) — needs a `tk_` session token; API keys are rejected (403).
- `user_only` (e.g. agents detail, skills list, chat) — a `tk_` session token is rejected with a hint to set `GRAPE_API_TOKEN` / use a Web JWT.
- `GRAPE_CLI_MODE` filters `grape --help` and `grape commands` to what the current role may run: `WORKER` (session-only + dual), `USER` (user-only + dual), `ALL` (everything, default).

## Exit Codes

`0` success · `1` generic/config error · `2` usage error ·
`>=400` HTTP status passthrough (e.g. `401`) · `130` Ctrl+C.

## Security

- No create/revoke token subcommands (prevents self-escalation); user-level API keys come from the Web UI.
- Tokens never appear in output/errors; git credentials injected via `GIT_CONFIG` stay in-process and are never written to disk.
- `tk_` session tokens auto-expire with the task/session; `grape_` user keys can be revoked.
- `grape git` injects credentials only for gitcode.com hosts and degrades to plain native git (with a warning) if an exchange fails.

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