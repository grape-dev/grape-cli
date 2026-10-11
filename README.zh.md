<h1 align="center">grape CLI</h1>

<p align="center"><a href="README.md">English</a> | 中文</p>

<p align="center">
  <strong>契约驱动的 Grape Agentic DevOps 平台命令行工具——token 零暴露</strong>
  <br>
  指向任意 Grape 服务端，新命令自动出现。
</p>

<p align="center">
  <a href="#grape-cli-是什么">grape CLI 是什么</a> ·
  <a href="#问题">问题</a> ·
  <a href="#核心特性">核心特性</a> ·
  <a href="#安装">安装</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#配置与-token">配置与 Token</a> ·
  <a href="#命令">命令</a> ·
  <a href="#退出码">退出码</a> ·
  <a href="#安全约定">安全约定</a> ·
  <a href="#开发与测试">开发与测试</a> ·
  <a href="#如何贡献">如何贡献</a>
</p>

---

## grape CLI 是什么

grape CLI 是 [Grape](https://gitcode.com/grape-dev/grape) 平台**主要面向 Agent 设计**的命令行客户端：
围绕代码仓的 DevOps 流程，为 Agent 提供该代码仓的全部上下文，让 Agent 更精准地理解项目背景，
从而更精准地实现开发者针对该项目的需求。它读取服务端
OpenAPI 契约，自动生成 `grape <group> <verb>` 命令，并在本地以进程内凭据的方式运行原生
`git` 操作。

**一句话：新增服务端接口 → 重新拉契约 → CLI 自动获得新命令，无需改源码。**

## 问题

面向契约驱动的 API 做交互，通常是手写 `curl`、零散脚本，token 还容易泄漏进 shell 历史：

| | 手工方式 | grape CLI |
|-|----------|-----------|
| 调用新接口 | 手写 `curl` + 手工解析 JSON | 依据 OpenAPI 自动生成 `grape <group> <verb>` |
| 认证 | token 复制进 shell 历史/文件 | 从一次性参数、环境变量或配置读取，自动携带 |
| 对平台跑 git | 凭据落盘持久化 | `grape git` 进程内注入凭据，永不落盘 |
| 服务端接口变更 | 每个客户端脚本都要改 | 重拉契约，CLI 自我更新 |

## 核心特性

- **契约驱动命令** — OpenAPI 3.x `operationId` → click 命令树（`tasks_current` → `grape tasks current`）；命令集合与所连服务端契约保持一致
- **自动认证注入** — 默认自动携带 Bearer token（客户端同时支持 `PRIVATE-TOKEN` / `?access_token=` 通道）
- **本地 git 透传** — `grape git` 运行真实 git，自动识别仓库，凭据经 `GIT_CONFIG` 注入子进程——不进命令行、不落磁盘
- **内置 `tasks wait`** — 轮询任务直至终态（`completed` / `failed` / `cancelled`）
- **机器可读输出** — `--json-out` 输出单行 JSON，供 worker 与脚本解析
- **按模式过滤命令** — `GRAPE_CLI_MODE`（WORKER / USER / ALL）按 token 作用域（dual / session-only / user-only）过滤命令集合

## 安装

先克隆或下载 CLI 源码：

```bash
git clone https://gitcode.com/grape-dev/grape-cli.git
cd grape-cli

# 仓库根目录，editable（推荐）
pip install -e .
# 或独立 venv
python3 -m venv /opt/grape-cli
/opt/grape-cli/bin/pip install -e /path/to/grape-cli
```

装好验证：`grape --version`。需要 Python >= 3.10。

## 快速开始

```bash
# 一次性调用（不设任何环境变量也行）
grape --base-url https://grape.example.com --token tk_xxx skills list --json-out

# 常用设置，然后探索
export GRAPE_BASE_URL=https://grape.example.com
export GRAPE_SESSION_TOKEN=tk_xxx    # 或 export GRAPE_API_TOKEN=grape_xxx
grape commands | head -40
grape skills list --json-out
```

## 配置与 Token

配置优先级（较高的优先）：
`--token / --base-url / --timeout`（一次性参数，仅本次进程）> `GRAPE_SESSION_TOKEN` >
`GRAPE_API_TOKEN` / `GRAPE_BASE_URL` > `~/.grape/config.json`。

| 来源 | 示例 | 说明 |
|------|------|------|
| 一次性参数（**推荐单次调用**） | `grape --token tk_xxx tasks current`<br>`grape --base-url https://grape.example.com --grape-api-token grape_xxx skills list --json-out` | 不落盘；`--token` / `--grape-api-token` / `--grape_api_token` 同义；`--timeout` 设请求超时（默认 30s，git 不受影响） |
| 环境变量 | `export GRAPE_SESSION_TOKEN=tk_xxx` | `tk_` 会话 token（任务级，自动失效）；`grape_` 长期用户 key；`GRAPE_BASE_URL`（回退 `GRAPE_SERVER_URL`），缺省 `http://localhost:8000`；`GRAPE_CLI_MODE=WORKER\|USER\|ALL`（缺省 ALL） |
| 配置文件 | `{ "base_url": "...", "token": "" }` 于 `~/.grape/config.json` | 持久默认值；token 建议用环境变量注入 |

- `GRAPE_CLI_MODE=USER` 时 `GRAPE_API_TOKEN` 优先于 `GRAPE_SESSION_TOKEN`。
- 无 token 时命令会报错，错误信息会提示如何配置 token。

## 命令

### 全局

```bash
grape --version / -v          # 版本号
grape --help                  # 命令组 + 内置（git/refresh/commands）
grape commands [pattern]      # 列出全部契约命令，可管道过滤：grape commands | grep issue
grape refresh                 # 强制拉取最新 OpenAPI 契约并刷新缓存
grape tasks wait --task-id 56 --timeout 120 --interval 3   # 轮询任务至终态
grape --timeout 300 tasks current                          # 请求超时上限（默认 30s；git 不受影响）
```

### 契约生成命令（自动）

命令形态：`grape <group> <verb> [--参数...]`，由 `operationId` 推导：

```bash
grape tasks current --json-out
grape tasks complete --json '{"result_text":"done","next_step":"a2a_issue"}'
grape issues list --owner o --repo r --json-out
grape git-repo issues list --owner o --repo r --state open --json-out
grape git-repo contents --owner o --repo r --path README.md --raw   # base64 自动解码为文件原文
grape skills upload --file skill.zip --scope user --agent_type coding
```

- `query` / `path` 参数 → `--<name>`；`requestBody` → `--json '<JSON>'`；`--json-out` → 单行机器可读 JSON。
- 长请求体：`--json @file.json` 从文件读取，`--json @-` 从 stdin 读取（免转义）。
- multipart 上传类端点用 `--file <路径>` + 表单字段参数；`git-repo contents --raw` 把单文件内容解码为原文。
- `--json` 请求体会按契约校验——未知字段 / 缺失必填字段立即报错，并列出允许字段。
- 可用性：`grape <group> --help` 查看动词，`grape <group> <verb> --help` 查看参数、body 字段与示例；动词拼写错误会有 `Did you mean ...` 提示。
- 契约拉取优先级：`{server}/static/openapi.json` → `{server}/openapi.json` → 内置快照；拉取结果缓存于 `~/.grape/openapi-<version>.json`，`grape refresh` 绕过缓存并打印来源。

具体 `group`/`verb` 与所连服务端契约保持一致——运行 `grape commands` 查看当前可用命令。

### git（本地执行，token 零暴露）

`grape git` 是 **git 原生命令透传**。它自动识别仓库——`clone` 从 URL 参数解析，其余从
当前目录的 `remote.origin.url` 解析——再把会话 token 换券成短期平台凭据，经 `GIT_CONFIG`
env 注入 git 子进程：**不进命令行、不落磁盘、agent 感知不到**。仅 gitcode.com 宿主注入；
换券失败仅告警、git 按本机原生行为执行。`grape git --help` 与 `git --help` 一致。

```bash
grape git status                                   # 本地命令（无需凭据）
grape git clone https://gitcode.com/owner/repo.git # 从 URL 识别仓库 → 注入凭据
grape git pull                                     # 从 remote.origin.url 识别仓库
grape git push
grape git checkout -b feat/issue-7
grape git commit -m "fix: ..."
```

### token 作用域与 GRAPE_CLI_MODE

每个契约操作携带 token 作用域：`dual` / `session_only` / `user_only`。

- `session_only`（如 repo workspace / git-credential）——必须用 `tk_` 会话 token，API key 会被拒（403）。
- `user_only`（如 agents detail、skills list、chat）——`tk_` 会话 token 被拒，并按提示改用 `GRAPE_API_TOKEN` / Web JWT。
- `GRAPE_CLI_MODE` 过滤 `grape --help` 与 `grape commands` 到当前角色可用的命令：`WORKER`（session-only + dual）、`USER`（user-only + dual）、`ALL`（全部，缺省）。

## 退出码

`0` 成功 · `1` 通用/配置错误 · `2` 用法错误 ·
`>=400` HTTP 状态透传（如 `401`） · `130` Ctrl+C。

## 安全约定

- CLI **不提供** create/revoke token 子命令（防自举越权）；用户级 API Key 由 Web UI 生成。
- token 不出现在输出/错误信息（`GIT_CONFIG` 注入的 git 凭据同样不外泄、不落盘）。
- `tk_` 会话 token 随任务/会话自动失效；`grape_` 用户 key 可吊销。
- `grape git` 仅对 gitcode.com 宿主注入凭据，换券失败时降级为本机原生 git（并给出告警）。

## 开发与测试

```bash
pip install -e .[dev]
python -m pytest test/ -q
```

测试覆盖：配置优先级、HTTP 客户端（认证/错误映射）、契约加载与缓存、命令生成、CLI 端到端、
git 透传（凭据注入/退出码）。

## 如何贡献

1. **提 Issue** — 描述要解决的问题或功能
2. **Fork 与开发** — 在特性分支上开发（`feat/`、`fix/`、`refactor/`、`docs/`、`chore/`）
3. **补测试** — 新行为附上 pytest 用例
4. **提交 PR** — 说明变更、测试结果与关联 Issue

## 反馈问题

- **GitCode Issues**：https://gitcode.com/grape-dev/grape-cli/issues
  - Bug：请附运行环境、复现步骤与日志
  - 功能建议：描述使用场景与预期行为