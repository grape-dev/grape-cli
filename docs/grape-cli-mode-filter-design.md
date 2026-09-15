# grape CLI 模式过滤设计（GRAPE_CLI_MODE）

> 状态：✅ 已实施（2026-09-15）
> 目的：按 token 类型隐藏当前模式不可用的命令，减少 agent 因"拿 session 打 user_only / 拿 user key 打 session_only"
> 而 403 重试的次数。
> 控制：环境变量 `GRAPE_CLI_MODE`：`WORKER` / `USER` / `ALL`。
> scope 数据源：**服务端契约 `x-token-scope`**（已实现：`docs/weekly-03/openapi-x-token-scope-design.md`），
> CLI 静态 `token-scope.json` 降级为缺省兜底。

---

## 〇、scope 取值（align 服务端三值）

服务端 `custom_openapi` 已为每个公开 op 写 `x-token-scope`，契约分布（2026-09-15）：
**user_only 171 / session_only 25 / dual 19（共 215 ops）**。

| scope | 含义 | 代表端点 | CLI 旧命名 |
|-------|------|----------|-----------|
| `dual` | session + user(API Key/JWT) 均可 | tasks-mine / a2a / issues-* pipeline 等核心 agent 流程 | `allow` |
| `session_only` | 仅 `tk_` 可用（API Key/JWT 403） | git-repo/*（21）、repos git_credential/workspace（2） | `session_only` |
| `user_only` | session 403；需 `grape_`/JWT | skills/agents/auth/chat/repos member+managed+deploy（171） | `user_only` |

## 一、模式 × 命令 scope

| scope | WORKER（tk_） | USER（grape_/JWT） | ALL |
|---|:---:|:---:|:---:|
| `dual` | ✅ | ✅ | ✅ |
| `session_only` | ✅ | ❌ | ✅ |
| `user_only` | ❌ | ✅ | ✅ |
| 工具（commands/refresh） | ✅ | ✅ | ✅ |

- **WORKER = dual + session_only**（隐藏 user_only）
- **USER = dual + user_only**（隐藏 session_only）
- **ALL = 全部**（默认，向后兼容）

> 动机验证：契约中 user_only 达 171 条，worker（session）执行不了；WORKER 模式只暴露
> dual(19)+session_only(25) ≈ 44 条可执行命令，agent 命令面显著变干净。

## 二、判定逻辑

```
mode = (os.environ.get("GRAPE_CLI_MODE") or "ALL").upper()   # 非法值回落 ALL
allowed(mode, scope):
    mode == "ALL"            -> True
    scope == "dual"          -> True
    mode == "WORKER"         -> scope in ("dual", "session_only")
    mode == "USER"           -> scope in ("dual", "user_only")
```

- **scope 读取顺序**（`_token_scope(meta)`）：
  1) `meta["op"].get("x-token-scope")` → 直接用（契约权威，autogen/可漂移最小）
  2) 缺省 → 回落现有 `token-scope.json` 表 / `gitrepo_*` 前缀（静态兜底）
- 内置 `git`=session_only（WORKER/ALL 显示，USER 隐藏）；`commands`/`refresh`=dual 恒显示
- 内置快照同步回填 `x-token-scope`（离线/兜底也可过滤）

### 二·1 token 选择与 mode 对齐（GRAPE_SESSION_TOKEN 与 GRAPE_API_TOKEN 并存时）

现状 `config.resolve` 优先级：`CLI 参数 > GRAPE_SESSION_TOKEN > GRAPE_API_TOKEN > config.json`（**session 恒优先**）。

当启用 `GRAPE_CLI_MODE` 时，token 选择应随 mode：

| mode | token 优先级 | 说明 |
|------|------------|------|
| WORKER | `tk_` > `grape_` | 会话优先（与过滤一致） |
| USER | `grape_` > `tk_` | **用户 key 优先**——否则 USER 模式下"显示 D 类命令但发的是 tk_"仍 403，帮助与行为脱节 |
| ALL（默认） | `tk_` > `grape_` | 向后兼容现状 |

守卫补充：`mode=USER` 但未设 `GRAPE_API_TOKEN`（仅存 `tk_`）→ 警告
`GRAPE_CLI_MODE=USER but GRAPE_API_TOKEN is missing; falling back to session token`。

## 三、过滤位置

1. **顶层 `grape --help`**：`ContractGroup.format_commands` 按 allowed 过滤条目；整类被禁则该分类行不显示
2. **组内 `grape <group> --help`**：`_ContractGroup` 复写 `format_commands`，隐藏被禁动词
3. **`grape commands [pattern]`**：`_tree_lines` 只列允许命令
4. **组摘要首行（动词含义列表）**：保持显示（信息性），被禁动词不单独列出

## 四、运行守卫（防"绕过帮助硬执行"）

根部分发时（`get_command` 命中叶子前），若命令 scope 被当前模式禁用 → 直接报 **模式不匹配**错误返回非 0：

```
`skills upload` is not available in GRAPE_CLI_MODE=WORKER
(scope: user_only — requires GRAPE_API_TOKEN; set GRAPE_CLI_MODE=USER or ALL, or switch token)
```

- 替代坐等服务端 403，省一次重试
- 退出码：1（模式/参数类配置错误）

## 五、改动面

| 文件 | 改动 |
|------|------|
| `src/registry.py` | `cli_mode()`（env 解析）；`_token_scope()` 改读 `op["x-token-scope"]`（缺省回落静态表）；`allowed_by_mode(mode, scope)`；`format_commands`/`_tree_lines`/组内 `format_commands` 过滤；`get_command` 守卫 |
| `src/cli.py` | 顶层 `format_commands`/`_tree_lines` 接入 mode |
| `src/data/openapi.json` | 回填各 op `x-token-scope`（从生产契约按路径+方法）；内置命令 scope 在代码内判定（`git`=session_only、`commands`/`refresh`=dual） |
| `test/` | 三模式 × 三 scope 可见性 + 守卫报错 + 默认 ALL（未设 env）+ 契约字段优先/静态兜底 |

## 六、已验证决策点（2026-09-15 评审确认）

| # | 项 | 结论 |
|---|----|------|
| 1 | env 未设默认 | **ALL**（向后兼容） |
| 2 | 内置 `git` 处理 | 视作 `session_only`：WORKER/ALL 显示，USER 隐藏 |
| 3 | 组摘要首行 | 保持显示（信息性） |
| 4 | 被禁命令运行 | 直接报"模式不匹配"错误，非坐等 403 |

## 七、预期效果

- WORKER（agent 主场景）：help/commands 只暴露 session 可用的命令，`user_only`（skills/auth/chat/repos-managed…171 条）不再出现 → 不再因"用 tk_ 打 user_only"而 403 重试
- USER：只暴露 grape_/JWT 可用命令，`session_only`（git-repo 等 25 条）隐藏 → 不再用 user key 打 session_only 403
- 切换模式只需 `export GRAPE_CLI_MODE=...`；旧脚本（未设 env）行为不变（ALL）