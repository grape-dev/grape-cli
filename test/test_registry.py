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
    assert short.startswith("List repo issues")
    assert "Invoke grape API: GET" in cmd.help


def test_group_help_derives_verb_meanings(sample_schema):
    groups = build_groups(sample_schema)
    tasks = groups["tasks"]
    assert "mine" in tasks.help
    assert "Mine tasks" in tasks.help
    assert "create" in tasks.help

    git_grp = groups["git-repo"]
    sub = git_grp.commands["issues"]
    assert "list" in sub.help
    assert "List repo issues" in sub.help


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
    op = next(o for o in ops if o["operationId"] == "gitrepo_issues_list")
    cmd = build_command(op)
    assert "Examples:" in cmd.help
    assert "grape git-repo issues list" in cmd.help
    assert "--owner" in cmd.help


def test_contents_help_has_bidirectional_examples():
    from src.contracts import load_bundled

    groups = build_groups(load_bundled())
    contents = groups["git-repo"].commands["contents"]
    assert "Examples:" in contents.help
    assert '--path ""' in contents.help
    assert "--path README.md" in contents.help
    assert "list root" in contents.help or "--path \"\"" in contents.help


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
                                      "--json", '{"assignee_ids":[1]}'])
    assert res.exit_code != 0
    assert isinstance(res.exception, CliError)
    assert "unknown request field(s): assignee_ids" in str(res.exception)
    assert "assignee" in str(res.exception)


def test_issues_update_body_now_allowed(monkeypatch, fake_httpx):
    """服务端已支持 issues update 的 body 字段 → 守卫放行。"""
    from click.testing import CliRunner
    from src.cli import cli

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    monkeypatch.setenv("GRAPE_BASE_URL", "http://x")
    calls = fake_httpx({"/api/git-repo/o/r/issues/7": (200, {"ok": True})})
    update = cli.get_command(None, "git-repo").commands["issues"].commands["update"]
    res = CliRunner().invoke(update, ["--owner", "o", "--repo", "r", "--number", "7",
                                      "--json", '{"body":"new body"}'])
    assert res.exit_code == 0
    patch_bodies = [k.get("json") for m, _, k in calls if m == "PATCH"]
    assert {"body": "new body"} == patch_bodies[0]


def test_json_at_file_supported(monkeypatch, fake_httpx, tmp_path):
    """--json @file.json 读取请求体（curl 风格）。"""
    from click.testing import CliRunner
    from src.cli import cli

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    monkeypatch.setenv("GRAPE_BASE_URL", "http://x")
    payload = tmp_path / "payload.json"
    payload.write_text('{"state":"closed"}', encoding="utf-8")
    calls = fake_httpx({"/api/git-repo/o/r/issues/7": (200, {"ok": True})})
    update = cli.get_command(None, "git-repo").commands["issues"].commands["update"]
    res = CliRunner().invoke(update, ["--owner", "o", "--repo", "r", "--number", "7",
                                      "--json", f"@{payload}"])
    assert res.exit_code == 0
    patch_bodies = [k.get("json") for m, _, k in calls if m == "PATCH"]
    assert {"state": "closed"} in patch_bodies


def test_json_at_missing_file_errors(monkeypatch, fake_httpx, tmp_path):
    from click.testing import CliRunner
    from src.cli import cli
    from src.client import CliError

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    monkeypatch.setenv("GRAPE_BASE_URL", "http://x")
    fake_httpx({})
    update = cli.get_command(None, "git-repo").commands["issues"].commands["update"]
    res = CliRunner().invoke(update, ["--owner", "o", "--repo", "r", "--number", "7",
                                      "--json", "@/no/such/file.json"])
    assert res.exit_code != 0
    assert isinstance(res.exception, CliError)
    assert "cannot read --json file" in str(res.exception)


def test_contents_omits_path_lists_root(monkeypatch, fake_httpx):
    """contents 缺省 --path → 根目录列表（规整到 /contents 根路由）。"""
    from urllib.parse import urlsplit
    from click.testing import CliRunner
    from src.cli import cli

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    monkeypatch.setenv("GRAPE_BASE_URL", "http://x")
    calls = fake_httpx({"/api/git-repo/o/r/contents": (200, [{"type": "dir", "name": "configs"}])})
    contents = cli.get_command(None, "git-repo").commands["contents"]
    res = CliRunner().invoke(contents, ["--owner", "o", "--repo", "r"])
    assert res.exit_code == 0
    gotten = [urlsplit(u).path for _, u, _ in calls if "contents" in u]
    assert "/api/git-repo/o/r/contents" in gotten
    assert not any(x.endswith("/contents/") for x in gotten)


