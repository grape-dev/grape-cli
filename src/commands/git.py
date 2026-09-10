"""grape git 本地执行（方案③）：git 原生命令透传 + 进程内凭据注入（token 零暴露）。

- `--repo` 解析工作区（GET /api/repos/{o}/{r}/workspace）；
- 平台 token 经 `GET /api/repos/{o}/{r}/git-credential` 获取，仅以 GIT_CONFIG env 注入 git 子进程
  （不进命令行、不落磁盘、不写 agent 工作区）；其余参数原样透传 git。
"""
import os
import shutil
import subprocess
import sys

import click

from src.client import ApiClient, CliError, basic_auth


def git_command() -> click.Command:
    @click.command(name="git", help="Run git locally: passthrough any native git command (credentials injected in-process)",
                   context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
    @click.option("--repo", default="", help="owner/repo (resolve workspace & credentials)")
    @click.pass_context
    def git_cmd(ctx, repo: str):
        if not shutil.which("git"):
            raise click.ClickException("未找到 git 可执行文件")

        env = dict(os.environ)
        cwd = None
        if repo:
            api = ApiClient()
            _s, ws = api.request("GET", f"/api/repos/{repo}/workspace")
            cwd = ws.get("workspace")
            _s, cred = api.request("GET", f"/api/repos/{repo}/git-credential")
            username, password = cred.get("username"), cred.get("password")
            if not username or not password:
                raise CliError(
                    f"服务端 git-credential 响应缺少 username/password 字段（仓库 {repo}）"
                )
            env["GIT_CONFIG_COUNT"] = "1"
            env["GIT_CONFIG_KEY_0"] = "http.extraheader"
            env["GIT_CONFIG_VALUE_0"] = f"Authorization: {basic_auth(username, password)}"

        cmd = ["git"] + list(ctx.args)
        try:
            r = subprocess.run(cmd, env=env, cwd=cwd)
        except KeyboardInterrupt:
            # Ctrl+C 时 git 与 CLI 同控制组已收到中断；拉起主入口统一 130 收口
            raise
        except OSError as e:
            raise click.ClickException(f"git 执行失败: {e}")
        sys.exit(r.returncode)

    return git_cmd