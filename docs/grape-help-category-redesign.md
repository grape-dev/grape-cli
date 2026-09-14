# grape --help 命令分类重组方案

> 状态：✅ 已实施（2026-09-14）
> 背景：`grape -h` 当前按"单体功能"分组，`tasks` 独占一类、`issues`/`auth` 等新组落在"Explore"
> 兜底，类别语义对 agent 不够清晰。
> 目标：基于最新 openapi 命令面，按 **agent 使用意图**分组，一屏可扫读、一选即中。

---

## 一、现状与问题

```
Work with tasks:          tasks
Work with repositories:   git, git-repo
Skills & knowledge:       knowledge, skills
Explore the platform:     a2a, agents, api, auth, chat, commands, events,
                          issues, refresh, repos, scenes
```

- `tasks` 单列一类，浪费一行，且与 `issues`（同为核心流转）割裂
- 新增的 `auth`(profile)、`issues`、`a2a` 统统落进 "Explore" 兜底，语义被稀释
- 内置元命令（`api`/`commands`/`refresh`）与平台资源命令混排

## 二、分组原则

1. **按意图 × 读写角色**（做什么 / 读还是改），不按单体
2. **核心流转优先**：agent 驱动的流程（task 状态/交接）与只读上下文（Issue/事件）分开
3. 内置元命令（api/commands/refresh）独立成"工具"类，不与资源类混淆
4. 未知新组默认进 "Account & platform"（契约动态新增不破坏结构）

## 三、目标分组（6 类）

| 类别 | 命令 | 一句话语义 |
|------|------|-----------|
| **Core workflows**（核心工作流） | `tasks` · `a2a` | agent 驱动的流程：任务状态/通知/交接 |
| **Agent Context**（Agent 上下文） | `issues` · `events` · `knowledge` | 只读上下文：Issue 阶段/事件/知识（改状态属 user 层） |
| **Code & repositories**（代码仓库） | `git` · `git-repo` | 本地 git 透传 / 平台仓库 API |
| **Account & platform**（账号与平台） | `agents` · `auth` · `chat` · `repos` · `scenes` · `skills` | 身份/会话/Agent 配置/托管仓库/场景/技能（用户级、管理导向） |
| **CLI utilities**（工具） | `commands` · `refresh` | 列出/刷新契约命令 |

> **读写角色划分**（为何 issues/events/knowledge 单列）：
> - **Core workflows** = agent **会去变更**的流程（task 状态/完成后通知/交接给下一 agent）；
> - **Agent Context** = 执行 task 的 agent **只读查询**的本钱（Issue 当前阶段/事件流/pipeline、知识库检索），
>   不改状态——改 Issue 状态/阶段属 user 层（webhook/UI），agent 不应去改 → 与"干活"类分开。
>   `issues create` 是入口/用户侧创建，非 task 内 agent 变更；
> - **skills 不放 Agent Context**：agent 所需的 skill **已由任务发放**（随任务注入技能目录），agent 无需去查；
>   `skills` 与 `scenes` 一样属**管理导向**（用户配置技能库/场景模板），归 **Account & platform**。

### 归属明细

| 命令 | 现类 | 新类 | 理由 |
|------|------|------|------|
| tasks | Work with tasks | Core workflows | agent 驱动的状态/通知/完成流程 |
| a2a | Explore | Core workflows | handoff = agent 交接，工作流一环 |
| issues | Explore | Agent Context | 只读查询 Issue 阶段/事件（改状态属 user 层） |
| events | Explore | Agent Context | 事件日志只读上下文 |
| knowledge | Skills & knowledge | Agent Context | 知识检索（content/context/list/stats/detail 均只读） |
| skills | Skills & knowledge | Account & platform | 管理导向：skill 已随任务下发，agent 无需查询（同 scenes） |
| git | repos | Code & repositories | 本地 git |
| git-repo | repos | Code & repositories | 平台仓库 API |
| agents/auth/chat/repos/scenes/skills | Explore | Account & platform | 用户级平台资源（身份/会话/事件/托管/场景/技能），未来面向用户 API key |
| commands/refresh | Explore | CLI utilities | 元命令，非平台资源 |
| （未来新契约组） | — | Account & platform（默认） | 动态兜底 |

## 四、目标展示预览

```text
Commands:
  Core workflows (agent-driven task actions & handoffs):
    tasks   mine/notify/status/complete/clarify/repo/...
    a2a     handoff

  Agent Context (read-only context — issue/events/knowledge; state changes are user-level):
    issues    detail/events/list/pipeline · create(入口)
    events    detail
    knowledge content/context/list/stats/detail

  Code & repositories (run git locally / platform repo API):
    git        Run git locally ...
    git-repo   Platform API by grape ...

  Account & platform (user-level platform resources; management-oriented incl. skills/scenes):
    agents / auth / chat / repos / scenes / skills

  CLI utilities:
    commands / refresh
```

## 五、实现要点（实施时）

| 项 | 文件 | 动作 |
|----|------|------|
| 1 | `src/cli.py` `ContractGroup.CATEGORY_MAP` | 映射：tasks/a2a→Core workflows；issues/events/knowledge→Agent Context；git/git-repo→Code & repositories；agents/auth/chat/repos/scenes/skills→Account & platform；commands/refresh→CLI utilities |
| 2 | `src/cli.py` `CATEGORY_ORDER` | 上述 5 类顺序 |
| 3 | `format_commands` | 类别行后追加一句引导（如 `Core workflows (agent-driven task actions & handoffs)`） |
| 4 | `test/test_cli.py` | `test_help_categories` 断言新类标题存在 |
| 5 | 文档 | README（中英）Commands 分类同步 |

## 六、可选增强

- 每类一行"何时用"引导（已在预览体现），数据放 `CATEGORY_INTRO: dict`
- 契约新增组保持默认进 Account & platform，避免每次接口变化改静态表

## 实施记录（2026-09-14）

- `src/cli.py`：`CATEGORY_MAP` 按 5 类定稿（tasks/a2a→Core workflows；issues/events/knowledge→Agent Context；
  git/git-repo→Code & repositories；agents/auth/chat/repos/scenes/skills→Account & platform；
  commands/refresh→CLI utilities）；`DEFAULT_CATEGORY=Account & platform`；
  `format_commands` 类别行带一句话引导（`CATEGORY_INTRO`）。
- `test/test_cli.py`：分类断言更新 + bundled 下 Agent Context 断言；**101 passed**。
- 实测 `grape --help` 5 类渲染符合预览。

## 追加决策（2026-09-14）：移除 `api` 命令

- **理由**：`grape api <METHOD> <path>` 是无契约白名单的原始 HTTP 透传——可打任意 path（含内部端点）、
  绕过契约命令的必填参数/未知字段守卫/did-you-mean 等确定性保护，属"逃生舱"，agent 用法不可审计。
- **决策（方案 A）**：删除 `api` 命令（`src/commands/api.py` 移除、CATEGORY_MAP/README 同步）；
  契约过期场景由 `grape refresh`（或内置快照）覆盖，开发调试可用 `curl`。

## 结论

按"意图 × 读写角色"重排 5 类：`tasks`/`a2a` 归 Core workflows（agent 驱动变更），
`issues`/`events`/`knowledge`/`skills` 并入 **Agent Context**（执行 agent 只读上下文，改状态属 user 层），
代码/账号平台/工具各自成类。agent 扫一眼 `grape -h` 即可确定"到哪类查/到哪类改"。