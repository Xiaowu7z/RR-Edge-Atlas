from __future__ import annotations

import base64
import binascii
import csv
import io
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from email.message import Message
from typing import Callable, Iterable


MAX_SOURCE_BYTES = 1_048_576
MAX_DOMAINS = 5_000
SUBSCRIPTION_TIMEOUT_SECONDS = 12
_DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_JSON_DOMAIN_KEYS = ("domain", "host", "hostname", "address", "target", "content", "name")
_JSON_LIST_KEYS = ("domains", "hosts", "items", "data", "results", "entries")
_CSV_DOMAIN_HEADERS = {"domain", "host", "hostname", "address", "target", "域名", "主机名"}


class DomainSourceError(ValueError):
    """Raised when a custom domain source cannot be parsed safely."""


@dataclass
class DomainParseResult:
    domains: list[str]
    source_format: str
    ignored: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "domains": self.domains,
            "count": len(self.domains),
            "format": self.source_format,
            "ignored": self.ignored,
            "warnings": self.warnings,
        }


def normalize_domain(value: object) -> str:
    """Return a canonical ASCII hostname or raise ``DomainSourceError``."""
    raw = str(value or "").strip().strip("\"'`[](){}<>").rstrip(".")
    if not raw:
        raise DomainSourceError("域名为空")
    if raw.startswith("*."):
        raise DomainSourceError("不支持通配符域名")

    parsed_host = ""
    if "://" in raw:
        parsed = urllib.parse.urlsplit(raw)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise DomainSourceError("只接受域名或 HTTP/HTTPS 地址")
        parsed_host = parsed.hostname
    elif any(char in raw for char in "/?#"):
        parsed = urllib.parse.urlsplit("//" + raw)
        parsed_host = parsed.hostname or ""
    elif raw.count(":") == 1:
        host, port = raw.rsplit(":", 1)
        if port.isdigit():
            parsed_host = host
    raw = (parsed_host or raw).strip().rstrip(".").lower()

    try:
        ipaddress.ip_address(raw)
    except ValueError:
        pass
    else:
        raise DomainSourceError("IP 地址不是候选域名")

    try:
        ascii_name = raw.encode("idna").decode("ascii").lower()
    except (UnicodeError, UnicodeDecodeError) as exc:
        raise DomainSourceError("域名编码无效") from exc
    if len(ascii_name) > 253 or "." not in ascii_name:
        raise DomainSourceError("请输入完整域名")
    labels = ascii_name.split(".")
    if any(not _DOMAIN_LABEL.fullmatch(label) for label in labels):
        raise DomainSourceError("域名格式无效")
    return ascii_name


def normalize_domain_values(values: Iterable[object], maximum: int = MAX_DOMAINS) -> list[str]:
    domains: list[str] = []
    seen: set[str] = set()
    for value in values:
        domain = normalize_domain(value)
        if domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)
        if len(domains) > maximum:
            raise DomainSourceError(f"域名数量不能超过 {maximum} 个")
    if not domains:
        raise DomainSourceError("没有识别到有效域名")
    return domains


def _decode_source_bytes(payload: bytes) -> str:
    if len(payload) > MAX_SOURCE_BYTES:
        raise DomainSourceError("域名源文件不能超过 1 MiB")
    if b"\x00" in payload:
        raise DomainSourceError("检测到二进制内容，只支持文本域名源")
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DomainSourceError("文件编码无法识别，请使用 UTF-8 文本")


def _json_values(value: object) -> list[object]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        output: list[object] = []
        for item in value:
            if isinstance(item, str):
                output.append(item)
            elif isinstance(item, dict):
                output.extend(_json_values(item))
        return output
    if not isinstance(value, dict):
        return []
    output = []
    for key in _JSON_DOMAIN_KEYS:
        item = value.get(key)
        if isinstance(item, str):
            output.append(item)
    for key in _JSON_LIST_KEYS:
        if key in value:
            output.extend(_json_values(value[key]))
    return output


def _csv_values(text: str) -> tuple[list[object], str] | None:
    sample = text[:8192]
    if "\n" not in sample and not any(delimiter in sample for delimiter in (",", "\t", ";")):
        return None
    delimiter = "\t" if sample.count("\t") > max(sample.count(","), sample.count(";")) else ","
    if sample.count(";") > sample.count(delimiter):
        delimiter = ";"
    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    except csv.Error:
        return None
    if not rows or max((len(row) for row in rows), default=0) < 2:
        return None

    headers = [cell.strip().lower() for cell in rows[0]]
    header_index = next((index for index, header in enumerate(headers) if header in _CSV_DOMAIN_HEADERS), None)
    if header_index is not None:
        return ([row[header_index] for row in rows[1:] if len(row) > header_index], "TSV" if delimiter == "\t" else "CSV")
    return ([cell for row in rows for cell in row], "TSV" if delimiter == "\t" else "CSV")


def _plain_values(text: str) -> list[object]:
    values: list[object] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";", "//")):
            continue
        line = re.split(r"\s+#", line, maxsplit=1)[0]
        values.extend(token for token in re.split(r"[\s,;|]+", line) if token)
    return values


def _try_base64(text: str) -> str | None:
    compact = "".join(text.split())
    if len(compact) < 16 or len(compact) % 4 == 1 or "." in compact:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_+/=-]+", compact):
        return None
    padded = compact + "=" * (-len(compact) % 4)
    try:
        decoded = base64.b64decode(padded.replace("-", "+").replace("_", "/"), validate=True)
        return _decode_source_bytes(decoded)
    except (binascii.Error, DomainSourceError):
        return None


