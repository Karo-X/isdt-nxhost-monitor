from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from isdt_monitor.collector import IsdtToolRunner, SerialCollector
from isdt_monitor.storage import HistoryStore


FRAME = (
    "0224aa2120df040307011916630406d100be004901410019000000be01000000"
    "f09b0600004ef20613082f1c8200000000000000000000000000000000000000"
)

COMPLETE_FRAME = (
    "0224aa2120df04040701191701e1050000a6000000de0054000000d005000000"
    "f09b06000085aca013082f1c8200000000000000000000000000000000000000"
)

COMPLETE_FRAME_CODE_5 = (
    "0224aa2120df070407011a1705dd050000b0000000d50052000000a105000000"
    "f09c0600005ab7a013082f1c8200000000000000000000000000000000000000"
)

ANALYSIS_DONE_FRAME = (
    "0224aa2120df040c0701191701e1050000a6000000de0040060000d005000000"
    "f09b06000085aca013082f1c8200000000000000000000000000000000000000"
)


class FakeRunner:
    def read_metrics(self, channel):
        return f"Writing 00\nReading {FRAME}\n[]", 0


class SequenceRunner:
    def __init__(self, frames):
        self.frames = iter(frames)

    def read_metrics(self, channel):
        return f"Reading {next(self.frames)}", 0


class CollectorTests(unittest.TestCase):
    def test_subprocess_is_fixed_read_only_metrics_command_without_shell(self):
        completed = subprocess.CompletedProcess([], 0, stdout="Reading " + FRAME, stderr="")
        with patch("isdt_monitor.collector.shutil.which", return_value=None):
            runner = IsdtToolRunner("/missing/isdttool", 7)
        with patch("isdt_monitor.collector.subprocess.run", return_value=completed) as run:
            output, code = runner.read_metrics(4)
        self.assertEqual(code, 0)
        self.assertIn("Reading", output)
        args, kwargs = run.call_args
        self.assertEqual(
            args[0],
            ["/missing/isdttool", "-d", "--output", "json", "metrics", "--channel", "4"],
        )
        self.assertNotIn("shell", kwargs)
        self.assertFalse(kwargs["check"])

    def test_poll_persists_decoded_values_and_channel_mismatch_warning(self):
        with tempfile.TemporaryDirectory() as folder:
            store = HistoryStore(Path(folder) / "history.sqlite3")
            collector = SerialCollector(FakeRunner(), store, [5], 5)
            collector._poll_channel(5)
            saved = store.latest()[0]
        self.assertEqual(saved["voltage_mv"], 1540)
        self.assertEqual(saved["temperature_c_candidate"], 25)
        self.assertEqual(saved["charge_percent_candidate"], 99)
        self.assertEqual(saved["capacity_mah_candidate"], 25)
        self.assertEqual(saved["unknown_offset19_u16"], 329)
        self.assertIn("Antwort meldet Kanal 4", saved["error"])
        self.assertIn("Reading", saved["raw_output"])

    def test_invalid_channel_never_starts_subprocess(self):
        with patch("isdt_monitor.collector.shutil.which", return_value=None):
            runner = IsdtToolRunner("/missing/isdttool")
        with patch("isdt_monitor.collector.subprocess.run") as run:
            with self.assertRaises(ValueError):
                runner.read_metrics(-1)
            run.assert_not_called()

    def test_existing_database_is_migrated_to_calibrated_columns(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.sqlite3"
            store = HistoryStore(path)
            with store._connect() as db:
                columns = {row[1] for row in db.execute("PRAGMA table_info(samples)")}
        self.assertIn("temperature_c_candidate", columns)
        self.assertIn("capacity_mah_candidate", columns)
        self.assertIn("unknown_offset19_u16", columns)
        self.assertIn("code_7_candidate", columns)
        self.assertIn("code_8_candidate", columns)

    def test_notifies_once_when_charging_changes_to_complete(self):
        notifications = []
        with tempfile.TemporaryDirectory() as folder:
            store = HistoryStore(Path(folder) / "history.sqlite3")
            collector = SerialCollector(
                SequenceRunner([FRAME, COMPLETE_FRAME, COMPLETE_FRAME]),
                store,
                [4],
                5,
                notifier=lambda title, message: notifications.append((title, message)),
                slot_labels={"4": "Eneloop"},
            )
            collector._poll_channel(4)
            collector._poll_channel(4)
            collector._poll_channel(4)

        self.assertEqual(len(notifications), 1)
        title, message = notifications[0]
        self.assertIn("Akku geladen", title)
        self.assertIn("Slot 5 (Eneloop)", message)
        self.assertIn("1.50 V", message)

    def test_does_not_notify_for_already_complete_cell_on_startup(self):
        notifications = []
        with tempfile.TemporaryDirectory() as folder:
            store = HistoryStore(Path(folder) / "history.sqlite3")
            collector = SerialCollector(
                SequenceRunner([COMPLETE_FRAME]),
                store,
                [4],
                5,
                notifier=lambda title, message: notifications.append((title, message)),
            )
            collector._poll_channel(4)
        self.assertEqual(notifications, [])

    def test_completion_notification_accepts_observed_raw_status_code_5(self):
        notifications = []
        with tempfile.TemporaryDirectory() as folder:
            store = HistoryStore(Path(folder) / "history.sqlite3")
            collector = SerialCollector(
                SequenceRunner([FRAME, COMPLETE_FRAME_CODE_5]),
                store,
                [4],
                5,
                notifier=lambda title, message: notifications.append((title, message)),
            )
            collector._poll_channel(4)
            collector._poll_channel(4)
        self.assertEqual(len(notifications), 1)

    def test_completed_analysis_capacity_is_persisted_separately(self):
        with tempfile.TemporaryDirectory() as folder:
            store = HistoryStore(Path(folder) / "history.sqlite3")
            collector = SerialCollector(SequenceRunner([ANALYSIS_DONE_FRAME]), store, [4], 5)
            collector._poll_channel(4)
            results = store.latest_analysis_results()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["channel"], 4)
        self.assertEqual(results[0]["measured_capacity_mah"], 1600)


if __name__ == "__main__":
    unittest.main()
