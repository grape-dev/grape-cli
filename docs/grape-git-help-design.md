# 设计方案：`grape git --help` 与 `git --help` 对齐

> 状态：待实施（仅方案，未改代码）
> 关联：Issue-45 / `grape git` 透传功能

---

## 一、现状（2026-09-09 实测）

```
grape git --help  → click 包装帮助：
                     Usage: grape git [OPTIONS]
                     Run git locally: passthrough any native git command (...)
                     Options:
                       --repo TEXT  owner/repo (resolve workspace & credentials)
                       --help       Show this message and exit.

grape git -h      → 透传给 git，显示真实 git help：
                     usage: git [-v | --version] [-h | --help] [-C <path>] ...
```

**当前行为是矛盾的**：`-h` 已是 git 风格，`--help` 却是 grape 包装风格。

---

## 二、根因

click 在**参数解析阶段**就拦截了 `--help`（每个命令默认自带 help option），
尚未进入 `grape git` 的透传逻辑就渲染了包装帮助；而 `-h` 不是 click 默认的
help 短参，被 `ignore_unknown_options` 收进 `ctx.args` 透传给了 git。

---

## 三、目标

`grape git` 与 `git` 定位等价（仅多进程内凭据注入与 `--repo` 参数），
因此 `grape git --help` 应与 `git --help` 一致，最大程度降低意外。

---

## 四、方案

在 `git_command()` 的命令装饰器上关闭 click 自动 help 拦截（改动约 1 行）：

```python
@click.command(
    name="git",
    help="Run git locally: passthrough any native git command (credentials injected in-process)",
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True),
    add_help_option=False,        # 新增：关闭 click 的 --help 拦截
)
@click.option("--repo", default="", help="owner/repo (resolve workspace & credentials)")
@click.pass_context
def git_cmd(ctx, repo: str):
    ...
```

生效后：
- `grape git --help` → 透传 → `git --help`（usage: git ...）
- `grape git -h` → 透传 → `git -h`（与现状一致）
- `--repo` 仍由 click 先消费，其余参数原样透传 git

---

## 五、边界与代价

| 场景 | 行为 | 是否合理 |
|------|------|----------|
| `grape git --repo o/r --help` | `--repo` 被 click 消费，`--help` 透传 → `git --help` | ✅ |
| `grape git help <topic>` / `git --version` | 本就透传，不受影响 | ✅ |
| `grape git`（无参数） | 与 `git` 空命令一致（status 提示） | ✅ |
| 退出码 | 仍由 git 原样返回 | ✅ |
| 包装帮助可见性 | `grape git --help` 不再展示 `--repo` 说明 | ⚠️ 由 `grape --help`（git 命令描述）+ README 承担 |

---

## 六、验证

- 新增测试：`grape git --help` 输出含 `usage: git`
- 回归：`grape git --repo owner/repo status` 凭据注入用例不受影响（43+ 现有用例全绿）
- 手动验证：
  ```bash
  grape git --help   # 输出 = git --help
  grape git -h       # 输出 = git -h
  ```

---

## 七、备选方案（不推荐）

1. **自定义 click help 文案模仿 git**：需复刻 git 各版本 usage，脆弱、难维护
2. **保持现状仅补文档**：`-h`/`--help` 行为不一致依旧，违背“grape git ≈ git”定位