def parse_domain_source(text: str, filename: str = "", *, _allow_base64: bool = True) -> DomainParseResult:
    if not isinstance(text, str):
        raise DomainSourceError("域名源必须是文本")
    if len(text.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise DomainSourceError("域名源文件不能超过 1 MiB")
    if "\x00" in text:
        raise DomainSourceError("检测到二进制内容，只支持文本域名源")
    stripped = text.lstrip("\ufeff \t\r\n")
    if not stripped:
        raise DomainSourceError("域名源内容为空")

    source_format = "TXT"
    values: list[object]
    if stripped[:1] in {"[", "{"}:
        try:
            parsed_json = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise DomainSourceError(f"JSON 格式无效：第 {exc.lineno} 行") from exc
        values = _json_values(parsed_json)
        source_format = "JSON"
        if not values:
            raise DomainSourceError("JSON 中未找到 domains/host/domain 等受支持字段")
    else:
        decoded = _try_base64(stripped) if _allow_base64 else None
        if decoded is not None:
            inner = parse_domain_source(decoded, filename, _allow_base64=False)
            inner.source_format = f"Base64 + {inner.source_format}"
            return inner
        csv_result = _csv_values(stripped)
        if csv_result:
            values, source_format = csv_result
        else:
            values = _plain_values(stripped)
            suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
            if suffix in {"csv", "tsv", "json"}:
                source_format = f"TXT（内容与 .{suffix} 扩展名不一致）"

    domains: list[str] = []
    seen: set[str] = set()
    ignored = 0
    for value in values:
        try:
            domain = normalize_domain(value)
        except DomainSourceError:
            ignored += 1
            continue
        if domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)
        if len(domains) > MAX_DOMAINS:
            raise DomainSourceError(f"域名数量不能超过 {MAX_DOMAINS} 个")
    if not domains:
        raise DomainSourceError("没有识别到有效域名；支持 TXT、CSV、TSV、JSON 和 Base64 文本")
    warnings = [f"已忽略 {ignored} 个非域名字段"] if ignored else []
    return DomainParseResult(domains, source_format, ignored, warnings)


def _public_subscription_url(url: str, resolver: Callable[..., list[tuple]] = socket.getaddrinfo) -> str:
    try:
        parsed = urllib.parse.urlsplit(str(url).strip())
    except ValueError as exc:
        raise DomainSourceError("订阅链接格式无效") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise DomainSourceError("订阅链接只支持 HTTP/HTTPS")
    if parsed.username or parsed.password:
        raise DomainSourceError("订阅链接不能包含账号或密码")
    try:
        port = parsed.port
    except ValueError as exc:
        raise DomainSourceError("订阅链接端口无效") from exc
    if port not in {None, 80, 443}:
        raise DomainSourceError("订阅链接只允许 80 或 443 端口")
    try:
        rows = resolver(parsed.hostname, port or (443 if parsed.scheme.lower() == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise DomainSourceError("订阅域名解析失败") from exc
    addresses = {row[4][0].split("%", 1)[0] for row in rows}
    if not addresses:
        raise DomainSourceError("订阅域名没有可用地址")
    for address in addresses:
        try:
            parsed_address = ipaddress.ip_address(address)
        except ValueError as exc:
            raise DomainSourceError("订阅域名返回了无效地址") from exc
        if not parsed_address.is_global:
            raise DomainSourceError("订阅链接不能指向本机、内网或保留地址")
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, ""))


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, resolver: Callable[..., list[tuple]]) -> None:
        super().__init__()
        self.resolver = resolver

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        safe_url = _public_subscription_url(urllib.parse.urljoin(req.full_url, newurl), self.resolver)
        return super().redirect_request(req, fp, code, msg, headers, safe_url)


def fetch_domain_subscription(
    url: str,
    *,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
    opener: urllib.request.OpenerDirector | None = None,
) -> tuple[DomainParseResult, str]:
    safe_url = _public_subscription_url(url, resolver)
    client = opener or urllib.request.build_opener(_SafeRedirectHandler(resolver))
    request = urllib.request.Request(
        safe_url,
        headers={"Accept": "text/plain, application/json, text/csv, application/octet-stream", "User-Agent": "RR-Edge-Atlas/1.1"},
    )
    try:
        with client.open(request, timeout=SUBSCRIPTION_TIMEOUT_SECONDS) as response:
            content_type = str(response.headers.get_content_type()).lower()
            if content_type == "text/html":
                raise DomainSourceError("订阅链接返回了网页，不是域名列表")
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_SOURCE_BYTES:
                raise DomainSourceError("订阅内容不能超过 1 MiB")
            payload = response.read(MAX_SOURCE_BYTES + 1)
            final_url = _public_subscription_url(response.geturl(), resolver)
            disposition = response.headers.get("Content-Disposition", "")
    except DomainSourceError:
        raise
    except urllib.error.HTTPError as exc:
        raise DomainSourceError(f"订阅链接返回 HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise DomainSourceError(f"订阅下载失败：{getattr(exc, 'reason', exc)}") from exc
    text = _decode_source_bytes(payload)
    filename = "subscription"
    if disposition:
        message = Message()
        message["content-disposition"] = disposition
        filename = message.get_filename() or filename
    return parse_domain_source(text, filename), final_url


__all__ = [
    "DomainParseResult",
    "DomainSourceError",
    "MAX_DOMAINS",
    "MAX_SOURCE_BYTES",
    "fetch_domain_subscription",
    "normalize_domain",
    "normalize_domain_values",
    "parse_domain_source",
]
