"""契约 → click 命令树（Issue-45 M4 方案 B：operationId 驱动命令生成）。

- operationId 首段 → 组名（`gitrepo_*` → `git-repo`），其余段 → 嵌套动词链。
  例：`tasks_mine` → `grape tasks mine`；`gitrepo_issues_list` → `grape git-repo issues list`。
- query/path 参数 → `--<name>`；requestBody → `--json '<body>'`；`--json-out` 机器可读输出。
- security 进契约 → 自动携带认证头（ApiClient 统一）。
- **新增 OpenAPI 接口 → 重建契约 → CLI 自动获得命令，零 CLI 源码改动**（R7）。
- 帮助语义：优先 `src/data/openapi.en.json` 的 operationId → 英文含义，回退契约 summary。
"""
import json
from importlib.resources import files

import click

from src.client import ApiClient, CliError

GROUP_ALIAS = {"gitrepo": "git-repo"}

# 组的固定引导行（首行=短帮助；帮助 agent 区分 demo 组语义）
_GROUP_INTRO = {
    "git-repo": (
        "Platform API by grape (gitcode / github / gitlab): branches, issues, "
        "PRs, comments, merge & review, checks. No extra token setup - "
        "use the grape session token."
    ),
}

_EN_SUMMARIES: dict = {}


def _load_en_summaries() -> dict:
    """惰性加载 operationId → 英文含义覆盖层（进程内缓存）。"""
    global _EN_SUMMARIES
    if not _EN_SUMMARIES:
        try:
            _EN_SUMMARIES = json.loads(
                files("src").joinpath("data", "openapi.en.json").read_text(encoding="utf-8")
            )
        except Exception:
            _EN_SUMMARIES = {}
    return _EN_SUMMARIES


def _en_summary(op: dict) -> str:
    """帮助用英文含义：英文覆盖层 > 契约 summary > 空。"""
    oid = op.get("operationId") or ""
    if oid:
        en = _load_en_summaries().get(oid)
        if en:
            return en
    return (op.get("summary") or "").strip()


def group_name(g: str) -> str:
    return GROUP_ALIAS.get(g, g)


def parse_operations(schema: dict) -> list[dict]:
    ops = []
    schemas = schema.get("components", {}).get("schemas", {})
    for path, methods in (schema.get("paths") or {}).items():
        for method, op in methods.items():
            if not isinstance(op, dict) or not op.get("operationId"):
                continue
            oid = op["operationId"]
            parts = oid.split("_")
            verb = parts[1:] or ["list"]
            ops.append({
                "operationId": oid,
                "method": method.upper(),
                "path": path,
                "group": group_name(parts[0]),
                "verb": verb,
                "op": op,
                "schemas": schemas,
            })
    return ops


def _params_by_in(op: dict, where: str) -> list[str]:
    return [p["name"] for p in (op.get("parameters") or []) if p.get("in") == where]


