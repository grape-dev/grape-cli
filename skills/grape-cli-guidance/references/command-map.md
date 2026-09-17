# grape CLI 命令分组（5 类）

> 顶层 `grape --help` 按「意图 × 读写角色」分 5 类；本表逐命令列出**当前线上契约（v2.1.0）实际可调用**命令。
> 权威清单以 `grape commands` 输出为准（只列可调用命令）；任何命令缺失/报错先 `grape refresh` 再 `grape commands`。

## 0. 命令全集速览（58 条 + 2 内置）

按组：`a2a`(handoff) · `agents`(detail) · `chat`(conversations, messages) · `events`(detail) ·
`git-repo`(repo, contents, tree, branches, commits, labels list/create, milestones,
issues list/get/create/update, issues comments list/create,
pulls list/get/create/update/merge, pulls comments list/create, pulls files) ·
`issues`(list, detail, events, pipeline, mine, create, start, resume, cancel, status,
confirm done, clarifications, clarify, upload attachment, delete attachment) ·
`knowledge`(list, content, context, stats, add refs batch) ·
`repos`(member, managed, deploy url, git credential, workspace) · `scenes`(list) ·
`skills`(list, detail, agent stats) · `tasks`(complete, current, wait) ·
内置：`git`（本地透传）、`commands`、`refresh`。

> 说明：
> - 服务端将大量新接口命名为 `*_api_*` 形式（autogen），CLI **有意过滤**，不走命令。
> - 契约仍声明但当前**被命令树吞掉**（前缀同为叶子命令）的：`issues list attachments`、`issues status get`、`issues pipeline detail`——不要依赖，以 `grape commands` 为准。

## 1. Core workflows（核心工作流）· 会话优先

```bash
grape tasks current --json-out                     # 内省当前任务（agent 执行期自省，session-only）
grape tasks complete --json '{"task_id":<id>,"result_text":"...","next_step":"a2a_issue"}'
grape tasks wait --task-id 7 --timeout 120          # 轮询任务到终态（内置命令）
grape a2a handoff --json '{"agent":"coding","payload":{"repository":"o/r","account":"<user>","issue_number":7,"context":"<ctx>"}}'
```

| 命令 | 用途 | Scope |
|------|------|-------|
| `tasks current` | 当前任务详情（执行期自省） | `session_only` |
| `tasks complete` | 标记任务完成 | `dual` |
| `tasks wait [--task-id --timeout]` | 轮询直到终态（内置） | `dual` |
| `a2a handoff` | 交接给其他 agent（coding/qa/sre/issue…） | `dual` |

> 任务**列表/状态/启动**已从契约短名接口迁出（新接口为 `api_` 形式被 CLI 过滤）——
> agent 执行期需要「认领/推进」请从 `issues ...`（平台 Issue 视图）获取上下文；不要硬猜 `grape tasks ...` 拼新名。

## 2. Agent Context（Agent 上下文）· 只读 session ok，改动作需 `grape_`/JWT

```bash
grape issues list --owner o --repo r --json-out                    # 仓库 Issue 列表（含阶段/状态聚合）
grape issues detail --owner o --repo r --number 7 --json-out       # 详情（阶段+事件+pipeline）
grape issues events --owner o --repo r --number 7 --json-out       # 事件流
grape issues pipeline --owner o --repo r --number 7 --json-out     # 路线图
grape issues mine --json-out                                       # 我的 Issue
grape events detail --event_id <seq> --json-out
grape knowledge list --json-out
grape knowledge content --repo o/r --file docs/x.md --json-out      # 单条知识全文
grape knowledge context --json-out                                 # 注入上下文文本
```

| 命令 | 用途 | Scope |
|------|------|-------|
| `issues list/detail/events/pipeline/mine` | Issue 只读视图（阶段/事件/路线图） | `dual` |
| `events detail` | 事件/日志详情 | `dual` |
| `knowledge list/content/context/stats` | 知识检索（读） | `dual` |
| `issues create/start/resume/cancel/status/clarify/confirm done/upload attachment/delete attachment` | **改动作**（变更属 user 层） | `user_only`（session→403） |
| `issues clarifications` | 澄清历史 | `user_only` |
| `knowledge add refs batch` | 写知识 | `user_only` |

> 结构化结论/澄清 → 写进 git 仓库的 **Issue 评论**（走 Code 类），不改平台 Issue 状态：
> `grape git-repo issues comments create --owner o --repo r --number 7 --json '{"body":"<内容>"}'`

## 3. Code & repositories（代码仓库）· session-only

```bash
grape git status                                        # 本地 git 透传（凭据进程内注入）
grape git log --oneline -10
grape git-repo repo --owner o --repo r --json-out       # 仓库信息（clone_url/default_branch）
grape git-repo contents --owner o --repo r --json-out                # 根/目录列表（空 path）
grape git-repo contents --owner o --repo r --path README.md --raw    # 文件原文（base64 自动解码）
grape git-repo tree --owner o --repo r --ref main --json-out         # 目录树
grape git-repo branches --owner o --repo r --json-out
grape git-repo commits --owner o --repo r --json-out
grape git-repo issues list --owner o --repo r --state open --json-out
grape git-repo issues comments create --owner o --repo r --number 7 --json '{"body":"..."}'
grape git-repo pulls list --owner o --repo r --json-out
grape git-repo pulls merge --owner o --repo r --number 7 --json '{"sha":"<head_sha>"}'
```

| 命令 | Scope |
|------|-------|
| `git ...` | `session_only`（本地透传） |
| `git-repo repo/tree/contents/branches/commits/labels/milestones` | `session_only` |
| `git-repo issues list/get/create/update · comments list/create` | `session_only` |
| `git-repo pulls list/get/create/update/merge · comments list/create · files` | `session_only` |
| `repos git credential` / `repos workspace` | `session_only`（CLI 内部用） |

## 4. Account & platform（账号与平台）· 需 `grape_`/JWT

```bash
export GRAPE_API_TOKEN=grape_xxx    # user_only 端点需用户级 Key 或 Web JWT
grape agents detail --name <n> --owner o --repo r --json-out
grape chat conversations --json-out
grape chat messages --conv_id <id> --json-out
grape repos managed --json-out        # 托管仓库
grape repos member --json-out         # 我可操作的仓库
grape repos deploy url --owner o --repo_name r --json-out
grape skills list --json-out
grape skills detail --skill_id <id> --json-out
grape skills agent stats --json-out
grape scenes list --json-out          # 场景（约定 dual，VOD 可用会话访问）
```

| 命令 | Scope |
|------|-------|
| `agents detail` / `chat conversations|messages` | `user_only` |
| `repos member/managed/deploy url` | `user_only` |
| `skills list/detail/agent stats` | `user_only` |
| `scenes list` | `dual` |

## 5. CLI utilities（工具）

```bash
grape commands                    # 列出可调用命令（权威）
grape commands issues             # 按关键词过滤
grape refresh                     # 重拉最新契约
grape --help                      # 分类总览 + token 作用域提示
```

> 每次接口变化后：`grape refresh`（会覆盖 `~/.grape/openapi-*.json`）。