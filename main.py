#!/usr/bin/env python3
"""Start the localhost-only ISDT NXHOST Battery Monitor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import threading
import webbrowser

from isdt_monitor.collector import DemoRunner, IsdtToolRunner, SerialCollector
from isdt_monitor.server import create_server
from isdt_monitor.storage import HistoryStore


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "config.json"


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    channels = config.get("channels", list(range(8)))
    if (
        not isinstance(channels, list)
        or not channels
        or len(channels) > 32
        or any(isinstance(item, bool) or not isinstance(item, int) or not 0 <= item <= 255 for item in channels)
        or len(set(channels)) != len(channels)
    ):
        raise ValueError("'channels' muss eine eindeutige Liste von 1–32 Kanälen (0–255) sein.")
    config["channels"] = channels
    labels = config.get("slot_labels", {})
    if not isinstance(labels, dict):
        raise ValueError("'slot_labels' muss ein Objekt mit Kanalnummern und Texten sein.")
    normalized_labels = {}
    for key, value in labels.items():
        try:
            channel = int(key)
        except (TypeError, ValueError) as exc:
            raise ValueError("Ungültige Kanalnummer in 'slot_labels'.") from exc
        if channel not in channels or not isinstance(value, str) or not value.strip() or len(value) > 80:
            raise ValueError("Slot-Bezeichnungen müssen zu konfigurierten Kanälen gehören und 1–80 Zeichen lang sein.")
        normalized_labels[str(channel)] = value.strip()
    config["slot_labels"] = normalized_labels
    config["poll_interval_seconds"] = max(
        1.0, float(config.get("poll_interval_seconds", 5.0))
    )
    config["command_timeout_seconds"] = max(
        1.0, float(config.get("command_timeout_seconds", 10.0))
    )
    config["max_history_per_slot"] = max(
        10, int(config.get("max_history_per_slot", 5000))
    )
    config["isdttool"] = str(config.get("isdttool", "~/isdt-env/bin/isdttool"))
    return config


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Gespeicherte Gesprächs-Frames statt echter Hardware wiedergeben.",
    )
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if not 1024 <= args.port <= 65535:
        raise SystemExit("Port muss zwischen 1024 und 65535 liegen.")
    try:
        config = load_config(args.config.expanduser().resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Konfiguration konnte nicht geladen werden: {exc}") from exc
    config["demo"] = bool(args.demo)

    store = HistoryStore(
        BASE_DIR / "data" / ("demo.sqlite3" if args.demo else "monitor.sqlite3"),
        config["max_history_per_slot"],
    )
    runner = (
        DemoRunner()
        if args.demo
        else IsdtToolRunner(config["isdttool"], config["command_timeout_seconds"])
    )
    collector = SerialCollector(
        runner, store, config["channels"], config["poll_interval_seconds"]
    )
    server = create_server(args.port, store, collector, config)
    url = f"http://127.0.0.1:{args.port}/"

    collector.start()
    print("ISDT NXHOST Battery Monitor")
    print(f"Lokale Oberfläche: {url}")
    print("Beenden: Ctrl+C")
    print("Hinweis: Reverse Engineering; mehrere Felder sind per Display abgeglichen,")
    print("Status und weitere Rohwerte bleiben experimentell. Nur metrics-Abfragen.")
    if args.demo:
        print("DEMO-MODUS: gespeicherte Frames, kein Hardwarezugriff.")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nMonitor wird beendet …")
    finally:
        server.shutdown()
        server.server_close()
        collector.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