def _body_fields(meta: dict) -> list[str]:
    """解析 requestBody schema 的字段清单（$ref 解引用到 components）。"""
    op = meta["op"]
    content = ((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}
    sch = content.get("schema") or {}
    name = (sch.get("$ref") or "").rsplit("/", 1)[-1]
    schema = meta.get("schemas", {}).get(name, {}) if name else (sch or {})
    return sorted(schema.get("properties") or {})


_EXAMPLES: dict = {}


def _load_examples() -> dict:
    global _EXAMPLES
    if not _EXAMPLES:
        try:
            _EXAMPLES = json.loads(
                files("src").joinpath("data", "examples.json").read_text(encoding="utf-8")
            )
        except Exception:
            _EXAMPLES = {}
    return _EXAMPLES


def _example_args(meta: dict, path_params: list[str], query_params: list[str],
                  body_fields: list[str]) -> str:
    """命令示例参数：优先 examples.json，否则按路径参数/body 字段自动生成占位示例。"""
    ex = _load_examples().get(meta["operationId"])
    if ex:
        return ex
    parts = [f"--{n} <{n}>" for n in path_params]
    if body_fields:
        parts.append(f"--json '{{\"{body_fields[0]}\":\"...\"}}'")
    else:
        parts += [f"--{n} <{n}>" for n in query_params[:2]]
    return " ".join(parts)


def build_command(meta: dict) -> click.Command:
    op, method, path = meta["op"], meta["method"], meta["path"]
    path_params = _params_by_in(op, "path")
    query_params = _params_by_in(op, "query")
    has_body = "requestBody" in op

    options = [click.Option([f"--{n}"], default=None, help=f"parameter {n}") for n in path_params]
    options += [click.Option([f"--{n}"], default=None, help=f"parameter {n}") for n in query_params]
    if has_body:
        options.append(click.Option(["--json"], default=None, help="JSON string request body"))
    options.append(click.Option(["--json-out"], is_flag=True, help="machine-readable JSON output"))

    def _run(**kw):
        api = ApiClient()
        url = path
        for name in path_params:
            v = kw.get(name)
            if v is None:
                raise CliError(f"Missing required parameter --{name}")
            url = url.replace("{" + name + "}", str(v))
        params = {n: kw.get(n) for n in query_params if kw.get(n) is not None}
        body = None
        raw = kw.get("json")
        if has_body and raw:
            try:
                body = json.loads(raw)
            except Exception:
                raise CliError("--json is not a valid JSON string")
        _status, data = api.request(method, url, params=params, json_body=body)
        click.echo(json.dumps(data, ensure_ascii=False,
                              indent=None if kw.get("json_out") else 2))

    summary = _en_summary(op)
    desc = (op.get("description") or "").strip()
    # 描述仅保留 ASCII（契约描述多为中文，帮助统一英文）
    if desc and not desc.isascii():
        desc = ""
    has_body_flag = "yes" if has_body else "no"
    method_path = f"Invoke grape API: {method} {path}"
    # 首行=实际含义 + 方法与是否需要 body（短帮助/命令列表直接展示）
    first = f"{summary or f'{method} {path}'} ({method}, body: {has_body_flag})"
    help_lines = [first, "", method_path]
    body_fields = _body_fields(meta)
    if body_fields:
        help_lines.append(f"Body fields: {', '.join(body_fields)}")
    elif has_body:
        help_lines.append("Body fields: (free-form JSON)")
    example_args = _example_args(meta, path_params, query_params, body_fields)
    if example_args:
        command_line = f"grape {meta['group']} {' '.join(meta['verb'])} {example_args}"
        help_lines += ["", "Examples:", "  " + command_line]
    if desc and desc != summary:
        help_lines += ["", desc]
    help_text = "\n".join(help_lines)
    return click.Command(name="", callback=_run, params=options, help=help_text)


def build_groups(schema: dict) -> dict[str, click.Group]:
    """返回 {组名: click.Group}，嵌套动词链按段建子组。"""
    holder: dict = {}
    for meta in parse_operations(schema):
        _insert(holder, meta)

    groups = {}
    for gname, subtree in sorted(holder.items()):
        groups[gname] = _materialize(subtree, gname)
    return groups


def _insert(holder: dict, meta: dict):
    node = holder.setdefault(meta["group"], {})
    for seg in meta["verb"][:-1]:
        node = node.setdefault(seg, {})
    node[meta["verb"][-1]] = meta  # 叶子：命令


def _is_meta(v) -> bool:
    return isinstance(v, dict) and "operationId" in v


def _materialize(subtree: dict, name: str) -> click.Group:
    """按子命令摘要聚合出“实际含义”，作为组帮助首行（方便 agent 快速理解）。"""
    meaning = []
    for key, val in sorted(subtree.items()):
        if _is_meta(val):
            s = _en_summary(val["op"])
            meaning.append(f"{key}: {s}" if s else key)
        else:
            meaning.append(key)
    lines = []
    intro = _GROUP_INTRO.get(name)
    if intro:
        lines += [intro, ""]
    lines += [
        ", ".join(meaning),
        "",
        f"Contract-driven group under group '{name}' "
        "(auto-generated from the OpenAPI contract by operationId).",
    ]
    grp = click.Group(
        name=name,
        help="\n".join(lines),
        context_settings=dict(help_option_names=["-h", "--help"]),
    )
    for key, val in sorted(subtree.items()):
        if _is_meta(val):
            cmd = build_command(val)
            cmd.name = key
            grp.add_command(cmd, name=key)
        else:
            grp.add_command(_materialize(val, key), name=key)
    return grp


def command_tree(schema: dict) -> dict[str, list[str]]:
    """{组: [动词链]} 便于 --list / commands 展示。"""
    tree: dict[str, set] = {}
    for meta in parse_operations(schema):
        tree.setdefault(meta["group"], set()).add(meta["operationId"].split("_", 1)[1] or "list")
    return {g: sorted(v) for g, v in sorted(tree.items())}