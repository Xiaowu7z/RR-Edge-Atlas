from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from .domain_sources import DomainSourceError, normalize_domain


API_BASE = "https://api.cloudflare.com/client/v4"
API_TIMEOUT_SECONDS = 15
MAX_API_RESPONSE_BYTES = 1_048_576
_ZONE_ID = re.compile(r"^[0-9a-fA-F]{32}$")
CloudflareTransport = Callable[[str, str, dict[str, object] | None], dict[str, object]]


class CloudflareError(RuntimeError):
    """A safe, user-facing Cloudflare API failure."""


@dataclass(frozen=True)
class CnameUpsertResult:
    operation: str
    zone_id: str
    record_id: str
    name: str
    target: str
    proxied: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "zone_id": self.zone_id,
            "record_id": self.record_id,
            "name": self.name,
            "target": self.target,
            "proxied": self.proxied,
            "ttl": 1,
        }


def _api_error_message(payload: object, status: int | None = None) -> str:
    messages: list[str] = []
    if isinstance(payload, dict):
        for item in payload.get("errors", []):
            if not isinstance(item, dict):
                continue
            code = item.get("code")
            message = str(item.get("message") or "").strip()
            if message:
                messages.append(f"{code}: {message}" if code is not None else message)
    if messages:
        return "；".join(messages[:3])
    return f"Cloudflare API 请求失败{f'（HTTP {status}）' if status else ''}"


