"""HTTP 客户端：三通道认证 + httpx 封装。"""
import base64

import httpx

from src import config


class CliError(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


class ApiClient:
    def __init__(self, base_url: str = "", token: str = "", channel: str = "bearer",
                 timeout: int = 0):
        self.base_url, self.token = config.resolve(base_url, token)
        self.channel = channel  # bearer / PRIVATE-TOKEN / access_token
        self.timeout = int(timeout or 0) or config.cli_timeout()
        if not self.token:
            raise CliError(
                "Missing token: set GRAPE_SESSION_TOKEN (task) / GRAPE_API_TOKEN (user), "
                "or the 'token' field in ~/.grape/config.json"
            )

    def _headers(self, extra: dict | None = None) -> dict:
        h = {"Accept": "application/json"}
        if self.channel == "bearer":
            h["Authorization"] = f"Bearer {self.token}"
        elif self.channel == "private-token":
            h["PRIVATE-TOKEN"] = self.token
        return h

    def request(self, method: str, path: str, *, params: dict | None = None,
                json_body: dict | None = None) -> tuple[int, dict]:
        url = self.base_url + path
        query = None
        if params:
            query = {k: v for k, v in params.items() if v not in (None, "", [])}
        if self.channel == "access_token":
            query = dict(query or {})
            query["access_token"] = self.token
        try:
            r = httpx.request(method.upper(), url, params=query or None,
                              headers=self._headers(), json=json_body or None,
                              timeout=self.timeout)
        except httpx.ConnectError as e:
            raise CliError(f"base_url unreachable: {self.base_url} ({e})")
        except httpx.TimeoutException as e:
            raise CliError(
                f"request timeout (> {self.timeout}s; increase with --timeout): "
                f"{self.base_url}{path}"
            )
        except httpx.HTTPError as e:
            raise CliError(f"HTTP error: {self.base_url}{path} ({e})")
        if r.status_code == 401:
            raise CliError("authentication failed: token invalid or expired", code=401)
        try:
            data = r.json()
        except Exception:
            data = r.text
        if r.status_code >= 400:
            msg = data.get("message") if isinstance(data, dict) else str(data)
            raise CliError(f"HTTP {r.status_code}: {msg or 'request failed'}", code=r.status_code)
        return r.status_code, data


def basic_auth(username: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()