def test_other_required_path_param_still_enforced(monkeypatch, fake_httpx):
    from click.testing import CliRunner
    from src.cli import cli
    from src.client import CliError

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    fake_httpx({})
    get_issue = cli.get_command(None, "git-repo").commands["issues"].commands["get"]
    res = CliRunner().invoke(get_issue, ["--owner", "o", "--repo", "r"])  # 缺 --number
    assert res.exit_code != 0
    assert isinstance(res.exception, CliError)
    assert "Missing required parameter --number" in str(res.exception)


def test_d_scope_403_appends_user_key_hint(monkeypatch, fake_httpx, isolate_config):
    """D 类（user_only）403 → 追加英文行动指引。"""
    from click.testing import CliRunner
    from src.cli import cli
    from src.client import CliError

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    monkeypatch.setenv("GRAPE_BASE_URL", "http://x")
    fake_httpx({"/api/skills": (403, {"message": "该接口不支持会话 token"})})
    skills = cli.get_command(None, "skills").commands["list"]
    res = CliRunner().invoke(skills, [])
    assert isinstance(res.exception, CliError)
    assert res.exception.code == 403
    assert "use GRAPE_API_TOKEN / Web JWT" in str(res.exception)
    assert "session token (tk_) is rejected" in str(res.exception)


def test_allow_scope_403_not_appended(monkeypatch, fake_httpx, isolate_config):
    """非 D 类 403 → 不追加 user key 指引（原样）。"""
    from click.testing import CliRunner
    from src.cli import cli
    from src.client import CliError

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    monkeypatch.setenv("GRAPE_BASE_URL", "http://x")
    fake_httpx({"/api/tasks/mine": (403, {"message": "forbidden"})})
    mine = cli.get_command(None, "tasks").commands["mine"]
    res = CliRunner().invoke(mine, [])
    assert isinstance(res.exception, CliError)
    assert res.exception.code == 403
    assert "use GRAPE_API_TOKEN" not in str(res.exception)


def test_skills_upload_sends_multipart(monkeypatch, fake_httpx, tmp_path, isolate_config):
    """skills upload：--file 以 multipart 发送（files+form data）。"""
    from click.testing import CliRunner
    from src.cli import cli

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    monkeypatch.setenv("GRAPE_BASE_URL", "http://x")
    zipf = tmp_path / "myskill.zip"
    zipf.write_bytes(b"PK\x03\x04 fakezip")
    calls = fake_httpx({"/api/skills/upload": (200, {"message": "ok"})})
    upload = cli.get_command(None, "skills").commands["upload"]
    res = CliRunner().invoke(upload, ["--file", str(zipf), "--scope", "user",
                                      "--agent_type", "coding"])
    assert res.exit_code == 0
    assert "ok" in res.output
    ups = [k for m, _, k in calls if m == "POST"]
    assert ups and ups[0]["files"]["file"][0] == "myskill.zip"
    assert ups[0]["files"]["file"][1] == b"PK\x03\x04 fakezip"
    assert ups[0]["data"] == {"scope": "user", "agent_type": "coding"}
    assert ups[0]["json"] is None


def test_skills_upload_requires_file(monkeypatch, fake_httpx, isolate_config):
    from click.testing import CliRunner
    from src.cli import cli
    from src.client import CliError

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    monkeypatch.setenv("GRAPE_BASE_URL", "http://x")
    fake_httpx({})
    upload = cli.get_command(None, "skills").commands["upload"]
    res = CliRunner().invoke(upload, ["--scope", "user"])
    assert isinstance(res.exception, CliError)
    assert "Missing required --file" in str(res.exception)


def test_token_scope_reads_contract_field_first():
    """契约 x-token-scope 优先于静态表。"""
    from src.registry import _token_scope

    # 静态表里 skills_list 是 user_only，契约字段为 dual → 契约优先
    meta = {"operationId": "skills_list",
            "op": {"x-token-scope": "dual"}}
    assert _token_scope(meta) == "dual"
    # 无字段 → 回落静态表
    meta2 = {"operationId": "skills_list", "op": {}}
    assert _token_scope(meta2) == "user_only"


