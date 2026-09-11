# 方案：CLI 契约拉取优先走服务端 `static/openapi.json`

> 状态：✅ 已实施（2026-09-11）
> 关联：P0（nginx 封禁 `/openapi.json`）、方案 C（内置快照兜底）、help-page-prototype §3.1
> 目标：让生产上 CLI 恒能从**未封禁、no-cache** 的固定 URL 拿到权威契约，快照降级为纯兜底。

---

## 一、背景与现状

- grape 服务端已在启动期把对外契约落盘到 `static/openapi.json`（对外安全路由，固定 URL），
  实测 `https://grape.example.com/static/openapi.json` → **200**；`/static/` 前缀不在 nginx
  封禁范围（P0 只封 `/openapi.json`,`/docs`,`/redoc`），因此该 URL 天然绕过 P0。
- 当前 CLI 拉取顺序：本地缓存 `~/.grape` → `fetch_schema()` 打 `{base}/openapi.json` → 内置快照。
  线上 `{base}/openapi.json` 仍是 403，导致远端拉取必失败 → 一直落回快照，取不到权威最新。

## 二、方案（A：优先 static URL）

**拉取顺序改为**：本地缓存 `~/.grape` > **`{base}/static/openapi.json`** > `{base}/openapi.json` > 内置快照。

```
fetch_schema()：
  1) GET {base}/static/openapi.json    ← 首选（公开、no-cache、绕过 nginx 封禁）
  2) 失败 → GET {base}/openapi.json    ← 兼容无 static 的部署
  3) 都失败 → 抛 CliError            → load_contract 捕获后落回内置快照
```

改动点（`src/contracts.py`，约 5 行）：
- `fetch_schema` 内先试 `static/openapi.json`，401/网络错/404 时再试 `/openapi.json`；
- 两个 URL 均走现有 `ApiClient`（自动带 Bearer/PRIVATE-TOKEN/access_token）；
- 契约写入缓存与 `contract_source()` 逻辑不变（按 `info.version`）。

## 三、行为矩阵

| 场景 | 结果 |
|------|------|
| 服务端提供 `static/openapi.json`（生产现状） | 直接拉权威最新；快照不再介入 |
| 服务端无 static（老版本/内网） | 回退 `/openapi.json`（原行为） |
| 两者都不可达（403/断网/离线） | 落回内置快照（方案 C 兜底，含丰富任务端点） |
| `grape refresh` | 同优先级强拉，命中 static 即更新缓存 |

## 四、权衡 / 注意事项

1. **命令面差异**：权威 `static/openapi.json` 只含**对外安全路由**（不含内部任务端点
   notify/close/clarify/clarifications）；内置快照反而更全。线上可达时 `grape tasks notify`
   将**不再出现**（符合服务端契约真实面）；离线/兜底时出现。需在 README 提示。
2. **缓存键**：static 与 /openapi.json 版本一致（同 `custom_openapi` 产物），缓存互不冲突。
3. **安全**：static 走 `/static/` 有 `NoCacheStaticMiddleware`；无需额外鉴权放行，无需改 nginx。

## 五、测试

- `test_contracts`：新增 router 提供 `/static/openapi.json` → `fetch_schema` 走 static（断言 URL）；
- 只有 `/openapi.json` → 走旧路径；
- 两者都 404/网络错 → 落回 bundled（现有用例保持）。
- `test_cli` 现有 fake router 无影响（router 未配 static 时走 /openapi.json，行为不变）。

## 六、文档同步

- README（中英）Contract 提示：优先 `{base}/static/openapi.json`，兜底内置快照。✅
- `docs/issue-1-production-issues.md` P0 过渡措施章节：补充"static URL 已使远端拉取恢复，快照降级兜底"。

---

## 实施记录（2026-09-11）

- `src/contracts.py`：`fetch_schema` 按 `_CONTRACT_PATHS=("/static/openapi.json","/openapi.json")` 顺序尝试；
  均失败抛 `contract unreachable ...`（由 `load_contract` 捕获落回快照）。
- 测试 +4：static 优先 / 回退根路径 / 全失败抛错 / static 畸形回落根路径 —— **79 passed**。
- README 中英同步契约拉取优先级说明。

> ⚠️ 线上可达时命令面=服务端对外安全路由（不含内部任务端点）；离线/兜底时快照更全（含 notify/close/clarify）。