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


class FakeRunner:
    def read_metrics(self, channel):
        return f"Writing 00\nReading {FRAME}\n[]", 0


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
        self.assertIn("Antwort meldet Kanal 4", saved["error"])
        self.assertIn("Reading", saved["raw_output"])

    def test_invalid_channel_never_starts_subprocess(self):
        with patch("isdt_monitor.collector.shutil.which", return_value=None):
            runner = IsdtToolRunner("/missing/isdttool")
        with patch("isdt_monitor.collector.subprocess.run") as run:
            with self.assertRaises(ValueError):
                runner.read_metrics(-1)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
