---
name: grape-cli-guidance
version: 1.1.0
description: |
  快速学会使用 grape CLI 的指南技能。契约驱动命令发现、5 类命令分组、
  token 作用域（session/user key/JWT 用哪个，user_only vs session_only）、
  常见读写配方（git-repo/issues/tasks/a2a）、错误排查与反模式。
  适合任何首次接触 grape CLI 的 agent。命令以 `grape commands` 实际输出为准。
tools:
  - grape
---

# grape CLI 使用指南

## 核心原则（先读）

1. **命令是契约驱动的**：`grape <group> <verb> [--参数]` 由服务端 `/openapi.json`（或内置快照）动态生成。
   - 不确定命令 → 先**发现**，别猜名字；权威清单 = `grape commands`。
2. **token 决定你能做什么**：`GRAPE_SESSION_TOKEN`（`tk_`）= 会话级；`GRAPE_API_TOKEN`（`grape_`）= 用户级。
   - `session_only` 命令（git-repo/tasks current）仅 `tk_` 可用；`user_only` 命令（平台变更、skills/chat/repos 管理）对 `tk_` 返回 **403**，需切 `grape_`/JWT。详见 `references/token-scope.md`。
3. **读仓库用 `git-repo`，任务交接用 `tasks`/`a2a`，查上下文用 `issues`/`events`/`knowledge`，内部凭据用 `repos`。**
4. **平台侧只读走 `dual` 命令，变更动作留给用户层**：`issues list/detail/events/pipeline`（dual）可随便查、写评论走 `git-repo issues comments create`；`issues start/cancel/status/clarify/...` 是 `user_only`（改状态属用户/UI），agent 别硬改，改了也会 403。
5. **机器可读输出加 `--json-out`**；长 JSON 用 `--json @file.json`。

## 安装

```bash
# 全新机器：装 grape CLI（已装可跳过）
# `git+<URL>` = pip 的 VCS 直装协议：从 Git 仓库（而非 PyPI）克隆并安装
pip install git+https://gitcode.com/grape-dev/grape-cli.git
grape --version

# 本仓库编辑安装（开发用地）
# cd <grape-cli 源码目录> && pip install -e .[dev]
```

> agent 环境通常已安装并注入环境变量；仅确认 `which grape` 与 `grape --version` 即可。

## 配置（token 与地址）

优先级：`--token/--base-url/--timeout`（一次性参数，进程内）> 环境变量 > `~/.grape/config.json`。

```bash
export GRAPE_BASE_URL=https://grape.example.com   # 服务端地址（agent 环境已注入 GRAPE_SERVER_URL，自动回退）
export GRAPE_SESSION_TOKEN=tk_xxx                  # 会话级（默认用这个）
# export GRAPE_API_TOKEN=grape_xxx                 # 用户级（D 类账户/平台命令需要）
```

- 缺省 `GRAPE_BASE_URL` → `http://localhost:8000`；缺 token 调用会报 `HTTP 401 ... re-inject`。
- `~/.grape/config.json`：
  ```json
  { "base_url": "https://grape.example.com", "token": "" }
  ```
  建议 token 用环境变量注入，勿写文件。

## 一行速查

```bash
grape --help                       # 全部命令 + 分类 + token 作用域提示
grape commands [pattern]           # 列出可调用命令；过滤：grape commands issues
grape <group> --help               # 该组动词（含方法/body/Token scope/示例）
grape <group> <verb> --help        # 完整：参数 + Body fields + Examples
grape refresh                      # 重拉最新契约（或回退内置快照）
```

## 命令发现（step 1 必做）

- 顶层：`grape --help` 分 **5 类**（见 references/command-map.md）：Core workflows / Agent Context / Code & repositories / Account & platform / CLI utilities。
- 枚举：`grape commands`（只列**可调用**命令，可直接照抄）；要过滤用 `grape commands <pattern>`（**别用 `| grep`**）。
- 组内：`grape <group> --help`；单命令：`grape <group> <verb> --help` —— 注意看 **Body fields**（请求体允许字段）、**Token scope**、**Examples**。

## 常见配方

