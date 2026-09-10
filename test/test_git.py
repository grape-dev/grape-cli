"""grape git：裸用自动识别仓库 + 免凭据注入 + help 透传 + 降级策略。"""
import subprocess

import pytest
from click.testing import CliRunner

from src.cli import cli
from src.commands import git as git_mod
from src.client import CliError


class _FakeRun:
    def __init__(self, returncode=0):
        self.returncode = returncode


class _FakeApi:
    def __init__(self, username="x-access-token", password="gitcode_pat"):
        self.username = username
        self.password = password

    def request(self, method, path):
        if path.endswith("/git-credential"):
            return 200, {"username": self.username, "password": self.password}
        raise AssertionError(f"unexpected path: {path}")


@pytest.fixture
def git_env(monkeypatch):
    captured = {}

    def _fake_run(cmd, env=None, **kw):
        captured["cmd"] = cmd
        captured["env"] = env
        return _FakeRun()

    monkeypatch.setattr("src.commands.git.shutil.which", lambda _: "git")
    monkeypatch.setattr("src.commands.git.subprocess.run", _fake_run)
    # 默认：不做 cwd 识别 → 无注入
    monkeypatch.setattr("src.commands.git._repo_from_cwd", lambda cwd=None: "")
    return captured


# ---------- 命令形态 ----------

def test_no_repo_option_anymore():
    cmd = cli.get_command(None, "git")
    assert not any(p.name == "repo" for p in cmd.params)


def test_help_passthrough_to_git(git_env):
    res = CliRunner().invoke(cli, ["git", "--help"])
    assert res.exit_code == 0
    assert git_env["cmd"] == ["git", "--help"]
    assert "GIT_CONFIG_COUNT" not in git_env["env"]


def test_short_h_passthrough_to_git(git_env):
    res = CliRunner().invoke(cli, ["git", "-h"])
    assert res.exit_code == 0
    assert git_env["cmd"] == ["git", "-h"]


def test_help_cmd_passthrough_to_git(git_env):
    res = CliRunner().invoke(cli, ["git", "help"])
    assert res.exit_code == 0
    assert git_env["cmd"] == ["git", "help"]


# ---------- URL 识别 ----------

def test_repo_from_url_https():
    assert git_mod._repo_from_url("https://gitcode.com/Jason7602/hello-html1.git") == "Jason7602/hello-html1"


def test_repo_from_url_https_no_suffix():
    assert git_mod._repo_from_url("https://gitcode.com/o/r") == "o/r"


def test_repo_from_url_scp_like():
    assert git_mod._repo_from_url("git@gitcode.com:o/r.git") == "o/r"


def test_repo_from_url_ssh_scheme():
    assert git_mod._repo_from_url("ssh://git@gitcode.com/o/r.git") == "o/r"


def test_repo_from_url_rejects_non_gitcode():
    assert git_mod._repo_from_url("https://github.com/x/y.git") == ""
    assert git_mod._repo_from_url("https://gitlab.com/x/y.git") == ""


def test_repo_from_url_rejects_empty():
    assert git_mod._repo_from_url("") == ""
    assert git_mod._repo_from_url("   ") == ""


def test_repo_from_cwd_real_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "remote", "add", "origin", "https://gitcode.com/o/r.git"],
                   cwd=str(tmp_path), check=True)
    assert git_mod._repo_from_cwd(str(tmp_path)) == "o/r"


def test_repo_from_cwd_non_git_repo_returns_empty(tmp_path):
    assert git_mod._repo_from_cwd(str(tmp_path)) == ""


def test_repo_from_args_clone_uses_url_arg():
    args = ["clone", "--branch", "main", "https://gitcode.com/o/r.git"]
    assert git_mod._repo_from_args(args) == "o/r"


def test_repo_from_args_clone_non_gitcode_empty():
    assert git_mod._repo_from_args(["clone", "https://github.com/x/y.git"]) == ""


def test_repo_from_args_non_clone_uses_cwd(monkeypatch):
    monkeypatch.setattr(git_mod, "_repo_from_cwd", lambda cwd=None: "o/r")
    assert git_mod._repo_from_args(["push"]) == "o/r"


