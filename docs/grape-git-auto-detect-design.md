# 设计方案：`grape git` 裸用自动识别仓库 + 免凭据注入（方案 B）

> 状态：待实施（仅方案，未改代码）
> 关联：Issue-45 方案③ / `grape git` 透传
> 设计意图：全新 worker 只靠环境注入的 `GRAPE_SESSION_TOKEN`，即可让
> `grape git xx` 生效——不配置 git config、SSH key、本地 GitCode token 也不用。

---

## 一、设计意图（对齐）

- `grape git xx` 只依赖 `GRAPE_SESSION_TOKEN`（worker/chat 环境已注入）
- 本地不需要任何 GitCode token / SSH key / git config
- 需要远端认证的操作（clone / push / pull / fetch / ls-remote）走 **token（HTTP Basic）**，禁 SSH
- `git commit` 等本地操作本不需要认证，但需保证 `user.name/email` 可用（身份注入，见 §五）

## 二、现状与差距

| 现状 | 差距 |
|------|------|
| 必须显式 `grape git --repo o/r ...` 才换券注入 | 裸用（无 `--repo`）时**零注入**，私有仓库一切远端操作失败 |
| `--repo` 是 `git` 子命令私有选项 | 与 `--token`（全局）规则不一致；若挪全局又破坏现有写法 |
| 换券时把 cwd 切到服务端 workspace | 裸用时原则是"仓库就在当前目录"，不应切目录 |

## 三、总体思路

**去掉 `--repo`，改为两路自动识别仓库，识别到且 host 白命中才换券注入。**

```
grape git <args>
  │
  ├─ 识别 owner/repo
  │    ├─ clone：解析第一个参数 URL 中的 owner/repo（此时 cwd 尚无 .git）
  │    └─ 其他：git config --get remote.origin.url（子目录亦可）
  │
  ├─ host 白名单（仅 gitcode.com）→ 才继续；否则零注入透传
  │
  ├─ 调 /workspace（不再使用其 cwd）+ /git-credential → http.extraheader 注入
  │    └─ 失败降级：无 token / 服务端不可达 → stderr 警告，不阻塞本地命令
  │
  ├─（可选）缺 user.name/email → 从会话用户派生注入（GIT_CONFIG env）
  └─ 透传 git <args>，全程不动 cwd
```

## 四、仓库识别

### 4.1 clone：从 URL 解析

支持形态（解析出 owner/repo 用于换券；远端连接仍按用户给的原 URL）：

```
https://gitcode.com/o/r.git
https://gitcode.com/o/r
git@gitcode.com:o/r.git          （scp-like）
ssh://git@gitcode.com/o/r.git
```

### 4.2 非 clone：从当前仓库 origin 解析

```
git config --get remote.origin.url
# → https://gitcode.com/o/r.git  /  git@gitcode.com:o/r.git ...
```

### 4.3 host 白名单

只对 `host ∈ {gitcode.com}`（含 `www.gitcode.com` 等子域名判断）换券；
github / gitlab / 其他 host **一律不注入**，防止 `http.extraheader` 把平台 token 发给第三方。

### 4.4 识别失败

零注入，直接透传 git（行为等同 `git xx`，错误由 git 原生呈现）。

## 五、身份注入（commit 可用）

换券成功后，检查目标配置缺失时一并注入（经 `GIT_CONFIG_COUNT/KEY/VALUE` env，进程内不落盘）：

- `user.name` / `user.email` ← 由会话用户 / 服务端 `/git-credential`（或新增字段）派生
- 目的：`git commit` 在全新机器上免配置直接可用

## 六、降级与失败策略

| 场景 | 行为 |
|------|------|
| 本地命令（status/diff/commit），服务端不可达 | 跳过换券，stderr 警告，命令照跑 |
| 远端操作（push/pull/clone），无 token / 换券失败 | 不注入，git 原生报错（提示配置 token 或检查网络） |
| URL 指向非 gitcode host | 不注入，透传 |
| 换券成功但目标目录/权限不符 | 服务端 502/403 兜底，CLI 透传错误信息 |

## 七、安全要点

- `http.extraheader` 会随 git 所有 HTTP 请求发出 → host 白名单钳制是硬要求
- 一万个仓库即一万个 repo_key 维度：服务端按 repo 作用域发 bot token / 用户 token，权限边界在服务端
- 凭据只在子进程 env，不落 `.git/config`、不落 `~/.git-credentials`、不进命令行
- 不修改用户全局 git config（`GIT_CONFIG_COUNT` 只对本进程生效）

## 八、改动清单（实施时）

