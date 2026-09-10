"""HTTP 客户端：认证头 / token 缺失 / 错误映射。"""
import httpx
import pytest

from src.client import ApiClient, CliError


def test_missing_token_raises():
    with pytest.raises(CliError, match="token"):
        ApiClient(base_url="http://x")


def test_bearer_header_sent(monkeypatch, fake_httpx):
    calls = fake_httpx({"/api/x": (200, {"ok": True})})
    ApiClient(base_url="http://x", token="tk_1").request("GET", "/api/x")
    headers = calls[0][2]["headers"]
    assert headers["Authorization"] == "Bearer tk_1"


def test_private_token_header(monkeypatch, fake_httpx):
    calls = fake_httpx({"/api/x": (200, {})})
    ApiClient(base_url="http://x", token="secret", channel="private-token").request("GET", "/api/x")
    headers = calls[0][2]["headers"]
    assert headers["PRIVATE-TOKEN"] == "secret"


def test_access_token_goes_into_query(monkeypatch, fake_httpx):
    calls = fake_httpx({"/api/x": (200, {})})
    ApiClient(base_url="http://x", token="tk_1", channel="access_token").request("GET", "/api/x")
    assert calls[0][2]["params"]["access_token"] == "tk_1"


def test_timeout_default_30(monkeypatch, fake_httpx):
    calls = fake_httpx({"/api/x": (200, {})})
    ApiClient(base_url="http://x", token="t").request("GET", "/api/x")
    assert calls[0][2]["timeout"] == 30


def test_401_maps_to_clierror(monkeypatch, fake_httpx):
    fake_httpx({"/api/x": (401, {})})
    with pytest.raises(CliError) as e:
        ApiClient(base_url="http://x", token="t").request("GET", "/api/x")
    assert e.value.code == 401


def test_http_error_exposes_server_message(monkeypatch, fake_httpx):
    fake_httpx({"/api/x": (500, {"message": "boom"})})
    with pytest.raises(CliError) as e:
        ApiClient(base_url="http://x", token="t").request("GET", "/api/x")
    assert e.value.code == 500
    assert "boom" in str(e.value)


def test_connect_error_maps_to_clierror(monkeypatch, fake_httpx):
    def _conn_raises(method, url, kwargs):
        raise httpx.ConnectError("no route")

    fake_httpx({"/api/x": _conn_raises})
    with pytest.raises(CliError, match="unreachable"):
        ApiClient(base_url="http://x", token="t").request("GET", "/api/x")


def test_timeout_error_maps_to_clierror(monkeypatch, fake_httpx):
    def _timeout_raises(method, url, kwargs):
        raise httpx.TimeoutException("slow")

    fake_httpx({"/api/x": _timeout_raises})
    with pytest.raises(CliError, match="timeout"):
        ApiClient(base_url="http://x", token="t").request("GET", "/api/x")


def test_query_params_drop_empty_values(monkeypatch, fake_httpx):
    calls = fake_httpx({"/api/x": (200, {})})
    ApiClient(base_url="http://x", token="t").request(
        "GET", "/api/x", params={"a": "1", "b": None, "c": "", "d": []}
    )
    query = calls[0][2]["params"]
    assert query == {"a": "1"}