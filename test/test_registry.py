"""契约 → 命令树：operationId 解析、分组、选项生成。"""
import json

from src.registry import (
    GROUP_ALIAS,
    _en_summary,
    build_command,
    build_groups,
    command_tree,
    parse_operations,
)

BARE_SCHEMA = {
    "paths": {
        "/api/skills": {
            "get": {
                "operationId": "skills_list",
            }
        }
    }
}


def test_group_alias_maps_gitrepo(sample_schema):
    ops = parse_operations(sample_schema)
    groups = {o["group"] for o in ops}
    assert "git-repo" in groups
    assert GROUP_ALIAS["gitrepo"] == "git-repo"


def test_verb_defaults_to_list_for_bare_operation_id():
    ops = parse_operations(BARE_SCHEMA)
    by_id = {o["operationId"]: o for o in ops}
    assert by_id["skills_list"]["verb"] == ["list"]
    assert by_id["skills_list"]["group"] == "skills"


def test_command_tree_shape(sample_schema):
    tree = command_tree(sample_schema)
    assert sorted(tree["tasks"]) == ["create", "mine"]
    assert tree["git-repo"] == ["issues_list"]
    assert tree["skills"] == ["list"]


def test_build_groups_nested_verbs(sample_schema):
    groups = build_groups(sample_schema)
    assert "git-repo" in groups
    verbs = [c.name for c in groups["git-repo"].commands.values()]
    assert "issues" in verbs
    sub = groups["git-repo"].commands["issues"]
    assert "list" in sub.commands


def test_generated_command_options(sample_schema):
    ops = parse_operations(sample_schema)
    op = next(o for o in ops if o["operationId"] == "gitrepo_issues_list")
    cmd = build_command(op)
    opt_names = {p.name for p in cmd.params}
    expect = {"owner", "repo", "state", "json_out"}
    assert expect.issubset(opt_names)
    assert "json" not in opt_names  # 无 requestBody 时不生成 --json


def test_generated_command_short_help_is_summary(sample_schema):
    ops = parse_operations(sample_schema)
    op = next(o for o in ops if o["operationId"] == "gitrepo_issues_list")
    cmd = build_command(op)
    short = cmd.get_short_help_str()
    assert short.startswith("List issues")
    assert "Invoke grape API: GET" in cmd.help


def test_group_help_derives_verb_meanings(sample_schema):
    groups = build_groups(sample_schema)
    tasks = groups["tasks"]
    assert "mine" in tasks.help
    assert "My task list" in tasks.help
    assert "create" in tasks.help

    git_grp = groups["git-repo"]
    sub = git_grp.commands["issues"]
    assert "list" in sub.help
    assert "List issues" in sub.help


def test_git_repo_group_has_platform_api_intro(sample_schema):
    groups = build_groups(sample_schema)
    git_grp = groups["git-repo"]
    assert git_grp.help.startswith("Platform API by grape")
    assert "no extra token setup" in git_grp.help.lower()


def test_contract_group_accepts_short_help_flag(sample_schema):
    groups = build_groups(sample_schema)
    ctx = {"help_option_names": groups["tasks"].context_settings.get("help_option_names")}
    assert "-h" in groups["tasks"].context_settings["help_option_names"]


def test_generated_command_help_marks_method_and_body(sample_schema):
    ops = parse_operations(sample_schema)
    by_id = {o["operationId"]: o for o in ops}
    create = build_command(by_id["tasks_create"])
    mine = build_command(by_id["tasks_mine"])
    assert "(POST, body: yes)" in create.help.splitlines()[0]
    assert "(GET, body: no)" in mine.help.splitlines()[0]


def test_generated_command_help_has_example(sample_schema):
    ops = parse_operations(sample_schema)
    op = next(o for o in ops if o["operationId"] == "tasks_create")
    cmd = build_command(op)
    assert "Examples:" in cmd.help
    assert "grape tasks create" in cmd.help
    assert "--json" in cmd.help


def test_issues_update_help_discloses_body_fields():
    from src.contracts import load_bundled

    groups = build_groups(load_bundled())
    update = groups["git-repo"].commands["issues"].commands["update"]
    assert "Body fields" in update.help
    assert "assignee" in update.help
    assert "state" in update.help
    assert "Examples:" in update.help


def test_unknown_body_field_rejected(monkeypatch, isolate_config):
    from click.testing import CliRunner
    from src.cli import cli
    from src.client import CliError

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    update = cli.get_command(None, "git-repo").commands["issues"].commands["update"]
    res = CliRunner().invoke(update, ["--owner", "o", "--repo", "r", "--number", "7",
                                      "--json", '{"body":"x"}'])
    assert res.exit_code != 0
    assert isinstance(res.exception, CliError)
    assert "unknown request field(s): body" in str(res.exception)
    assert "assignee" in str(res.exception)
    assert "--help" in str(res.exception)


def test_allowed_body_field_passes_to_request(monkeypatch, fake_httpx):
    from click.testing import CliRunner
    from src.cli import cli

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    monkeypatch.setenv("GRAPE_BASE_URL", "http://x")
    calls = fake_httpx({"/api/repos/o/r/issues/7": (200, {"ok": True})})
    update = cli.get_command(None, "git-repo").commands["issues"].commands["update"]
    res = CliRunner().invoke(update, ["--owner", "o", "--repo", "r", "--number", "7",
                                      "--json", '{"state":"closed"}'])
    assert res.exit_code == 0
    patch_bodies = [k.get("json") for m, _, k in calls if m == "PATCH"]
    assert {"state": "closed"} in patch_bodies


def test_freeform_body_not_validated(sample_schema):
    # 无具名 properties（自由格式）→ 不拦截未知字段
    from src.registry import _body_fields, _validate_body

    ops = parse_operations(sample_schema)
    meta = next(o for o in ops if o["operationId"] == "tasks_create")
    bf = _body_fields(meta)
    assert bf == []
    _validate_body(meta, {"anything": 1}, bf)  # 不抛异常


def test_en_summary_overlay_falls_back_to_contract(sample_schema):
    # 覆盖层未收录的 operationId 回落契约 summary
    op = {"operationId": "custom_thing", "summary": "Do a custom thing"}
    assert _en_summary(op) == "Do a custom thing"


def test_en_summary_overlay_preferred(monkeypatch):
    op = {"operationId": "tasks_mine", "summary": "中文摘要"}
    assert _en_summary(op) == "My task list"