# ---------- 注入行为 ----------

def test_git_clone_injects_credentials_from_url(git_env, monkeypatch):
    monkeypatch.setattr("src.commands.git.ApiClient", lambda *a, **k: _FakeApi())
    res = CliRunner().invoke(cli, ["git", "clone", "https://gitcode.com/o/r.git"])
    assert res.exit_code == 0
    assert git_env["cmd"] == ["git", "clone", "https://gitcode.com/o/r.git"]
    env = git_env["env"]
    assert env["GIT_CONFIG_COUNT"] == "1"
    assert env["GIT_CONFIG_KEY_0"] == "http.extraheader"
    assert env["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")


def test_git_push_injects_from_cwd(git_env, monkeypatch):
    monkeypatch.setattr("src.commands.git.ApiClient", lambda *a, **k: _FakeApi())
    monkeypatch.setattr("src.commands.git._repo_from_cwd", lambda cwd=None: "owner/repo")
    res = CliRunner().invoke(cli, ["git", "push"])
    assert res.exit_code == 0
    assert git_env["cmd"] == ["git", "push"]
    assert git_env["env"]["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")


def test_git_status_no_repo_no_injection(git_env):
    res = CliRunner().invoke(cli, ["git", "status"])
    assert res.exit_code == 0
    assert git_env["cmd"] == ["git", "status"]
    assert "GIT_CONFIG_COUNT" not in git_env["env"]


def test_git_non_gitcode_url_no_injection(git_env):
    res = CliRunner().invoke(cli, ["git", "clone", "https://github.com/x/y.git"])
    assert res.exit_code == 0
    assert "GIT_CONFIG_COUNT" not in git_env["env"]


def test_git_keeps_existing_git_config_count_offset(git_env, monkeypatch):
    monkeypatch.setattr("src.commands.git.ApiClient", lambda *a, **k: _FakeApi())
    monkeypatch.setattr("src.commands.git._repo_from_cwd", lambda cwd=None: "owner/repo")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")  # 模拟用户已有 git config env
    res = CliRunner().invoke(cli, ["git", "push"])
    assert res.exit_code == 0
    assert git_env["env"]["GIT_CONFIG_COUNT"] == "3"
    assert "GIT_CONFIG_KEY_2" in git_env["env"]


def test_git_propagates_failure_exit_code(git_env, monkeypatch):
    monkeypatch.setattr("src.commands.git.subprocess.run",
                        lambda *a, **kw: _FakeRun(returncode=128))
    res = CliRunner().invoke(cli, ["git", "status"])
    assert res.exit_code == 128


def test_git_missing_binary_raises(monkeypatch, isolate_config):
    monkeypatch.setattr("src.commands.git.shutil.which", lambda _: None)
    res = CliRunner().invoke(cli, ["git", "status"])
    assert res.exit_code == 1
    assert "git" in res.output


# ---------- 降级策略 ----------

def test_git_credential_missing_fields_warns_and_continues(git_env, monkeypatch):
    class _BadApi:
        def request(self, method, path):
            return 200, {"username": "u"}  # 缺 password

    monkeypatch.setattr("src.commands.git.ApiClient", lambda *a, **k: _BadApi())
    monkeypatch.setattr("src.commands.git._repo_from_cwd", lambda cwd=None: "o/r")
    res = CliRunner().invoke(cli, ["git", "status"])
    assert res.exit_code == 0
    assert git_env["cmd"] == ["git", "status"]
    assert "git-credential" in (res.output + getattr(res, "stderr", ""))


def test_git_credentials_unavailable_warns_and_continues(git_env, monkeypatch):
    class _DownApi:
        def request(self, method, path):
            raise CliError("HTTP 403: Forbidden", code=403)

    monkeypatch.setattr("src.commands.git.ApiClient", lambda *a, **k: _DownApi())
    monkeypatch.setattr("src.commands.git._repo_from_cwd", lambda cwd=None: "o/r")
    res = CliRunner().invoke(cli, ["git", "status"])
    assert res.exit_code == 0
    assert "credential injection failed" in (res.output + getattr(res, "stderr", ""))