| 项 | 文件 | 动作 |
|----|------|------|
| 1 | `src/commands/git.py` | 删 `--repo`；新增 `_repo_from_url()` / `_repo_from_cwd()` / `_allow_host()`；注入失败 try/except 降级；可选身份注入 |
| 2 | `src/commands/git.py` docstring | 更新为"裸用自动识别 + 免凭据"语义 |
| 3 | `test/test_git.py` | `--repo` 用例改为：临时仓库配 origin 验证自动注入；clone 由 URL 解析注入 |
| 4 | README.md / README.zh.md | git 章节示例改为 `grape git status` / `push` / `clone https://...`，去掉 `--repo` |
| 5 | `docs/issue-1-production-issues.md` | （如涉及）同步示例 |

## 九、验证

### GRAPE_SESSION_TOKEN 在这里起什么作用？

它**不直接进 git、也不是 clone 的凭据**，只扮演"门票/换券授权"：

```
GRAPE_SESSION_TOKEN ──Bearer──▶ GET /api/repos/Jason7602/hello-html1/git-credential
                                        │（服务端校验会话，按 repo_key 取 bot token / 用户 token）
                                        ▼
发文下发一次性平台 token ◀────────────────
                                        │
CLI 注入 http.extraheader = Authorization: Basic(x-access-token:<平台token>) ──▶ git 用
```

- `GRAPE_SESSION_TOKEN` = 换取 git 用凭据（`password` 字段）的**授权凭证**，客户端不与 git 共享
- git 真正用的是**服务端换出来的平台 token**，304 到期（TTL），不落在本地任何存储
- 所以：本地不存 GitCode token / SSH key，只要环境有 `GRAPE_SESSION_TOKEN` 即可换券 clone

### 完整示例：`grape git clone`

项目地址：`https://gitcode.com/Jason7602/hello-html1.git`

```bash
# 全新 worker，只需环境里已注入 GRAPE_SESSION_TOKEN（无需任何 flag / git config / SSH key）
GRAPE_SESSION_TOKEN=tk_xxx grape git clone https://gitcode.com/Jason7602/hello-html1.git
#                                    └──────────① 透传给 git 的原文 URL──────────┘
#                                       ② CLI 从该 URL 解析 host=gitcode.com、owner/repo=Jason7602/hello-html1
#                                       ③ 换券 → http.extraheader 注入 Basic ┈┈┈┈┈┈┈┈┈┈▶ git 认证成功
# 落地：当前目录下生成 ./hello-html1/，远端 origin = https://gitcode.com/Jason7602/hello-html1.git
```

- 换券走的是 URL 里解析出的 `Jason7602/hello-html1`，`clone` 目标目录由 git 自己建（`./hello-html1/`）
- 该 repo 如果有仓库级 bot token，服务端按 `repo_key=Jason7602/hello-html1` 发 token；`git commit` 身份缺失时另注入 user.name/email

### 完整示例：`grape git push`

```bash
# 已 clone 的 hello-html1 目录里，自动识别 cwd 的 origin → 换券注入 → push
cd hello-html1
GRAPE_SESSION_TOKEN=tk_xxx grape git push
#                                    └───── ① CLI 读 remote.origin.url = https://gitcode.com/Jason7602/hello-html1.git
#                                       ② 解析 owner/repo=Jason7602/hello-html1，host=gitcode.com
#                                       ③ 换券 → http.extraheader 注入 Basic → git push 认证通过
```

### 完整示例：`grape git pull`

```bash
cd hello-html1
GRAPE_SESSION_TOKEN=tk_xxx grape git pull
#                                    └───── 与 push 同流程：读 origin → 换券注入 → git pull
```

> 与 clone 唯一的区别：clone 从 **URL 参数**解析仓库，push/pull 从 **cwd 的 origin** 解析仓库。

### 完整示例：`grape git --help`

```bash
GRAPE_SESSION_TOKEN=tk_xxx grape git --help
#                                     └─ 透传给 git → 输出与 `git --help` 完全一致（usage: git ...）
```

实现：`git` 子命令关掉 click 自动 help（`add_help_option=False`），`--help`/`-h` 都落进透传参数。
（独立方案细节见 `docs/grape-git-help-design.md`；去掉 `--repo` 后，`grape git` 侧面只有透传，无包装帮助可展示。）

### 其他命令对应完整形态

```bash
# 本地命令：服务端挂掉也不打断
GRAPE_BASE_URL=http://127.0.0.1:9 grape git status   # 有警告，仍执行

# 非 gitcode host：不透传凭据
grape git clone https://github.com/x/y.git
```

## 十、取舍备注

- 不做"挪 `--repo` 到全局"（方案 A）：裸用识别后可彻底删掉 `--repo`，接口最简
- clone 是唯一依赖 URL 解析的路径；若以后引入"先建 workspace 再 clone"，仍可复用该解析逻辑
- `grape git --help`/`-h` 与 `git --help` 完全一致——无 `--repo` 后 git 子命令只有透传，help 也一并交给 git（见 `docs/grape-git-help-design.md`）