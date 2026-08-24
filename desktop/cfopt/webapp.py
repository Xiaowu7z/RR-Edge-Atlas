from __future__ import annotations

import csv
import io
import json
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .history import load_history, save_history
from .models import MODES, OptimizerResult
from .pipeline import load_domains, run_optimizer


WEB_DIR = Path(__file__).resolve().parents[1] / "web"


@dataclass
class RuntimeState:
    lock: threading.RLock = field(default_factory=threading.RLock)
    status: str = "idle"
    stage: str = "等待开始"
    current: int = 0
    total: int = 0
    detail: str = ""
    logs: list[str] = field(default_factory=list)
    result: OptimizerResult | None = None
    error: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    worker: threading.Thread | None = None

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "status": self.status,
                "stage": self.stage,
                "current": self.current,
                "total": self.total,
                "detail": self.detail,
                "logs": self.logs[-220:],
                "result": self.result.to_dict() if self.result else None,
                "error": self.error,
                "config": self.config,
            }

    def on_stage(self, name: str, current: int, total: int, detail: str) -> None:
        with self.lock:
            self.stage = name
            self.current = current
            self.total = total
            self.detail = detail

    def log(self, message: str) -> None:
        with self.lock:
            self.logs.append(message)
            if len(self.logs) > 500:
                del self.logs[:-400]

    def start(self, config: dict[str, Any]) -> tuple[bool, str]:
        with self.lock:
            if self.status in {"running", "stopping"}:
                return False, "已有任务正在运行"
            self.status = "running"
            self.stage = "准备优选"
            self.current = 0
            self.total = 0
            self.detail = ""
            self.logs = []
            self.result = None
            self.error = ""
            self.config = config
            self.cancel_event = threading.Event()
            self.worker = threading.Thread(target=self._work, args=(config,), name="rr-optimizer", daemon=True)
            self.worker.start()
        return True, "优选已开始"

    def _work(self, config: dict[str, Any]) -> None:
        try:
            result = run_optimizer(
                mode=str(config.get("mode", "balanced")),
                family=str(config.get("family", "dual")),
                operator=str(config.get("operator", "自动")),
                limit=int(config.get("limit", 0)),
                cancel_event=self.cancel_event,
                on_stage=self.on_stage,
                log=self.log,
            )
            with self.lock:
                self.result = result
                self.status = "cancelled" if result.cancelled else "completed"
                self.stage = "已停止" if result.cancelled else "优选完成"
                self.detail = ""
            if not result.cancelled and result.families:
                try:
                    save_history(result.to_dict())
                except OSError as exc:
                    self.log(f"历史记录保存失败：{exc}")
        except Exception as exc:
            with self.lock:
                self.status = "error"
                self.stage = "发生错误"
                self.error = f"{type(exc).__name__}: {exc}"
            self.log(self.error)

    def stop(self) -> tuple[bool, str]:
        with self.lock:
            if self.status != "running":
                return False, "当前没有运行中的任务"
            self.status = "stopping"
            self.stage = "正在停止"
            self.cancel_event.set()
            return True, "停止信号已发送"


def _csv_bytes(result: OptimizerResult) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "family",
            "rank",
            "domain",
            "address_floor_mbps",
            "avg_complete_mbps",
            "min_complete_mbps",
            "success_rate_pct",
            "variation_pct",
            "median_ttfb_ms",
            "primary_pop",
            "best_ip",
            "worst_ip",
            "all_ips",
        ]
    )
    for family in result.families:
        rows = family.asia_ranked if result.mode == "asia" else family.ranked
        for index, item in enumerate(rows, 1):
            writer.writerow(
                [
                    family.family,
                    index,
                    item.domain,
                    f"{item.address_floor_mbps:.3f}",
                    f"{item.avg_complete_mbps:.3f}",
                    f"{item.min_complete_mbps:.3f}",
                    f"{item.success_rate_pct:.1f}",
                    f"{item.variation_pct:.1f}",
                    f"{item.median_ttfb_ms:.1f}",
                    item.primary_pop,
                    item.best_ip,
                    item.worst_ip,
                    " | ".join(item.current_ips),
                ]
            )
    return output.getvalue().encode("utf-8-sig")


