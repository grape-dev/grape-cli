"""契约加载：缓存命中 / refresh 强制重拉。"""
from src import contracts


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