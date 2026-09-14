# 基于 Token 作用域分类的 CLI help 优化方案

> 依据：grape 服务端 `docs/weekly-03/token-scope-classification-design.md`（已实施上线）
> 状态：✅ 已实施（#1/#2/#3/#4；#5 待建 whoami，#6 待服务端 x-token-scope）
> 目的：让 agent 在调用前从 `grape --help` 看到命令的 **token 作用域**（session 可用 / 需 user key / 仅会话），
> 避免"用注入的 session token 打 D 类管理接口 → 403 → 不知所措"。

---

## 一、服务端已生效的 Token 作用域事实

| 类 | 命令分组 | session_token(tk_) | API Key(grape_)/JWT |
|----|---------|:---:|:---:|
| A Core workflows | tasks · a2a | **允许** | 放行（现状） |
| B Agent Context | issues · events · knowledge | **允许** | 放行（现状） |
| C Code & repositories | git-repo/* · repos git_credential/workspace | **允许（现状仅 session）** | API Key/JWT 现状 403（不扩大） |
| D Account & platform | agents · auth·profile · chat · repos member/managed/deploy · skills | **❌ 403（本次收紧）** | 放行（现状） |

> `scenes` **不归 D**（VOD 技能用 session 调 `GET /api/scenes`，维持 200）。

**关键**：token 作用域是**动词级**而非组级——
- `repos` 组：`member/managed/deploy` 是 D（session→403），`git-credential/workspace` 是 C（session-only）；
- `Account & platform` 组里的 `scenes` 并非 D；
- `auth/profile`（D）→ 若做 `grape whoami`（调 profile）用 session 会 403，须 user key/JWT。

**数据源现状**：服务端 §3.3 的 `x-token-scope` 契约扩展为**遗留未落地** → CLI 先用静态映射表，待服务端标注后再契约驱动。

---

## 二、优化方案

> **展示层级**（作用域标注出现在哪层帮助）：
> | 标注 | 出现位置 | 说明 |
> |------|---------|------|
> | #3 分类引导行 | **`grape -h`（顶层）** | CATEGORY_INTRO 直接展示，如 `Account & platform (...session tk_ rejected on some...)`、`Code & repositories (...session-only)` |
> | #2 命令短帮助标注 | `grape <group> --help` 列表 + `grape <group> <verb> --help` | 顶层 `-h` 不逐命令显示（只显示组级摘要=动词含义行） |
> | #4 403 二次提示 | 运行时 stderr | 命中 D 类 403 时追加英文引导 |
>
> 若想让顶层 `-h` 更易见：均匀作用域的组可在组级摘要行尾附标注（如 `git-repo ... (session-only)`、`skills` 全 D → 摘要行附 `(session 403 → grape_/JWT)`）；混合组（`repos`）只能落在组帮助的逐动词标注上。

### 1.（P0）Token 作用域映射表 `src/data/token-scope.json`

operationId → scope 枚举：

| scope | 含义 | 命令示例 |
|-------|------|---------|
| `user_only` | **D 类**：session(tk_) 403，需 `grape_` API Key / JWT | agents_detail, auth_profile_get, chat_conversations/messages, repos_member/managed/deploy_url, skills_list/detail |
| `session_only` | **C 类**：仅 session 可用（API Key/JWT 现状 403） | gitrepo_*（全部）, repos_git_credential, repos_workspace |
| （默认） | A/B 类及 scenes：session/API Key/JWT 均放行 | tasks_*, a2a_handoff, issues_*, events_detail, knowledge_*, scenes_list |

> 表内容按设计文档 §2.2 四类生成；缺失 operationId 一律默认放行（A/B），避免误标。

### 2.（P0）命令短帮助标注（`build_command`）

- `user_only` → 追加 `(session 403 → use GRAPE_API_TOKEN / JWT)`
- `session_only` → 追加 `(session-only)`
- 默认 → 不加（session 可用）

示例：

```
Account & platform:
  skills  detail: Get skill detail (incl. SKILL.md) (session 403 → use grape_ key / JWT)
  repos   managed: Managed repository list (session 403 → use grape_ key / JWT)
           workspace: Repository workspace path (session-only)
```

### 3.（P1）分类引导行提示（`format_commands` / `CATEGORY_INTRO`）

- `Account & platform` → `user-level platform resources (session tk_ rejected on some → use GRAPE_API_TOKEN/JWT)`
- `Code & repositories` → `run git locally / platform repo API (session-only)`
- `Core workflows` / `Agent Context` → `(session ok)`

### 4.（P1）403 错误二次提示（`client.py`）

命中 `user_only` 表（D 类）且状态码 403 时，错误追加：
```
use GRAPE_API_TOKEN / Web JWT — session token (tk_) is rejected for this scope
```
（服务端已给中文"该接口不支持会话 token"，CLI 补英文引导；git-repo 403 既有 hint 保留。）

### 5.（P2）内置命令说明

- 若后续添加 `grape whoami`（调 `auth_profile_get`，属 D）→ 明确"需 `grape_` API Key / Web JWT；session token 403"。

### 6.（待服务端）数据源演进

服务端落地 `x-token-scope` 契约扩展后，CLI 改为从契约读取 scope（替换静态表，避免漂移）。

---

## 实施记录（2026-09-14）

- **#1** `src/data/token-scope.json`：user_only(D 9 个 operationId)/session_only(repos credential+workspace)；
  `gitrepo_*` 前缀按前缀判 session_only；`registry._token_scope()`
- **#2** `build_command`：命令短帮助追加 `(session 403 → grape_/JWT)` / `(session-only)`；帮助体加 `Token scope: ...` 行
- **#3** `cli.py CATEGORY_INTRO`：Account & platform / Code & repositories / Core workflows / Agent Context 引导行带作用域
- **#4** `registry._run`：D 类 403 追加 `use GRAPE_API_TOKEN / Web JWT — session token (tk_) is rejected for this scope`
- 测试 +3，**103 passed**；`grape --help` 顶层即可见分类作用域提示

## 三、测试

- `test_registry`：`user_only` 命令短帮助含 `use GRAPE_API_TOKEN`；`session_only` 含 `session-only`；默认无
- `test_client`：D 类 403 → 错误含 `session token ... rejected`
- `test_cli`：`--help` 分类引导行含 scope 提示

## 四、收益与不破坏

- **收益**：agent 调用前即知作用域，减少"session 打 D 类 / API Key 打 C 类"的 403 探索往返；C 类"仅会话"也顺带澄清。
- **不破坏**：仅帮助文本 + 错误提示，不影响命令解析、退出码、既有 403 逻辑。