### 读仓库 / 文件（Code & repositories，session-only）
```bash
grape git-repo repo --owner o --repo r --json-out        # 仓库信息（clone_url/default_branch）
grape git-repo contents --owner o --repo r --json-out            # 根/目录列表
grape git-repo contents --owner o --repo r --path README.md --raw # 文件原文（自动 base64 解码）
grape git-repo tree --owner o --repo r --ref main --json-out      # 目录树
grape git-repo issues get --owner o --repo r --number 7 --json-out
grape git-repo issues comments create --owner o --repo r --number 7 --json '{"body":"<内容>"}'
```

### Issue / 事件 / 知识（Agent Context，只读 dual）
```bash
grape issues list --owner o --repo r --json-out
grape issues detail --owner o --repo r --number 7 --json-out
grape issues events --owner o --repo r --number 7 --json-out
grape issues pipeline --owner o --repo r --number 7 --json-out
grape events detail --event_id <seq> --json-out
grape knowledge list --json-out
grape knowledge detail --knowledge_id <id> --json-out   # 单条知识全文
grape knowledge stats --json-out                         # 知识统计
```
> 结构化结论/澄清写进**评论**（`git-repo issues comments create`），不要调用 `issues status/clarify` 这些 user_only 变更命令。

### 任务与交接（Core workflows）
```bash
grape tasks current --json-out              # 内省当前任务（session-only，agent 执行期用）
grape tasks complete --json '{"task_id":7,"result_text":"...","next_step":"a2a_issue"}'
grape tasks wait --task-id 7 --timeout 120  # 轮询到终态
grape a2a handoff --json '{"agent":"coding","payload":{"repository":"o/r","account":"<user>","issue_number":7,"context":"<ctx>"}}'
```

### 通用兜底查询（Account & platform，需 `grape_`/JWT）
```bash
export GRAPE_API_TOKEN=grape_xxx     # user_only 端点需用户级 Key / Web JWT
grape skills list --json-out
grape skills detail --skill_id <id> --json-out
grape repos managed --json-out
grape chat conversations --json-out
```

## 错误排查

| 现象 | 含义 | 处理 |
|------|------|------|
| `HTTP 401: ... re-inject` | token 无效/过期/缺失 | 重新注入 `GRAPE_SESSION_TOKEN` 或 `GRAPE_API_TOKEN` |
| `HTTP 403: ... 不支持会话 token / use GRAPE_API_TOKEN` | `user_only`（平台变更/管理）拒绝会话凭据 | 改用 `GRAPE_API_TOKEN`（`grape_`）或 Web JWT，或改走只读 `dual` 路径 |
| `HTTP 403: ... session token (tk_) only` | `session_only`（git-repo、tasks current）仅会话 | 使用 `GRAPE_SESSION_TOKEN` |
| `No such command 'X'. Did you mean: A, B?` | 命令名写错 | 按建议改；或 `grape commands <关键词>` 查 |
| `unknown request field(s): ... allowed for ...` | `--json` 字段不在请求体允许集 | 看 `grape <group> <verb> --help` 的 Body fields |
| `(path not found; try --path '' to list root)` | `contents` 路径不存在 | 先 `--path ""` 看根列表定位 |
| 命令在 `--help` 有但在 `grape commands` 缺 | 仅辅助/被过滤（或契约在刷新） | 以 `grape commands` 为准，必要时 `grape refresh` |

## 反模式（禁止）

- ❌ 凭印象/经验拼命令名或 `--参数` —— 先 `--help` 或 `grape commands`。
- ❌ `grape commands | grep ...` —— 用 `grape commands <pattern>`。
- ❌ 用 `tk_` 会话 token 打 `user_only` 接口（等 403 再疑惑）—— 换 `grape_`/JWT 或走只读路径。
- ❌ 给平台 Issue 改状态（`issues status/cancel/start/...` 属 user 层；写评论用 `git-repo issues comments create`）。
- ❌ 相信**已下架命令**（如 `tasks mine/status/start`、`auth profile`、`skills search/upload`）—— 先用 `grape commands` 确认。
- ❌ 大 JSON 手拼内联 —— 用 `--json @file.json`。

详细分组与 token 作用域见 `references/command-map.md`、`references/token-scope.md`。