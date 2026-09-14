"""CLI 端到端：version / help / 契约命令 / wait / api 兜底。"""
import json
import re

import pytest
from click.testing import CliRunner

from src.cli import cli


@pytest.fixture
def env(monkeypatch, isolate_config):
    monkeypatch.setenv("GRAPE_BASE_URL", "https://grape.test")
    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    return {}


@pytest.fixture
def standard_router(sample_schema):
    return {
        "/openapi.json": (200, sample_schema),
        "/api/tasks/mine": (200, {"items": [], "status": "completed"}),
        "/api/scenes": (200, {"scenes": ["s1", "s2"]}),
        "/api/tasks/9/status": (200, {"status": "completed", "id": 9}),
    }


def test_version(env):
    res = CliRunner().invoke(cli, ["--version"])
    assert res.exit_code == 0
    assert re.match(r"grape 0\.\d+\.\d+", res.output.strip())


def test_version_short_flag(env):
    res = CliRunner().invoke(cli, ["-v"])
    assert res.exit_code == 0
    assert re.match(r"grape 0\.\d+\.\d+", res.output.strip())


def test_help_short_flag(env):
    res = CliRunner().invoke(cli, ["-h"])
    assert res.exit_code == 0
    assert "Commands:" in res.output


def test_help_categories(env, fake_httpx, standard_router):
    fake_httpx(standard_router)
    res = CliRunner().invoke(cli, ["--help"])
    assert res.exit_code == 0
    for cat in ("Core workflows", "Code & repositories",
                "Account & platform", "CLI utilities"):
        assert cat in res.output
    assert "session-only" in res.output
    assert "session tk_ rejected" in res.output


def test_help_categories_agent_context_with_bundled(env, fake_httpx):
    """bundled 契约含 issues/events/knowledge → Agent Context 分类出现。"""
    fake_httpx({})  # 全部 404 → 契约回退 bundled
    res = CliRunner().invoke(cli, ["--help"])
    assert res.exit_code == 0
    assert "Agent Context" in res.output
    assert "issues" in res.output
    assert "knowledge" in res.output


def test_help_lists_builtins(env):
    res = CliRunner().invoke(cli, ["--help"])
    assert res.exit_code == 0
    for name in ("git", "refresh", "commands"):
        assert name in res.output


def test_commands_lists_contract_commands(env, fake_httpx, standard_router):
    fake_httpx(standard_router)
    res = CliRunner().invoke(cli, ["commands"])
    assert res.exit_code == 0
    assert "tasks mine" in res.output
    assert "git-repo issues_list" in res.output


def test_generated_command_runs(env, fake_httpx, standard_router):
    fake_httpx(standard_router)
    res = CliRunner().invoke(cli, ["tasks", "mine", "--status", "active"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["status"] == "completed"


def test_json_out_single_line(env, fake_httpx, standard_router):
    fake_httpx(standard_router)
    res = CliRunner().invoke(cli, ["tasks", "mine", "--json-out"])
    assert res.exit_code == 0
    assert res.output.strip().startswith("{")
    assert "\n" not in res.output.strip()


def test_path_params_build_url(env, fake_httpx, standard_router):
    called = []
    router = dict(standard_router)

    def issues_handler(method, url, kwargs):
        called.append((url, kwargs))
        return __import__("conftest", fromlist=["FakeResponse"]).FakeResponse(200, {"count": 1})

    router["/api/repos/o/r/issues"] = issues_handler
    fake_httpx(router)
    res = CliRunner().invoke(cli, ["git-repo", "issues", "list", "--owner", "o", "--repo", "r", "--state", "open"])
    assert res.exit_code == 0
    url, kwargs = called[0]
    from urllib.parse import urlsplit

    assert urlsplit(url).path == "/api/repos/o/r/issues"
    assert kwargs["params"] == {"state": "open"}


def test_wait_returns_terminal_state(env, fake_httpx, standard_router):
    fake_httpx(standard_router)
    res = CliRunner().invoke(cli, ["tasks", "wait", "--task-id", "9", "--timeout", "10"])
    assert res.exit_code == 0
    assert json.loads(res.output)["status"] == "completed"


def test_wait_polls_until_terminal(env, fake_httpx, sample_schema):
    router = {
        "/openapi.json": (200, sample_schema),
        "/api/tasks/9/status": (200, {"status": "running"}),
    }
    results = [{"status": "running"}, {"status": "completed", "id": 9}]

    def status_handler(method, url, kwargs):
        return __import__("conftest", fromlist=["FakeResponse"]).FakeResponse(200, results.pop(0))

    router["/api/tasks/9/status"] = status_handler
    fake_httpx(router)
    res = CliRunner().invoke(cli, ["tasks", "wait", "--task-id", "9", "--timeout", "120", "--interval", "0"])
    assert res.exit_code == 0
    assert json.loads(res.output)["status"] == "completed"


def test_commands_help_hints_pattern_filter(env):
    res = CliRunner().invoke(cli, ["commands", "--help"])
    assert res.exit_code == 0
    assert "grape commands issue" in res.output
    assert "filter" in res.output


def test_commands_no_pattern_hints_on_stderr(env, fake_httpx, standard_router):
    fake_httpx(standard_router)
    res = CliRunner().invoke(cli, ["commands"])
    assert res.exit_code == 0
    assert "grape commands <pattern>" in res.output


def test_subgroup_bare_invocation_shows_help(env, fake_httpx, standard_router):
    fake_httpx(standard_router)
    res = CliRunner().invoke(cli, ["git-repo", "issues"])
    # 裸组展示 Commands（可用动词）；exit 2 为 click 约定但帮助可见
    assert res.exit_code in (0, 2)
    assert "list" in (res.output + getattr(res, "stderr", ""))


def test_subgroup_with_stray_args_shows_help_not_error(env, fake_httpx, standard_router):
    fake_httpx(standard_router)
    res = CliRunner().invoke(cli, ["git-repo", "issues", "--state", "all"])
    assert res.exit_code == 0
    assert "No such option" not in res.output
    assert "list" in res.output


def test_unknown_subcommand_suggests_similar(env, fake_httpx, standard_router):
    fake_httpx(standard_router)
    res = CliRunner().invoke(cli, ["git-repo", "issuess"])
    assert res.exit_code != 0
    out = res.output + getattr(res, "stderr", "")
    assert "Did you mean" in out
    assert "issues" in out


def test_missing_token_fails_readably(monkeypatch, isolate_config):
    from src.client import CliError

    monkeypatch.delenv("GRAPE_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("GRAPE_API_TOKEN", raising=False)
    res = CliRunner().invoke(cli, ["git-repo", "issues", "get",
                                   "--owner", "o", "--repo", "r", "--number", "1"])
    assert res.exit_code != 0
    assert isinstance(res.exception, CliError)
    assert "token" in str(res.exception)