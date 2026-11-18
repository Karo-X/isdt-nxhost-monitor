"""Localhost-only HTTP server for the NXHOST monitor."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .storage import HistoryStore


WEB_DIR = Path(__file__).with_name("web")
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


def make_handler(store: HistoryStore, collector: Any, config: dict[str, Any]):
    class MonitorHandler(BaseHTTPRequestHandler):
        server_version = "NXHOSTMonitor/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in STATIC_FILES:
                filename, content_type = STATIC_FILES[parsed.path]
                self._send_bytes((WEB_DIR / filename).read_bytes(), content_type)
                return
            if parsed.path == "/api/state":
                self._send_json(
                    {
                        "collector": collector.status(),
                        "config": {
                            "channels": config["channels"],
                            "slot_labels": config.get("slot_labels", {}),
                            "poll_interval_seconds": config["poll_interval_seconds"],
                            "notifications_enabled": config.get("notifications_enabled", True),
                            "demo": config.get("demo", False),
                        },
                        "latest": store.latest(),
                        "recent": store.recent(80),
                        "experimental_notice": (
                            "Reverse Engineering: Temperatur, Spannung, Widerstand und "
                            "Kapazität wurden live mit dem Display abgeglichen. "
                            "Momentanstrom, Status und weitere Rohwerte bleiben experimentell."
                        ),
                    }
                )
                return
            if parsed.path == "/api/history":
                query = parse_qs(parsed.query)
                try:
                    channel = int(query.get("channel", [config["channels"][0]])[0])
                    limit = int(query.get("limit", [500])[0])
                except (TypeError, ValueError):
                    self._send_json({"error": "Ungültiger channel- oder limit-Wert."}, 400)
                    return
                if channel not in config["channels"]:
                    self._send_json({"error": "Kanal ist nicht konfiguriert."}, 400)
                    return
                self._send_json({"channel": channel, "samples": store.history(channel, limit)})
                return
            if parsed.path == "/api/export.csv":
                body = store.csv_text().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="isdt-history.csv"')
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            self._send_json({"error": "Nicht gefunden."}, 404)

        def _send_json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send_bytes(body, "application/json; charset=utf-8", status)

        def _send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return MonitorHandler


def create_server(
    port: int, store: HistoryStore, collector: Any, config: dict[str, Any]
) -> ThreadingHTTPServer:
    # Deliberately fixed to loopback; this project never binds to the LAN.
    return ThreadingHTTPServer(
        ("127.0.0.1", port), make_handler(store, collector, config)
    )
