# grape CLI 命令分组（5 类）

> 顶层 `grape --help` 按「意图 × 读写角色」分 5 类，每类带 token 作用域提示。
> 所有示例均为**可调用命令**（占位：`o/r`=owner/repo、`N`=编号、`<...>`=替换）。更全的逐命令帮助见 `grape <group> <verb> --help`。

## 1. Core workflows（核心工作流）· session ok

agent **会去变更**的流程。

```bash
grape tasks mine --status active --json-out            # 我的任务
grape tasks status --task_id 7 --json '{"status":"processing"}'
grape tasks complete --task_id 7 --json '{"result_text":"已修复...","next_step":"a2a_issue"}'
grape tasks start --task_id 7                          # 打开会话
grape tasks repo --owner o --repo r --json-out         # 仓库全部任务
grape tasks clarify --task_id 7 --json '{"message":"需要补充验收标准"}'
grape tasks clarifications --task_id 7 --json-out      # 澄清历史
grape a2a handoff --json '{"agent":"coding","payload":{"repository":"o/r","account":"<user>","issue_number":7,"pr_number":0,"context":"<ctx>"}}'
```

| 命令 | 用途 |
|------|------|
| `tasks mine/status/complete/start/repo` | 我的任务 / 更新状态 / 完成 / 启动 / 仓库任务 |
| `tasks notify` | 分配并通知（内部） |
| `tasks clarifications/clarify` | 澄清历史 / 回复澄清 |
| `a2a handoff` | 交接给指定 agent（coding/qa/sre/issue…） |

## 2. Agent Context（Agent 上下文）· session ok

执行 agent 的**只读上下文**（改状态属 user 层）。

```bash
grape issues list --owner o --repo r --json-out                     # 含阶段/状态聚合
grape issues detail --owner o --repo r --number 7 --json-out        # +events+pipeline
grape issues events --owner o --repo r --number 7 --json-out        # 事件流
grape issues pipeline --owner o --repo r --number 7 --json-out      # 路线图
grape issues create --owner o --repo r --json '{"title":"bug: x","description":"..."}'   # 仅入口/用户侧创建
grape events detail --event_id <seq> --json-out
grape knowledge list --json-out
grape knowledge content --knowledge_id <id> --json-out
grape knowledge context --json-out                                 # 注入上下文文本
```
> 结构化结论/澄清 → 写进**评论**，不改 Issue 状态：
> `grape git-repo issues comments create --owner o --repo r --number 7 --json '{"body":"<内容>"}'`

| 命令 | 用途 |
|------|------|
| `issues list/detail/events/pipeline/create` | Issue 聚合视图（阶段/事件/路线图）；create 为入口 |
| `events detail` | 事件/日志详情 |
| `knowledge list/content/context/stats/detail` | 知识检索 |

## 3. Code & repositories（代码仓库）· session-only

```bash
grape git status                      # 本地透传（自动识别仓库→注入凭据）
grape git log --oneline -10
grape git-repo contents --owner o --repo r --json-out            # 根/目录列表
grape git-repo contents --owner o --repo r --path README.md --raw  # 文件原文（base64 自动解码）
grape git-repo tree --owner o --repo r --ref main --json-out     # 目录树
grape git-repo branches --owner o --repo r --json-out
grape git-repo commits --owner o --repo r --json-out
grape git-repo issues list --owner o --repo r --state open --json-out
grape git-repo issues get --owner o --repo r --number 7 --json-out
grape git-repo issues comments list --owner o --repo r --number 7 --json-out
grape git-repo pulls list --owner o --repo r --json-out
grape git-repo pulls files --owner o --repo r --number 7 --json-out
grape git-repo pulls merge --owner o --repo r --number 7
grape git-repo labels list --owner o --repo r --json-out
```

| 命令 | 用途 |
|------|------|
| `git ...` | 本地 git 透传（克隆/推送/日志，凭据进程内注入） |
| `git-repo tree/contents/branches/commits/labels/milestones` | 平台仓库只读资源 |
| `git-repo issues/pulls ...` | Issue/PR（列表/详情/评论/合并等） |
| `repos git-credential/workspace` | CLI 内部凭据/工作区（一般不用） |

## 4. Account & platform（账号与平台）· session 部分 403，需 `grape_`/JWT

```bash
export GRAPE_API_TOKEN=grape_xxx     # D 类端点需用户级 Key 或 Web JWT
grape skills list --json-out
grape skills detail --skill_id <id> --json-out
grape scenes list --json-out                       # VOD 技能可用会话访问
grape agents detail --json-out
grape auth profile --json-out                      # 当前身份
grape chat conversations --json-out
grape repos managed --json-out
grape repos member --json-out
```

| 命令 | 用途 |
|------|------|
| `skills list/detail` | 技能库（技能已随任务下发，通常无需查） |
| `scenes list` | 场景模板（VOD 技能可会话访问） |
| `agents detail` / `auth profile` / `chat conversations\|messages` / `repos member\|managed\|deploy-url` | 身份/会话/托管仓库查看 |

## 5. CLI utilities（工具）

```bash
grape commands                    # 列出可调用命令
grape commands issues             # 按关键词过滤
grape refresh                     # 重拉最新契约（或回退内置快照）
grape --help                      # 分类总览 + token 作用域提示
```

| 命令 | 用途 |
|------|------|
| `commands [pattern]` | 列出可调用命令（过滤） |
| `refresh` | 重拉最新契约 |

> 每次接口变化后：`grape refresh`（或清 `~/.grape/openapi-*.json`）。