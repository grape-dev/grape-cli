"""共享测试夹具与工具（grape-cli）。"""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAMPLE_SCHEMA = {
    "openapi": "3.0.3",
    "info": {"title": "grape", "version": "0.0.1"},
    "paths": {
        "/api/tasks/mine": {
            "get": {
                "operationId": "tasks_mine",
                "summary": "Mine tasks",
                "parameters": [
                    {"name": "status", "in": "query", "schema": {"type": "string"}}
                ],
            }
        },
        "/api/tasks": {
            "post": {
                "operationId": "tasks_create",
                "summary": "Create a task",
                "requestBody": {
                    "content": {"application/json": {"schema": {"type": "object"}}}
                },
            }
        },
        "/api/repos/{owner}/{repo}/issues": {
            "get": {
                "operationId": "gitrepo_issues_list",
                "summary": "List repo issues",
                "parameters": [
                    {"name": "owner", "in": "path", "schema": {"type": "string"}},
                    {"name": "repo", "in": "path", "schema": {"type": "string"}},
                    {"name": "state", "in": "query", "schema": {"type": "string"}},
                ],
            }
        },
        "/api/skills": {
            "get": {
                "operationId": "skills_list",
                "summary": "List skills",
            }
        },
    },
}


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        if json_data is None:
            json_data = {}
        self._json = json_data
        self.text = text

    def json(self):
        if isinstance(self._json, BaseException):
            raise self._json
        return self._json


@pytest.fixture(autouse=True)
def _reset_module_state():
    """每次用例前重置模块级可变状态，避免用例间串扰。"""
    from src import config
    from src import cli

    config._CLI_PARAMS = {"base_url": "", "token": "", "timeout": 0}
    cli.cli._loaded = False
    cli.cli._groups = {}
    cli.cli._load_error = ""
    yield
    config._CLI_PARAMS = {"base_url": "", "token": "", "timeout": 0}
    cli.cli._loaded = False
    cli.cli._groups = {}
    cli.cli._load_error = ""


@pytest.fixture
def isolate_config(tmp_path, monkeypatch):
    """把配置读写重定向到临时目录，隔离真实 ~/.grape。"""
    from src import config as cfg

    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.json")
    return tmp_path


@pytest.fixture
def sample_schema():
    return json.loads(json.dumps(SAMPLE_SCHEMA))


@pytest.fixture
def fake_httpx(monkeypatch):
    """用内存 router 替换 src.client.httpx.request，返回安装函数。

    router: dict[path_prefix → (status, data) | callable(method, url, kwargs)]
    未命中路径返回 404。
    """
    import src.client as client_mod

    def install(router):
        calls = []

        def _request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            path = urlsplit(url).path
            handler = router.get(path)
            if handler is None:
                return FakeResponse(404, {"message": "not found"})
            if callable(handler):
                return handler(method, url, kwargs)
            status, data = handler
            return FakeResponse(status, data)

        monkeypatch.setattr(client_mod.httpx, "request", _request)
        return calls

    return install