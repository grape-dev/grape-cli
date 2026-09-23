# grape CLI Token 作用域

> 服务端规则（v2.1.0 契约，`x-token-scope` 为权威）：会话 token（`tk_`）用于 agent 日常执行；
> 账户/平台管理与**平台侧变更动作**归 `user_only`（`tk_` → 403）；`grape_` API Key 与 Web JWT 两者皆可。

## 三类凭据

| 凭据 | 环境变量 | 语义 | 何时用 |
|------|---------|------|--------|
| session_token（`tk_`） | `GRAPE_SESSION_TOKEN` | agent/worker 任务级临时凭据（自动注入） | **默认就用它**：Workflows / 只读 Agent Context / git-repo / tasks current |
| user API Key（`grape_`） | `GRAPE_API_TOKEN`（或 `--grape-api-token`） | 用户长期 Key（Web UI「API Tokens」生成） | 账户/平台管理、平台侧变更动作（改 Issue 状态、澄清、skills/chat/repos-managed 等） |
| JWT（Web 登录） | 浏览器登录态 | Web 页面身份 | 自动化场景一般不用 |

## 分类 × 作用域（命令级）

| 类/命令 | Scope | tk_(session) | grape_/JWT |
|---------|-------|:---:|:---:|
| **Core workflows** | | | |
| `tasks current` | session_only | ✅ | ❌ |
| `tasks complete` / `a2a handoff` / `tasks wait` | dual | ✅ | ✅ |
| **Agent Context（只读）** | | | |
| `issues list/detail/events/pipeline`、`issues status get`、`issues list attachments` | dual | ✅ | ✅ |
| `events detail` | dual | ✅ | ✅ |
| `knowledge list/detail/stats` | dual | ✅ | ✅ |
| **Agent Context（平台侧变更，user 层）** | | | |
| `issues mine`、`issues create/start/resume/cancel/status/confirm done`、`issues clarifications/clarify`、`issues upload/delete attachment`、`issues pipeline detail` | user_only | ❌ 403 | ✅ |
| `knowledge add refs batch` | user_only | ❌ 403 | ✅ |
| **Code & repositories** | | | |
| `git ...`（本地透传） | session_only | ✅ | ❌ |
| `git-repo ...`（全部） | session_only | ✅ | ❌ |
| `repos git credential` / `repos workspace` | session_only | ✅ | ❌ |
| **Account & platform** | | | |
| `scenes detail` | dual | ✅（agent 执行期读当前场景） | ✅ |
| `scenes list` | user_only | ❌ 403 | ✅ |
| `agents detail`、`chat conversations/messages`、`repos member/managed/deploy url`、`skills agent stats` | user_only | ❌ 403 | ✅ |
| `skills list/detail` | dual | ✅ | ✅ |

## 用哪个凭据（决策）

1. 任务环境默认注入 `tk_` → 先用它覆盖：Core workflows、只读 Agent Context、git-repo、`tasks current`。
2. 看到 `HTTP 403: ... 该接口不支持会话 token / use GRAPE_API_TOKEN`（`user_only`）：
   → 换 `GRAPE_API_TOKEN`（`grape_`）再执行；或选择**平台侧只读路径**规避（如查读用 `issues list/detail/events/pipeline`，改状态交给用户层）。
3. 看到 `HTTP 403: ... session token (tk_) only`（`session_only`，git-repo / tasks current）：
   → 用 `GRAPE_SESSION_TOKEN`（`tk_`），不要用 API Key。

## CLI 上的可见提示

- `grape --help / grape <group> --help`：命令列表内嵌 `session 403 → grape_/JWT` / `session-only` 标注。
- `grape <group> <verb> --help`：首行含 scope，另有 `Token scope: ...` 行。
- 运行时 403：CLI 追加英文行动指引（换 `grape_`/JWT 或换 `tk_`）。
- `GRAPE_CLI_MODE=WORKER` 时 `user_only` 命令不出现在帮助里且运行时被守卫拦截。