def test_worker_mode_hides_user_only_in_commands(monkeypatch, fake_httpx, isolate_config):
    from click.testing import CliRunner
    from src.cli import cli

    monkeypatch.delenv("GRAPE_CLI_MODE", raising=False)
    monkeypatch.setenv("GRAPE_CLI_MODE", "WORKER")
    # 走 bundled（含 x-token-scope）
    fake_httpx({})
    res = CliRunner().invoke(cli, ["commands"])
    assert res.exit_code == 0
    assert "skills upload" not in res.output          # user_only 隐藏
    assert "git-repo branches" in res.output          # session_only 可见
    assert "tasks mine" in res.output                 # dual 可见


def test_user_mode_hides_session_only_in_commands(monkeypatch, fake_httpx, isolate_config):
    from click.testing import CliRunner
    from src.cli import cli

    monkeypatch.setenv("GRAPE_CLI_MODE", "USER")
    fake_httpx({})
    res = CliRunner().invoke(cli, ["commands"])
    assert res.exit_code == 0
    assert "git-repo branches" not in res.output      # session_only 隐藏
    assert "skills upload" in res.output              # user_only 可见
    assert "tasks mine" in res.output


def test_mode_guard_blocks_worker_user_only(monkeypatch, fake_httpx, isolate_config):
    from click.testing import CliRunner
    from src.cli import cli
    from src.client import CliError

    monkeypatch.setenv("GRAPE_CLI_MODE", "WORKER")
    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    monkeypatch.setenv("GRAPE_BASE_URL", "http://x")
    fake_httpx({})
    upload = cli.get_command(None, "skills").commands["upload"]
    res = CliRunner().invoke(upload, ["--file", "x.zip", "--agent_type", "qa"])
    assert isinstance(res.exception, CliError)
    assert "GRAPE_CLI_MODE=WORKER" in str(res.exception)
    assert "user_only" in str(res.exception)


def test_contents_raw_decodes_base64(monkeypatch, fake_httpx):
    """#3：contents --raw 解码单文件 base64 直出文本。"""
    import base64 as b64
    from click.testing import CliRunner
    from src.cli import cli

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    monkeypatch.setenv("GRAPE_BASE_URL", "http://x")
    content = "aGVsbG8="  # "hello"
    fake_httpx({"/api/git-repo/o/r/contents/README.md":
                (200, {"content": content, "encoding": "base64", "type": "file"})})
    contents = cli.get_command(None, "git-repo").commands["contents"]
    res = CliRunner().invoke(contents, ["--owner", "o", "--repo", "r",
                                        "--path", "README.md", "--raw"])
    assert res.exit_code == 0
    assert res.output == "hello\n"


def test_contents_raw_falls_back_to_json_for_dirs(monkeypatch, fake_httpx):
    from click.testing import CliRunner
    from src.cli import cli

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    monkeypatch.setenv("GRAPE_BASE_URL", "http://x")
    fake_httpx({"/api/git-repo/o/r/contents": (200, [{"type": "dir", "name": "x"}])})
    contents = cli.get_command(None, "git-repo").commands["contents"]
    res = CliRunner().invoke(contents, ["--owner", "o", "--repo", "r", "--raw"])
    assert res.exit_code == 0
    assert '"type": "dir"' in res.output


def test_command_help_marks_token_scope():
    """#2：user_only / session_only 命令帮助带作用域标识；allow 不带。"""
    from src.contracts import load_bundled

    g = build_groups(load_bundled())
    skills_list = g["skills"].commands["list"]
    assert "session 403 → grape_/JWT" in skills_list.help
    assert "Token scope: session (tk_) → 403" in skills_list.help

    branches = g["git-repo"].commands["branches"]
    assert "session-only" in branches.help
    assert "session (tk_) only" in branches.help

    mine = g["tasks"].commands["mine"]
    assert "session-only" not in mine.help
    assert "session 403" not in mine.help


def test_allowed_body_field_passes_to_request(monkeypatch, fake_httpx):
    from click.testing import CliRunner
    from src.cli import cli

    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_test")
    monkeypatch.setenv("GRAPE_BASE_URL", "http://x")
    calls = fake_httpx({"/api/git-repo/o/r/issues/7": (200, {"ok": True})})
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


