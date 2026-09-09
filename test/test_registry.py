"""契约 → 命令树：operationId 解析、分组、选项生成。"""
from src.registry import (
    GROUP_ALIAS,
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