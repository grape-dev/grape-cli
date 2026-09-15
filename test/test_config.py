"""配置解析：优先级 / 环境变量回退 / 保存。"""
import json

from src import config


def _no_base_env(monkeypatch):
    monkeypatch.delenv("GRAPE_BASE_URL", raising=False)
    monkeypatch.delenv("GRAPE_SERVER_URL", raising=False)


def test_default_base_url(monkeypatch, isolate_config):
    _no_base_env(monkeypatch)
    base, token = config.resolve()
    assert base == "http://localhost:8000"
    assert token == ""


def test_cli_params_beat_env_and_file(monkeypatch, isolate_config):
    file = isolate_config / "config.json"
    file.write_text(json.dumps({"base_url": "https://file.example", "token": "file_tk"}), encoding="utf-8")
    monkeypatch.setenv("GRAPE_BASE_URL", "https://env.example")
    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "env_tk")
    config.set_cli_params(base_url="https://cli.example", token="cli_tk")
    base, token = config.resolve()
    assert base == "https://cli.example"
    assert token == "cli_tk"


def test_env_beats_config_file(monkeypatch, isolate_config):
    file = isolate_config / "config.json"
    file.write_text(json.dumps({"base_url": "https://file.example", "token": "file_tk"}), encoding="utf-8")
    monkeypatch.setenv("GRAPE_BASE_URL", "https://env.example")
    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "env_tk")
    base, token = config.resolve()
    assert base == "https://env.example"
    assert token == "env_tk"


def test_grapeserver_url_fallback_for_base_url(monkeypatch, isolate_config):
    _no_base_env(monkeypatch)
    monkeypatch.setenv("GRAPE_SERVER_URL", "https://server.example")
    base, _ = config.resolve()
    assert base == "https://server.example"


def test_config_file_only_source(monkeypatch, isolate_config):
    _no_base_env(monkeypatch)
    file = isolate_config / "config.json"
    file.write_text(json.dumps({"base_url": "https://file.example", "token": "file_tk"}), encoding="utf-8")
    base, token = config.resolve()
    assert base == "https://file.example"
    assert token == "file_tk"


def test_save_config_writes_file(isolate_config):
    config.save_config("https://saved.example", token="saved_tk")
    data = json.loads((isolate_config / "config.json").read_text(encoding="utf-8"))
    assert data == {"base_url": "https://saved.example", "token": "saved_tk"}


def test_default_timeout_30_and_cli_override():
    assert config.cli_timeout() == 30
    config.set_cli_params(timeout=120)
    assert config.cli_timeout() == 120


def test_user_mode_prefers_api_token(monkeypatch, isolate_config):
    monkeypatch.setenv("GRAPE_CLI_MODE", "USER")
    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_1")
    monkeypatch.setenv("GRAPE_API_TOKEN", "grape_1")
    _, tok = config.resolve()
    assert tok == "grape_1"


def test_worker_all_mode_prefer_session_token(monkeypatch, isolate_config):
    monkeypatch.setenv("GRAPE_CLI_MODE", "WORKER")
    monkeypatch.setenv("GRAPE_SESSION_TOKEN", "tk_1")
    monkeypatch.setenv("GRAPE_API_TOKEN", "grape_1")
    _, tok = config.resolve()
    assert tok == "tk_1"