def make_handler(state: RuntimeState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "RR-CF-Optimizer/0.1"

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _send(self, body: bytes, content_type: str, status: int = 200, headers: dict[str, str] | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, value: object, status: int = 200) -> None:
            self._send(json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

        def _body_json(self) -> dict[str, Any]:
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 64 * 1024)
                value = json.loads(self.rfile.read(length).decode("utf-8"))
                return value if isinstance(value, dict) else {}
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
                return {}

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/config":
                try:
                    domain_count = len(load_domains())
                except OSError:
                    domain_count = 0
                self._json(
                    {
                        "version": "1.0",
                        "domain_count": domain_count,
                        "modes": {
                            name: {
                                "label": mode.label,
                                "top_domains": mode.top_domains,
                                "final_domains": mode.final_domains,
                                "pre_bytes": mode.pre_bytes,
                                "micro_bytes": mode.micro_bytes,
                                "full_bytes": mode.full_bytes,
                            }
                            for name, mode in MODES.items()
                        },
                    }
                )
                return
            if parsed.path == "/api/status":
                self._json(state.snapshot())
                return
            if parsed.path == "/api/history":
                self._json(load_history())
                return
            if parsed.path == "/api/export":
                snapshot = state.snapshot()
                if not state.result:
                    self._json({"error": "暂无可导出的结果"}, HTTPStatus.NOT_FOUND)
                    return
                query = urllib.parse.parse_qs(parsed.query)
                export_format = query.get("format", ["json"])[0]
                if export_format == "csv":
                    body = _csv_bytes(state.result)
                    self._send(
                        body,
                        "text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="rr-cf-optimizer-result.csv"'},
                    )
                else:
                    body = json.dumps(snapshot["result"], ensure_ascii=False, indent=2).encode("utf-8")
                    self._send(
                        body,
                        "application/json; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="rr-cf-optimizer-result.json"'},
                    )
                return
            name = "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
            candidate = (WEB_DIR / name).resolve()
            try:
                candidate.relative_to(WEB_DIR.resolve())
            except ValueError:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if not candidate.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_types = {
                ".html": "text/html; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".svg": "image/svg+xml",
            }
            self._send(candidate.read_bytes(), content_types.get(candidate.suffix, "application/octet-stream"))

        def do_POST(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/start":
                body = self._body_json()
                mode = str(body.get("mode", "balanced"))
                family = str(body.get("family", "dual"))
                operator = str(body.get("operator", "自动"))[:30]
                try:
                    limit = max(0, min(1000, int(body.get("limit", 0))))
                except (TypeError, ValueError):
                    limit = 0
                if mode not in MODES or family not in {"ipv4", "ipv6", "dual"}:
                    self._json({"ok": False, "message": "参数无效"}, HTTPStatus.BAD_REQUEST)
                    return
                ok, message = state.start({"mode": mode, "family": family, "operator": operator, "limit": limit})
                self._json({"ok": ok, "message": message}, 200 if ok else HTTPStatus.CONFLICT)
                return
            if parsed.path == "/api/stop":
                ok, message = state.stop()
                self._json({"ok": ok, "message": message}, 200 if ok else HTTPStatus.CONFLICT)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

    return Handler


def serve(host: str = "127.0.0.1", port: int = 0, open_browser: bool = True) -> None:
    state = RuntimeState()
    server = ThreadingHTTPServer((host, port), make_handler(state))
    actual_port = server.server_address[1]
    url = f"http://{host}:{actual_port}/"
    print(f"RR 优选工具已启动：{url}")
    print("保持此窗口运行；按 Ctrl+C 退出。")
    if open_browser:
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        state.cancel_event.set()
        print("\n已退出。")
    finally:
        server.server_close()
