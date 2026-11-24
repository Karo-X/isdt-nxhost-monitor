"""Serial, read-only polling of isdttool metrics."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time
from typing import Any

from .parser import FrameError, parse_isdttool_output
from .storage import HistoryStore


class MacOSNotifier:
    """Deliver a local Notification Center message without third-party tools."""

    def __init__(self, enabled: bool = True):
        self.enabled = bool(enabled)

    def __call__(self, title: str, message: str) -> None:
        if not self.enabled:
            return
        script = (
            f"display notification {json.dumps(message, ensure_ascii=False)} "
            f"with title {json.dumps(title, ensure_ascii=False)} sound name \"Glass\""
        )
        try:
            subprocess.run(
                ["/usr/bin/osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            # Notifications must never interrupt measurement collection.
            return


class IsdtToolRunner:
    """Invoke exactly the read-only metrics command requested by the project."""

    def __init__(self, configured_path: str, timeout_seconds: float = 10.0):
        expanded = Path(configured_path).expanduser()
        if expanded.is_file():
            self.executable = str(expanded)
        else:
            located = shutil.which(configured_path) or shutil.which("isdttool")
            self.executable = located or str(expanded)
        self.timeout_seconds = float(timeout_seconds)

    def read_metrics(self, channel: int) -> tuple[str, int]:
        if isinstance(channel, bool) or not isinstance(channel, int) or not 0 <= channel <= 255:
            raise ValueError("Kanal muss eine ganze Zahl zwischen 0 und 255 sein.")
        command = [
            self.executable,
            "-d",
            "--output",
            "json",
            "metrics",
            "--channel",
            str(channel),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        return output.strip(), completed.returncode


class DemoRunner:
    """Replay captured conversation frames without accessing USB hardware."""

    FRAMES = {
        4: "0224aa2120df040307011916630406d100be004901410019000000be01000000f09b0600004ef20613082f1c8200000000000000000000000000000000000000",
        5: "0224aa2120df050307011916639605de00fc00460146001c000000ce01000000f09306000038f20613082f1c8200000000000000000000000000000000000000",
        6: "0224aa2120df060307011916639005e100b3004b013d00180000009f01000000f0a4060000c7f20613082f1c8200000000000000000000000000000000000000",
        7: "0224aa2120df070307011916630106d800bd0055013d0017000000a101000000f0a706000049f20613082f1c8200000000000000000000000000000000000000",
    }
    EMPTY = "0224aa2120df0000000417160000000000000000000000000000000000000000f0a6060000edf20613082f1c8200000000000000000000000000000000000000"

    def read_metrics(self, channel: int) -> tuple[str, int]:
        frame = self.FRAMES.get(channel)
        if frame is None:
            raw = bytearray.fromhex(self.EMPTY)
            raw[6] = channel
            frame = raw.hex()
        return f"Demo-Modus (gespeicherter Frame)\nReading {frame}", 0


class SerialCollector:
    def __init__(
        self,
        runner: Any,
        store: HistoryStore,
        channels: list[int],
        poll_interval_seconds: float,
        notifier: Any | None = None,
        slot_labels: dict[str, str] | None = None,
    ):
        self.runner = runner
        self.store = store
        self.channels = channels
        self.poll_interval_seconds = max(1.0, float(poll_interval_seconds))
        self.notifier = notifier
        self.slot_labels = slot_labels or {}
        self._previous_code_7: dict[int, int] = {}
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._status: dict[str, Any] = {
            "running": False,
            "polling_channel": None,
            "cycles": 0,
            "last_cycle_finished_at": None,
        }

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._loop, name="isdt-poller", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def _set_status(self, **updates: Any) -> None:
        with self._lock:
            self._status.update(updates)

    def _loop(self) -> None:
        self._set_status(running=True)
        try:
            while not self.stop_event.is_set():
                cycle_started = time.monotonic()
                for channel in self.channels:
                    if self.stop_event.is_set():
                        break
                    self._set_status(polling_channel=channel)
                    self._poll_channel(channel)
                elapsed = time.monotonic() - cycle_started
                status = self.status()
                self._set_status(
                    polling_channel=None,
                    cycles=status["cycles"] + 1,
                    last_cycle_finished_at=datetime.now(timezone.utc).isoformat(),
                )
                self.stop_event.wait(max(0.0, self.poll_interval_seconds - elapsed))
        finally:
            self._set_status(running=False, polling_channel=None)

    def _poll_channel(self, channel: int) -> None:
        now = datetime.now(timezone.utc)
        sample: dict[str, Any] = {
            "observed_at": now.isoformat(),
            "epoch": now.timestamp(),
            "channel": channel,
            "raw_output": "",
            "error": None,
        }
        try:
            output, returncode = self.runner.read_metrics(channel)
            sample["raw_output"] = output
            metrics = parse_isdttool_output(output)
            sample.update(metrics.to_dict())
            self._handle_charge_completion(channel, metrics)
            if metrics.frame_channel != channel:
                sample["error"] = (
                    f"Antwort meldet Kanal {metrics.frame_channel}, abgefragt wurde {channel}."
                )
            if returncode:
                extra = f"isdttool endete mit Status {returncode}."
                sample["error"] = f"{sample['error']} {extra}" if sample["error"] else extra
        except subprocess.TimeoutExpired:
            sample["error"] = "Zeitüberschreitung bei isdttool."
        except FileNotFoundError:
            sample["error"] = f"isdttool nicht gefunden: {self.runner.executable}"
        except (FrameError, OSError, ValueError) as exc:
            sample["error"] = str(exc)
        self.store.add(sample)

    def _handle_charge_completion(self, channel: int, metrics: Any) -> None:
        """Notify once when an observed charge changes from active to complete.

        The condition is deliberately narrow and based on the jointly observed
        N-Series frames: byte 7 changes from active charge code 3 to completed
        charge code 4 and current falls to zero. Byte 12 is not part of this
        condition because completed cells exposed both raw codes 1 and 5.
        """
        previous_code_7 = self._previous_code_7.get(channel)
        self._previous_code_7[channel] = metrics.code_7_candidate
        complete = bool(
            metrics.battery_present_candidate
            and metrics.code_7_candidate == 4
            and metrics.current_ma_unverified == 0
        )
        if previous_code_7 != 3 or not complete or self.notifier is None:
            return

        slot = channel + 1
        manual = self.slot_labels.get(str(channel))
        name = f"Slot {slot}" + (f" ({manual})" if manual else "")
        self.notifier(
            "ISDT NXHOST · Akku geladen",
            f"{name} ist vollständig geladen – "
            f"{metrics.voltage_mv / 1000:.2f} V, "
            f"{metrics.temperature_c_candidate} °C.",
        )
