#!/usr/bin/env python3
"""macOS USB watcher and LaunchAgent installer for the local NXHOST monitor."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import plistlib
import signal
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


LABEL = "de.karox.isdt-nxhost-monitor"
USB_NAME = "ISDTNX"
USB_VENDOR_ID = 10473  # 0x28E9
USB_PRODUCT_ID = 650  # 0x028A
MONITOR_URL = "http://127.0.0.1:8765/"
STATE_URL = f"{MONITOR_URL}api/state"
IOREG = "/usr/sbin/ioreg"
OPEN = "/usr/bin/open"
LAUNCHCTL = "/bin/launchctl"


def usb_signature_matches(output: str) -> bool:
    """Return true only for the observed ISDT N-Series USB identity."""
    return all(
        marker in output
        for marker in (
            f'"USB Product Name" = "{USB_NAME}"',
            f'"idVendor" = {USB_VENDOR_ID}',
            f'"idProduct" = {USB_PRODUCT_ID}',
        )
    )


def device_connected() -> bool:
    try:
        result = subprocess.run(
            [IOREG, "-p", "IOUSB", "-n", USB_NAME, "-r", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and usb_signature_matches(result.stdout)


def server_running() -> bool:
    try:
        with urlopen(STATE_URL, timeout=1) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def wait_for_server(timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server_running():
            return True
        time.sleep(0.25)
    return False


def stop_child(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def watch(project_dir: Path, poll_seconds: float = 2.0) -> int:
    """Open the dashboard once per USB connection and manage our own server."""
    owned_monitor: subprocess.Popen[bytes] | None = None
    opened_for_connection = False
    stopping = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    try:
        while not stopping:
            connected = device_connected()
            if connected and not opened_for_connection:
                if not server_running():
                    owned_monitor = subprocess.Popen(
                        [sys.executable, str(project_dir / "main.py")],
                        cwd=project_dir,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                if wait_for_server():
                    subprocess.Popen(
                        [OPEN, MONITOR_URL],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    opened_for_connection = True
            elif not connected:
                if opened_for_connection:
                    stop_child(owned_monitor)
                    owned_monitor = None
                opened_for_connection = False

            if owned_monitor is not None and owned_monitor.poll() is not None:
                owned_monitor = None
            time.sleep(max(0.5, poll_seconds))
    finally:
        stop_child(owned_monitor)
    return 0


def launch_agent_payload(project_dir: Path, python_path: Path) -> dict[str, object]:
    data_dir = project_dir / "data"
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(python_path),
            str(project_dir / "usb_autostart.py"),
            "--watch",
        ],
        "WorkingDirectory": str(project_dir),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "StandardOutPath": str(data_dir / "usb-autostart.log"),
        "StandardErrorPath": str(data_dir / "usb-autostart-error.log"),
    }


def agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def launch_domain() -> str:
    return f"gui/{os.getuid()}"


def install(project_dir: Path) -> int:
    python_path = Path.home() / "isdt-env" / "bin" / "python"
    if not python_path.is_file():
        print(f"Python-Umgebung nicht gefunden: {python_path}", file=sys.stderr)
        return 1

    project_dir = project_dir.resolve()
    (project_dir / "data").mkdir(exist_ok=True)
    path = agent_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [LAUNCHCTL, "bootout", launch_domain(), str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    temporary = path.with_suffix(".plist.tmp")
    with temporary.open("wb") as handle:
        plistlib.dump(launch_agent_payload(project_dir, python_path), handle)
    temporary.replace(path)
    result = subprocess.run(
        [LAUNCHCTL, "bootstrap", launch_domain(), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        print(result.stderr.strip() or "LaunchAgent konnte nicht gestartet werden.", file=sys.stderr)
        return result.returncode
    print("USB-Autostart ist aktiv.")
    print(f"Erkannt wird {USB_NAME} ({USB_VENDOR_ID:04X}:{USB_PRODUCT_ID:04X}).")
    return 0


def uninstall() -> int:
    path = agent_path()
    subprocess.run(
        [LAUNCHCTL, "bootout", launch_domain(), str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    path.unlink(missing_ok=True)
    print("USB-Autostart ist entfernt.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--watch", action="store_true")
    action.add_argument("--install", action="store_true")
    action.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    project_dir = Path(__file__).resolve().parent
    if args.install:
        return install(project_dir)
    if args.uninstall:
        return uninstall()
    return watch(project_dir)


if __name__ == "__main__":
    raise SystemExit(main())
