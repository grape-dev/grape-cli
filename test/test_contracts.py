"""契约加载：缓存命中 / refresh 强制重拉 / 版本选择 / 内置快照兜底。"""
import json

import pytest

from src import contracts
from src.client import CliError


def test_load_contract_caches_and_reuses(isolate_config, monkeypatch, sample_schema):
    calls = []

    def fake_fetch(base_url, token):
        calls.append(base_url)
        return sample_schema

    monkeypatch.setattr(contracts, "fetch_schema", fake_fetch)
    first = contracts.load_contract()
    second = contracts.load_contract()
    assert first["info"]["version"] == "0.0.1"
    assert second == first  # 内容一致且第二次命中缓存
    assert len(calls) == 1  # 第二次命中缓存
    assert (isolate_config / "openapi-0.0.1.json").exists()


def test_refresh_forces_refetch(isolate_config, monkeypatch, sample_schema):
    calls = []

    def fake_fetch(base_url, token):
        calls.append(base_url)
        return sample_schema

    monkeypatch.setattr(contracts, "fetch_schema", fake_fetch)
    contracts.load_contract()
    contracts.load_contract(refresh=True)
    assert len(calls) == 2


def test_read_cache_picks_highest_semantic_version(isolate_config):
    (isolate_config / "openapi-0.9.0.json").write_text(
        json.dumps({"info": {"version": "0.9.0"}}), encoding="utf-8")
    (isolate_config / "openapi-0.10.0.json").write_text(
        json.dumps({"info": {"version": "0.10.0"}}), encoding="utf-8")
    cached = contracts._read_cache()
    assert cached["info"]["version"] == "0.10.0"


def test_read_cache_falls_back_to_current_file(isolate_config):
    (isolate_config / "openapi-current.json").write_text(
        json.dumps({"info": {"version": "unknown"}}), encoding="utf-8")
    cached = contracts._read_cache()
    assert cached["info"]["version"] == "unknown"


def test_read_cache_prefers_versioned_over_current(isolate_config):
    (isolate_config / "openapi-current.json").write_text(
        json.dumps({"info": {"version": "unknown"}}), encoding="utf-8")
    (isolate_config / "openapi-0.5.0.json").write_text(
        json.dumps({"info": {"version": "0.5.0"}}), encoding="utf-8")
    cached = contracts._read_cache()
    assert cached["info"]["version"] == "0.5.0"


def test_load_bundled_returns_bundled_contract():
    bundled = contracts.load_bundled()
    assert bundled is not None
    assert "paths" in bundled
    assert "info" in bundled


def test_remote_failure_falls_back_to_bundled(isolate_config, monkeypatch):
    def _fail(base_url, token):
        raise CliError("HTTP 403: Forbidden", code=403)

    monkeypatch.setattr(contracts, "fetch_schema", _fail)
    schema = contracts.load_contract()
    assert "paths" in schema
    src_info = contracts.contract_source()
    assert src_info["kind"] == "bundled"
    assert "unreachable" in src_info["detail"]


def test_remote_success_prefers_remote_over_bundled(isolate_config, monkeypatch, sample_schema):
    def _ok(base_url, token):
        return sample_schema

    monkeypatch.setattr(contracts, "fetch_schema", _ok)
    schema = contracts.load_contract()
    assert schema == sample_schema
    assert contracts.contract_source()["kind"] == "remote"


def test_bundled_fallback_does_not_write_cache(isolate_config, monkeypatch):
    def _fail(base_url, token):
        raise CliError("HTTP 403: Forbidden", code=403)

    monkeypatch.setattr(contracts, "fetch_schema", _fail)
    contracts.load_contract()
    cached = [f for f in isolate_config.iterdir() if f.name.startswith("openapi-")]
    assert cached == []  # 快照只作兜底，不回写 ~/.grape 缓存，避免污染真实契约