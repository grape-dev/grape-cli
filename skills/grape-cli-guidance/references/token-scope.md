# grape CLI Token 作用域

> 服务端规则：会话 token（`tk_`）不得用于「账户/平台管理」端点（403）；`grape_` API Key 与 Web JWT 放行。
> 依据：grape `docs/weekly-03/token-scope-classification-design.md`（已上线）。

## 三类凭据

| 凭据 | 环境变量 | 语义 | 何时用 |
|------|---------|------|--------|
| session_token（`tk_`） | `GRAPE_SESSION_TOKEN` | agent/worker 任务级临时凭据（自动注入） | **默认就用它**：Workflows / Agent Context / git-repo 等 |
| user API Key（`grape_`） | `GRAPE_API_TOKEN`（或 `--grape-api-token`） | 用户长期 Key（Web UI「API Tokens」生成） | 账户/平台管理（skills/auth/chat/repos-managed…）、独立/三方集成 |
| JWT（Web 登录） | 浏览器登录态 | Web 页面身份 | 自动化场景一般不用 |

## 分类 × 作用域

| 类 | session(tk_) | grape_/JWT |
|----|:---:|:---:|
| Core workflows（tasks/a2a） | ✅ | ✅ |
| Agent Context（issues/events/knowledge） | ✅ | ✅ |
| Code & repositories（git/git-repo） | ✅ 仅会话 | ❌ |
| Account & platform（skills/agents/auth/chat/repos member+managed+deploy） | ❌ **403** | ✅ |
| `scenes` | ✅（VOD 技能用 session 调） | ✅ |

## 用哪个凭据（决策）

1. 任务环境默认注入 `tk_` → 先用它；覆盖 A/B/C 类全部日常操作。
2. 看到 `HTTP 403: ... 该接口不支持会话 token / use GRAPE_API_TOKEN`（D 类）：
   → 设置/切换 `GRAPE_API_TOKEN`（`grape_`）再执行。
3. 看到 `HTTP 403: ... session token (tk_) only`（C 类 git-repo）：
   → 用 `GRAPE_SESSION_TOKEN`（`tk_`），不要用 API Key。

## CLI 上的可见提示

- `grape --help` 分类引导行：如 `Account & platform (...session tk_ rejected on some → use GRAPE_API_TOKEN/JWT)`、`Code & repositories (...session-only)`。
- `grape <group> <verb> --help`：`Token scope: ...` 行。
- 运行时 403：CLI 会追加英文行动指引（换 `grape_`/JWT）。