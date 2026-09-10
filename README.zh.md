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
  <a href="#配置与-token">配置与 Token</a> ·
  <a href="#命令">命令</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#开发与测试">开发与测试</a>
</p>

---

## grape CLI 是什么

grape CLI 是 [Grape](https://gitcode.com/grape-dev/grape) 平台的命令行客户端。它读取服务端
`/openapi.json`，自动生成 `grape <group> <verb>` 命令，并在本地以进程内凭据的方式运行原生
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

- **契约驱动命令** — OpenAPI 3.x `operationId` → click 命令树（`tasks_mine` → `grape tasks mine`）
- **三通道认证** — Bearer / `PRIVATE-TOKEN` / `?access_token=`，自动注入
- **本地 git 透传** — `grape git --repo owner/repo ...`，凭据经 `GIT_CONFIG` 注入
- **内置 `tasks wait`** — 轮询任务直至终态（`completed` / `failed` / `cancelled`）
- **通用 `api` 兜底** — 直接调用尚未生成命令的任意契约端点
- **机器可读输出** — `--json-out` 输出单行 JSON，供 worker 解析

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

## 配置与 Token

配置优先级（较高的优先）：
`--token / --base-url / --timeout`（一次性参数，仅本次进程）> `GRAPE_SESSION_TOKEN` >
`GRAPE_API_TOKEN` / `GRAPE_BASE_URL` > `~/.grape/config.json`。

| 来源 | 示例 | 说明 |
|------|------|------|
| 一次性参数（**推荐单次调用**） | `grape --token tk_xxx tasks mine`<br>`grape --base-url https://grape.example.com --grape-api-token grape_xxx skills list --json-out` | 不落盘；`--token` / `--grape-api-token` / `--grape_api_token` 同义；`--timeout` 设请求超时（默认 30s） |
| 环境变量 | `export GRAPE_SESSION_TOKEN=tk_xxx` | `tk_` 会话 token（任务级，自动失效）；`grape_` 长期用户 key；`GRAPE_BASE_URL` 缺省 `http://localhost:8000` |
| 配置文件 | `{ "base_url": "...", "token": "" }` 于 `~/.grape/config.json` | 持久默认值；token 建议用环境变量注入 |

> 无 token 时命令会提示配置 token。

## 命令

### 全局

```bash
grape --help                  # 命令组 + 内置（git/api/refresh/commands）
grape commands [pattern]      # 列出全部契约命令，可管道过滤：grape commands | grep issue
grape refresh                 # 强制拉取最新 OpenAPI 契约并缓存
grape tasks wait --task-id 56 --timeout 120 --interval 3   # 轮询任务至终态
grape --timeout 300 tasks mine                             # 请求超时上限（默认 30s；git 不受影响）
```

### 契约生成命令（自动）

命令形态：`grape <group> <verb> [--参数...]`，由 `operationId` 推导：

```bash
grape tasks mine --status active --json-out        # GET  /api/tasks/mine?status=active
grape tasks create --json '{"repo_key":"o/r","title":"x","description":"y"}'
grape git-repo issues list --owner o --repo r --state open --json-out
```

- `query` / `path` 参数 → `--<name>`；`requestBody` → `--json '<JSON 字符串>'`；`--json-out` → 单行机器可读 JSON。
- 可用性：`grape <group> --help` 查看动词；`grape <group> <verb> --help` 查看参数。
- 服务端 `/openapi.json` 不可达时，CLI 自动回退到内置契约快照（`grape refresh` 会显示来源）。

### git（本地执行，token 零暴露）

`grape git` 是 **git 原生命令透传**。它自动识别仓库——`clone` 从 URL 参数解析，其余从
当前目录的 `remote.origin.url` 解析——再把会话 token 换券成短期平台凭据，经 `GIT_CONFIG`
env 注入 git 子进程：**不进命令行、不落磁盘、agent 感知不到**。仅 gitcode.com 宿主注入；
换券失败仅告警、git 按本机原生行为执行。`grape git --help` 与 `git --help` 一致。

```bash
grape git status                                   # 本地命令（无需凭据）
grape git clone https://gitcode.com/owner/repo.git # 从 URL 识别仓库 → 注入凭据
grape git pull
grape git push
grape git checkout -b feat/issue-7
grape git commit -m "fix: ..."
```

### api（通用兜底）

契约未覆盖/特殊场景：

```bash
grape api GET /api/scenes
grape api POST /api/tasks/create -d '{"repo_key":"o/r","title":"x"}'
```

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

## 退出码

`0` 成功 · `1` 通用/配置错误 · `2` 用法错误 ·
`>=400` HTTP 状态透传（如 `401`） · `130` Ctrl+C。

## 安全约定

- CLI **不提供** create/revoke token 子命令（防自举越权）；用户级 API Key 由 Web UI 生成。
- token 不出现在输出/错误信息（`GIT_CONFIG` 注入的 git 凭据同样不外泄）。
- `tk_` 会话 token 随任务/会话自动失效；`grape_` 用户 key 可吊销。

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