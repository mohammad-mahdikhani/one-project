"""HTTPS helper that works on Windows embeddable Python and slow shops."""

from __future__ import annotations

import http.client
import json
import ssl
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

CA_FILE = Path(__file__).resolve().parent / "certs" / "cacert.pem"


@dataclass
class HttpResult:
    status: int
    body: bytes
    headers: dict[str, str]


class HttpError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, body: bytes = b""):
        super().__init__(message)
        self.status = status
        self.body = body


def ssl_context(insecure: bool = False) -> ssl.SSLContext:
    if insecure:
        ctx = ssl._create_unverified_context()
        ctx.check_hostname = False
        return ctx
    ctx = ssl.create_default_context()
    if CA_FILE.is_file():
        ctx.load_verify_locations(cafile=str(CA_FILE))
    return ctx


def normalize_shop_url(value: str) -> str:
    text = (value or "").strip()
    for mark in ("\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u00a0"):
        text = text.replace(mark, "")
    text = text.strip().strip("/")
    if not text:
        return ""
    lower = text.lower()
    for junk in ("/wp-admin", "/wp-login.php", "/wp-json", "/?rest_route="):
        idx = lower.find(junk)
        if idx != -1:
            text = text[:idx]
            lower = text.lower()
    if not lower.startswith("http://") and not lower.startswith("https://"):
        text = "https://" + text
    if text.lower().startswith("http://"):
        text = "https://" + text[7:]
    return text.rstrip("/")


def _read_body(resp: http.client.HTTPResponse, limit: int = 2_000_000) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while size < limit:
        try:
            piece = resp.read(min(64 * 1024, limit - size))
        except (TimeoutError, OSError):
            break
        if not piece:
            break
        chunks.append(piece)
        size += len(piece)
    return b"".join(chunks)


def request_url(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 25,
    insecure: bool = False,
) -> HttpResult:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HttpError("آدرس سایت نامعتبر است")
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    hdrs = {
        "Host": parsed.hostname,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Encoding": "identity",
        "Connection": "close",
    }
    if headers:
        hdrs.update(headers)
    if body is not None:
        hdrs.setdefault("Content-Type", "application/json")
        hdrs["Content-Length"] = str(len(body))

    connector = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    kwargs: dict = {"timeout": timeout}
    if parsed.scheme == "https":
        kwargs["context"] = ssl_context(insecure)
    conn = connector(parsed.hostname, parsed.port, **kwargs)
    try:
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        raw = _read_body(resp)
        out_headers = {key.lower(): value for key, value in resp.getheaders()}
        return HttpResult(resp.status, raw, out_headers)
    except TimeoutError as exc:
        raise HttpError("سایت دیر جواب می‌دهد") from exc
    except ssl.SSLError as exc:
        raise HttpError("ssl") from exc
    except OSError as exc:
        raise HttpError(f"network:{exc}") from exc
    finally:
        try:
            conn.close()
        except OSError:
            pass


def request_json(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict | None = None,
    timeout: int = 25,
    insecure: bool = False,
) -> tuple[int, object, dict[str, str]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    result = request_url(url, method=method, headers=headers, body=body, timeout=timeout, insecure=insecure)
    data: object = {}
    if result.body:
        try:
            data = json.loads(result.body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            data = result.body.decode("utf-8", errors="replace")[:240]
    return result.status, data, result.headers
