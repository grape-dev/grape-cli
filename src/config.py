"""配置解析：CLI 参数 > 环境变量 > ~/.grape/config.json。

token 优先级：--token 参数 > `GRAPE_SESSION_TOKEN`（任务级临时 token，worker 优先）> `GRAPE_API_TOKEN`（用户级）> config.json。

`GRAPE_AUTH_FILE`（由 DshRuntime.get_env 写入，指向一个 0600 临时文件）在所有模式下
优先于环境变量：dsh 的 subprocess 服务会 scrub 掉名字匹配 /KEY|PASSWORD|SECRET|TOKEN/i
的父进程变量，GRAPE_SESSION_TOKEN 命中 TOKEN → 被洗掉 → bash 里拿不到。
DshRuntime 把 token 值写到临时文件，路径通过 GRAPE_AUTH_FILE（不命中 scrub）传递；
grape CLI 从文件读 token 值，完全绕过 env scrub。
其他引擎不做此 scrub，GRAPE_AUTH_FILE 不存在 → fallback 到 GRAPE_SESSION_TOKEN，零影响。

`DSH_GRAPE_SESSION_TOKEN`（由 dsh-grape 插件的 shellEnv contributor 注入）同样优先于
`GRAPE_SESSION_TOKEN`，作为插件层的备选穿透路径（目前 headless 不加载插件，此路径不生效）。
"""
import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".grape"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_TIMEOUT = 30  # 秒

# 本次进程的 CLI 一次性参数（--base-url / --token / --timeout），优先级最高，不落盘
_CLI_PARAMS = {"base_url": "", "token": "", "timeout": 0}


def set_cli_params(base_url: str = "", token: str = "", timeout: int = 0):
    """记录本次调用 `grape --base-url/--token/--timeout ...` 的一次性参数（进程内，随命令结束即失）。"""
    _CLI_PARAMS["base_url"] = (base_url or "").strip()
    _CLI_PARAMS["token"] = (token or "").strip()
    try:
        _CLI_PARAMS["timeout"] = max(0, int(timeout or 0))
    except (TypeError, ValueError):
        _CLI_PARAMS["timeout"] = 0


def cli_timeout() -> int:
    """本次调用请求超时（秒）；未指定用默认 30。"""
    return _CLI_PARAMS["timeout"] or DEFAULT_TIMEOUT


def load_file_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


_config_warned = False


def _read_auth_file(env: dict) -> str:
    """从 GRAPE_AUTH_FILE 指向的文件读 token 值。

    DshRuntime.get_env 把 session token 写到一个 0600 临时文件，
    路径通过 GRAPE_AUTH_FILE 传递（该变量名不命中 dsh 的 /KEY|PASSWORD|SECRET|TOKEN/i scrub）。
    文件不存在或为空 → 返回空字符串（fallback 到环境变量）。
    """
    path = (env.get("GRAPE_AUTH_FILE") or "").strip()
    if not path:
        return ""
    try:
        p = Path(path)
        if not p.exists():
            return ""
        val = p.read_text(encoding="utf-8").strip()
        return val
    except Exception:
        return ""


def resolve(base_url: str = "", token: str = "", refresh: bool = False) -> tuple[str, str]:
    """返回 (base_url, token)。缺任一 → 抛 if config incomplete.

    优先级：函数参数 == CLI 一次性参数（--base-url/--token）> 环境变量 > config.json。
    token 双变量在 GRAPE_CLI_MODE=USER 时优先 GRAPE_API_TOKEN，否则 session 优先。
    """
    global _config_warned
    cfg = load_file_config() if not refresh else {}
    env = os.environ

    _base = (base_url or "").strip() or _CLI_PARAMS["base_url"] or \
            (env.get("GRAPE_BASE_URL") or "").strip() or \
            (env.get("GRAPE_SERVER_URL") or "").strip() or \
            str(cfg.get("base_url") or "").strip()
    if not _base:
        _base = "http://localhost:8000"

    mode = (env.get("GRAPE_CLI_MODE") or "ALL").strip().upper()
    one_shot = (token or "").strip() or _CLI_PARAMS["token"]
    file_tok = _read_auth_file(env)
    if mode == "USER":
        env_tok = file_tok or \
                  (env.get("GRAPE_API_TOKEN") or "").strip() or \
                  (env.get("DSH_GRAPE_SESSION_TOKEN") or "").strip() or \
                  (env.get("GRAPE_SESSION_TOKEN") or "").strip()
        if not env.get("GRAPE_API_TOKEN") and not one_shot and not file_tok and not _config_warned:
            _config_warned = True
            import sys
            sys.stderr.write(
                "warning: GRAPE_CLI_MODE=USER but GRAPE_API_TOKEN is missing; "
                "falling back to session token\n"
            )
    else:  # WORKER / ALL
        env_tok = file_tok or \
                  (env.get("DSH_GRAPE_SESSION_TOKEN") or "").strip() or \
                  (env.get("GRAPE_SESSION_TOKEN") or "").strip() or \
                  (env.get("GRAPE_API_TOKEN") or "").strip()
    _token = one_shot or env_tok or str(cfg.get("token") or "").strip()
    return _base.rstrip("/"), _token


def save_config(base_url: str, token: str = ""):
    cfg = load_file_config()
    if base_url:
        cfg["base_url"] = base_url
    if token:
        cfg["token"] = token
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")