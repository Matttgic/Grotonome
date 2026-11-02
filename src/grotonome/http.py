"""HTTP minimal. Les URL d'erreur sont expurgées des clés et jetons."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
    "Chrome/122.0.0.0 Mobile Safari/537.36 Grotonome/0.1"
)

_SECRET = re.compile(
    r"(apiKey|api_key|token|key|access_token)=([^&\s]+)",
    re.IGNORECASE,
)


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str, body: str = ""):
        self.status = status
        self.url = redact(url)
        snippet = body[:180].replace("\n", " ")
        super().__init__(f"HTTP {status} {self.url} {snippet}")


def redact(text: str) -> str:
    return _SECRET.sub(r"\1=***", text)


def request(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 25,
    method: str = "GET",
    data: bytes | None = None,
) -> tuple[int, bytes, float]:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.8"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read()
        elapsed = time.perf_counter() - started
        raise HttpError(exc.code, url, body.decode("utf-8", "replace")) from None
    except urllib.error.URLError as exc:
        raise HttpError(0, url, redact(str(exc.reason))) from None
    elapsed = time.perf_counter() - started
    return status, body, elapsed


def get_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 25) -> Any:
    _status, body, _elapsed = request(url, headers=headers, timeout=timeout)
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HttpError(200, url, "réponse non JSON") from exc


def get_text(url: str, *, headers: dict[str, str] | None = None, timeout: float = 20) -> str:
    _status, body, _elapsed = request(url, headers=headers, timeout=timeout)
    return body.decode("utf-8", "replace")