class CloudflareClient:
    def __init__(self, api_token: str, transport: CloudflareTransport | None = None) -> None:
        token = str(api_token or "").strip()
        if not 20 <= len(token) <= 512 or any(char.isspace() for char in token):
            raise CloudflareError("API Token 格式无效")
        self._token = token
        self._transport = transport

    def request(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        if self._transport is not None:
            response = self._transport(method, path, payload)
            if not isinstance(response, dict):
                raise CloudflareError("Cloudflare API 返回格式无效")
            if response.get("success") is False:
                raise CloudflareError(_api_error_message(response))
            return response

        data = json.dumps(payload, separators=(",", ":")).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            API_BASE + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "RR-Edge-Atlas/1.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
                raw = response.read(MAX_API_RESPONSE_BYTES + 1)
                if len(raw) > MAX_API_RESPONSE_BYTES:
                    raise CloudflareError("Cloudflare API 返回内容过大")
                value = json.loads(raw.decode("utf-8"))
        except CloudflareError:
            raise
        except urllib.error.HTTPError as exc:
            try:
                value = json.loads(exc.read(MAX_API_RESPONSE_BYTES).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                value = {}
            raise CloudflareError(_api_error_message(value, exc.code)) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise CloudflareError(f"无法连接 Cloudflare API：{getattr(exc, 'reason', exc)}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CloudflareError("Cloudflare API 返回格式无效") from exc
        if not isinstance(value, dict):
            raise CloudflareError("Cloudflare API 返回格式无效")
        if value.get("success") is not True:
            raise CloudflareError(_api_error_message(value))
        return value


def _normalize_zone_id(value: object) -> str:
    zone_id = str(value or "").strip()
    if zone_id and not _ZONE_ID.fullmatch(zone_id):
        raise CloudflareError("Zone ID 应为 32 位十六进制字符串")
    return zone_id.lower()


def _resolve_zone(client: CloudflareClient, zone_id: str, zone_name: str) -> tuple[str, str]:
    normalized_id = _normalize_zone_id(zone_id)
    normalized_name = ""
    if zone_name:
        try:
            normalized_name = normalize_domain(zone_name)
        except DomainSourceError as exc:
            raise CloudflareError(f"区域域名无效：{exc}") from exc
    if normalized_id:
        return normalized_id, normalized_name
    if not normalized_name:
        raise CloudflareError("请填写 Zone ID 或区域域名")
    query = urllib.parse.urlencode({"name": normalized_name, "status": "active", "per_page": 2})
    response = client.request("GET", f"/zones?{query}")
    rows = response.get("result")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise CloudflareError("未找到唯一的活动区域；请改填 Zone ID，并确认 Token 已授予 Zone Read")
    resolved_id = str(rows[0].get("id") or "")
    return _normalize_zone_id(resolved_id), normalize_domain(rows[0].get("name") or normalized_name)


def _record_name(value: object, zone_name: str) -> str:
    raw = str(value or "").strip()
    if raw == "@":
        if not zone_name:
            raise CloudflareError("使用 @ 时必须同时填写区域域名")
        raw = zone_name
    elif "." not in raw and zone_name:
        raw = f"{raw}.{zone_name}"
    try:
        record = normalize_domain(raw)
    except DomainSourceError as exc:
        raise CloudflareError(f"记录名称无效：{exc}") from exc
    if zone_name and record != zone_name and not record.endswith("." + zone_name):
        raise CloudflareError("CNAME 记录名称不属于所填区域")
    return record


def upsert_cname(
    *,
    api_token: str,
    record_name: str,
    target: str,
    zone_id: str = "",
    zone_name: str = "",
    proxied: bool = False,
    transport: CloudflareTransport | None = None,
) -> CnameUpsertResult:
    client = CloudflareClient(api_token, transport)
    resolved_zone_id, resolved_zone_name = _resolve_zone(client, zone_id, zone_name)
    name = _record_name(record_name, resolved_zone_name)
    try:
        content = normalize_domain(target)
    except DomainSourceError as exc:
        raise CloudflareError(f"CNAME 目标无效：{exc}") from exc
    if name == content:
        raise CloudflareError("记录名称与 CNAME 目标不能相同，否则会形成解析循环")

    query = urllib.parse.urlencode({"name": name, "per_page": 100})
    response = client.request("GET", f"/zones/{resolved_zone_id}/dns_records?{query}")
    rows = response.get("result")
    if not isinstance(rows, list):
        raise CloudflareError("无法读取现有 DNS 记录")
    exact = [row for row in rows if isinstance(row, dict) and str(row.get("name", "")).lower().rstrip(".") == name]
    non_cname = [row for row in exact if str(row.get("type", "")).upper() != "CNAME"]
    if non_cname:
        record_types = ", ".join(sorted({str(row.get("type", "?")) for row in non_cname}))
        raise CloudflareError(f"同名记录已存在（{record_types}），请先在 Cloudflare 中处理冲突")
    cname_rows = [row for row in exact if str(row.get("type", "")).upper() == "CNAME"]
    if len(cname_rows) > 1:
        raise CloudflareError("检测到多个同名 CNAME，已停止以避免更新错误记录")

    payload: dict[str, object] = {
        "type": "CNAME",
        "name": name,
        "content": content,
        "ttl": 1,
        "proxied": bool(proxied),
    }
    if cname_rows:
        current = cname_rows[0]
        record_id = str(current.get("id") or "")
        if not _ZONE_ID.fullmatch(record_id):
            raise CloudflareError("现有 DNS 记录 ID 无效")
        unchanged = (
            str(current.get("content", "")).lower().rstrip(".") == content
            and bool(current.get("proxied")) is bool(proxied)
            and int(current.get("ttl") or 1) == 1
        )
        if unchanged:
            return CnameUpsertResult("unchanged", resolved_zone_id, record_id, name, content, bool(proxied))
        changed = client.request("PATCH", f"/zones/{resolved_zone_id}/dns_records/{record_id}", payload)
        operation = "updated"
    else:
        changed = client.request("POST", f"/zones/{resolved_zone_id}/dns_records", payload)
        operation = "created"

    result = changed.get("result")
    if not isinstance(result, dict):
        raise CloudflareError("Cloudflare API 未返回 DNS 记录")
    record_id = str(result.get("id") or "")
    if not _ZONE_ID.fullmatch(record_id):
        raise CloudflareError("Cloudflare API 返回的 DNS 记录 ID 无效")
    return CnameUpsertResult(operation, resolved_zone_id, record_id, name, content, bool(proxied))


__all__ = ["CnameUpsertResult", "CloudflareClient", "CloudflareError", "upsert_cname"]
