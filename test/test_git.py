"""grape git 本地透传：凭据注入 + 工作区解析 + 参数透传。"""
from click.testing import CliRunner

from src.cli import cli


class _FakeApi:
    def __init__(self, workspace="C:\\ws"):
        self.workspace = workspace

    def request(self, method, path):
        if path.endswith("/workspace"):
            return 200, {"workspace": self.workspace}
        if path.endswith("/git-credential"):
            return 200, {"username": "u", "password": "p"}
        raise AssertionError(f"unexpected path: {path}")


class _FakeRun:
    def __init__(self, returncode=0):
        self.returncode = returncode


def test_git_passthrough_injects_credentials(monkeypatch, isolate_config):
    monkeypatch.setattr("src.commands.git.ApiClient", lambda: _FakeApi())
    captured = {}

    def _fake_run(cmd, env=None, cwd=None, **kw):
        captured["cmd"] = cmd
        captured["env"] = env
        captured["cwd"] = cwd
        return _FakeRun()

    monkeypatch.setattr("src.commands.git.shutil.which", lambda _: "git")
    monkeypatch.setattr("src.commands.git.subprocess.run", _fake_run)
    res = CliRunner().invoke(cli, ["git", "--repo", "owner/repo", "status"])
    assert res.exit_code == 0
    assert captured["cmd"] == ["git", "status"]
    assert captured["cwd"] == "C:\\ws"
    assert captured["env"]["GIT_CONFIG_COUNT"] == "1"
    assert captured["env"]["GIT_CONFIG_KEY_0"] == "http.extraheader"
    assert captured["env"]["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")


def test_git_without_repo_runs_in_cwd_and_no_creds(monkeypatch, isolate_config):
    captured = {}

    def _fake_run(cmd, env=None, cwd=None, **kw):
        captured["cmd"] = cmd
        captured["env"] = env
        captured["cwd"] = cwd
        return _FakeRun()

    monkeypatch.setattr("src.commands.git.shutil.which", lambda _: "git")
    monkeypatch.setattr("src.commands.git.subprocess.run", _fake_run)
    res = CliRunner().invoke(cli, ["git", "log", "--oneline", "-5"])
    assert res.exit_code == 0
    assert captured["cmd"] == ["git", "log", "--oneline", "-5"]
    assert captured["cwd"] is None
    assert "GIT_CONFIG_COUNT" not in captured["env"]


def test_git_propagates_failure_exit_code(monkeypatch, isolate_config):
    monkeypatch.setattr("src.commands.git.shutil.which", lambda _: "git")
    monkeypatch.setattr("src.commands.git.subprocess.run", lambda *a, **kw: _FakeRun(returncode=128))
    res = CliRunner().invoke(cli, ["git", "status"])
    assert res.exit_code == 128


def test_git_missing_binary_raises(monkeypatch, isolate_config):
    monkeypatch.setattr("src.commands.git.shutil.which", lambda _: None)
    res = CliRunner().invoke(cli, ["git", "status"])
    assert res.exit_code == 1
    assert "git" in res.output