def test_help_renders_required_marker_and_file_hint():
    """help 显示必填星号字段与 --json @file.json 引导（英文）。"""
    from src.contracts import load_bundled

    groups = build_groups(load_bundled())
    create = groups["git-repo"].commands["labels"].commands["create"]
    assert "name* (required string)" in create.help
    assert "Long JSON body hint: use --json @file.json" in create.help


def test_missing_required_request_field_rejected(monkeypatch, isolate_config):
    """schema.required 缺失 → 报缺少必填字段（而非网络请求）。"""
    import pytest
    from src.contracts import load_bundled
    from src.client import CliError
    from src.registry import _body_fields, _validate_body

    ops = parse_operations(load_bundled())
    meta = next(o for o in ops if o["operationId"] == "gitrepo_labels_create")
    bf = _body_fields(meta)
    # LabelCreateBody 契约 required=["name"]
    with pytest.raises(CliError) as ei:
        _validate_body(meta, {"color": "#d73a4a"}, bf)
    assert "missing required request field(s)" in str(ei.value)
    assert "name" in str(ei.value)


def test_unsupported_field_gives_actionable_hint():
    """pulls update 的 state 字段：能力位缺失 → 行动指引而非冷冰冰 unknown field。"""
    import pytest
    from src.contracts import load_bundled
    from src.client import CliError
    from src.registry import _body_fields, _validate_body

    ops = parse_operations(load_bundled())
    meta = next(o for o in ops if o["operationId"] == "gitrepo_pulls_update")
    bf = _body_fields(meta)
    with pytest.raises(CliError) as ei:
        _validate_body(meta, {"state": "closed"}, bf)
    assert "state" in str(ei.value)
    assert "not supported" in str(ei.value)


def test_en_summary_uses_contract_summary():
    """摘要直接用服务端契约 summary（英文单一事实源，无 overlay）。"""
    op = {"operationId": "custom_thing", "summary": "Do a custom thing"}
    assert _en_summary(op) == "Do a custom thing"
    assert _en_summary({}) == ""


def test_parse_skips_autogen_ugly_operation_ids():
    """解析契约时过滤 autogen 丑名（含 api_ 的内嵌路径），避免噪音组。"""
    schema = {
        "paths": {
            "/api/ok": {"get": {"operationId": "things_list", "summary": "ok"}},
            "/api/bad": {"get": {"operationId": "create_scene_api_scenes_bad_post",
                                 "summary": "bad"}},
        }
    }
    ops = parse_operations(schema)
    ids = [o["operationId"] for o in ops]
    assert "things_list" in ids
    assert "create_scene_api_scenes_bad_post" not in ids


def test_snapshot_summaries_all_english():
    """快照 summary/description 全英文（服务端单一事实源），防中文泄漏。"""
    from src.contracts import load_bundled

    bad = []
    for ms in load_bundled()["paths"].values():
        for o in ms.values():
            if not isinstance(o, dict):
                continue
            oid = o.get("operationId", "")
            for k in ("summary", "description"):
                v = o.get(k)
                if v and any(ord(ch) > 127 for ch in str(v)):
                    bad.append((oid, k))
    assert bad == [], f"快照仍有非英文 text: {bad}"


def test_worker_mode_group_summary_hides_user_only(monkeypatch):
    """WORKER：组摘要行不再列 user_only 动词（skills 全为 user_only → 摘要为空）；dual 保留。"""
    from src.contracts import load_bundled

    monkeypatch.setenv("GRAPE_CLI_MODE", "WORKER")
    skills = build_groups(load_bundled())["skills"].help
    assert "upload" not in skills.lower()
    tasks = build_groups(load_bundled())["tasks"].help
    assert "mine" in tasks  # tasks 为会话可用，保留


def test_all_mode_group_summary_keeps_all(monkeypatch):
    from src.contracts import load_bundled

    monkeypatch.setenv("GRAPE_CLI_MODE", "ALL")
    up_summary = ""
    for ms in load_bundled()["paths"].values():
        for o in ms.values():
            if isinstance(o, dict) and o.get("operationId") == "skills_upload":
                up_summary = o.get("summary", "")
                break
    skills = build_groups(load_bundled())["skills"].help
    assert up_summary in skills