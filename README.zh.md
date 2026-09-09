# grape CLI

Agentic DevOps 命令行工具：**契约驱动命令生成** + `git` 本地传输（平台 token 零暴露）。

- 读服务端 `/openapi.json`（OpenAPI 3.x）自动生成 `grape <group> <verb>` 命令；
- **新增服务端接口 → 重新拉契约 → CLI 自动获得新命令，无需改 CLI 源码**；
- 认证复用 grape token（默认 Bearer），从配置/环境变量读取，自动携带。

---

## 安装

```bash
pip install -e .                               # 仓库根目录，editable（推荐）
/opt/grape-cli/bin/pip install -e /path/to/grape-cli   # 或独立 venv
```

装好验证：`grape --version`。

---

## 配置与 token

配置优先级（较高的优先）：
`--token / --base-url / --timeout`（一次性参数，仅本次进程）> `GRAPE_SESSION_TOKEN` >
`GRAPE_API_TOKEN` / `GRAPE_BASE_URL` > `~/.grape/config.json`。

| 来源 | 示例 | 说明 |
|------|------|------|
| 一次性参数（**推荐单次调用**） | `grape --token tk_xxx tasks mine`<br>`grape --base-url https://grape.example.com --grape-api-token grape_xxx skills list --json-out` | 不落盘；`--token` / `--grape-api-token` / `--grape_api_token` 同义；`--timeout` 设请求超时（默认 30s） |
| 环境变量 | `export GRAPE_SESSION_TOKEN=tk_xxx` | `tk_` 会话 token（任务级，自动失效）；`grape_` 长期用户 key；`GRAPE_BASE_URL` 缺省 `http://localhost:8000` |
| 配置文件 | `{ "base_url": "...", "token": "" }` 于 `~/.grape/config.json` | 持久默认值；token 建议用环境变量注入 |

> 无 token 时命令会提示配置 token。

---

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

### git（本地执行，token 零暴露）

`grape git` 是 **git 原生命令透传**：token 只在 CLI 进程内经 `/git-credential` 获取，
经 git 的 `GIT_CONFIG` env 注入——**不进命令行、不落磁盘、agent 感知不到**。

```bash
grape git --repo owner/repo status
grape git --repo owner/repo checkout -b feat/issue-7
grape git --repo owner/repo commit -m "fix: ..."
grape git --repo owner/repo push feat/issue-7
grape git status                # 不指定 --repo：在当前目录直接执行 git
```

### api（通用兜底）

契约未覆盖/特殊场景：

```bash
grape api GET /api/scenes
grape api POST /api/tasks/create -d '{"repo_key":"o/r","title":"x"}'
```

---

## 快速上手指引

```bash
# 一次性调用（不设任何环境变量也行）
grape --base-url https://grape.example.com --token tk_xxx skills list --json-out

# 常用设置，然后探索
export GRAPE_BASE_URL=https://grape.example.com
export GRAPE_SESSION_TOKEN=tk_xxx    # 或 export GRAPE_API_TOKEN=grape_xxx
grape commands | head -40
grape skills list --json-out
```

---

## 退出码

`0` 成功 · `1` 通用/配置错误 · `2` 用法错误 ·
`>=400` HTTP 状态透传（如 `401`） · `130` Ctrl+C。

---

## 安全约定

- CLI **不提供** create/revoke token 子命令（防自举越权）；用户级 API Key 由 Web UI 生成。
- token 不出现在输出/错误信息（`GIT_CONFIG` 注入的 git 凭据同样不外泄）。
- `tk_` 会话 token 随任务/会话自动失效；`grape_` 用户 key 可吊销。