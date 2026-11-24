import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import urlopen

from isdt_monitor.server import create_server
from isdt_monitor.storage import HistoryStore


class DummyCollector:
    def status(self):
        return {"running": True, "polling_channel": None, "cycles": 0}


class ServerTests(unittest.TestCase):
    def test_server_binds_loopback_and_serves_api(self):
        with tempfile.TemporaryDirectory() as folder:
            store = HistoryStore(Path(folder) / "history.sqlite3")
            config = {
                "channels": list(range(8)),
                "poll_interval_seconds": 5,
                "design_capacity_mah": {"0": 2000},
                "demo": True,
            }
            server = create_server(0, store, DummyCollector(), config)
            self.assertEqual(server.server_address[0], "127.0.0.1")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(
                    f"http://127.0.0.1:{server.server_address[1]}/api/state",
                    timeout=2,
                ) as response:
                    payload = json.load(response)
                self.assertEqual(payload["config"]["channels"], list(range(8)))
                self.assertEqual(payload["config"]["design_capacity_mah"]["0"], 2000)
                self.assertEqual(payload["analysis_results"], [])
                self.assertIn("live mit dem Display abgeglichen", payload["experimental_notice"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
