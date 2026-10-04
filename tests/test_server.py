"""Unit tests for Collector REST API and HTTP Server."""
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

import sys
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))

from collector.database import Database
from collector.server import run_server


class ServerApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "server_test.db")
        self.db = Database(self.db_path)
        self.db.init_schema()

        # Seed test data
        self.db.insert_observation({
            "schema_version": 1,
            "node_id": "esp32-001",
            "timestamp": 1760000000,
            "radio": "ble",
            "address": "a8:e6:e8:d0:6b:74",
            "rssi": -80,
            "ssid": "WH-CH720N",
            "manufacturer": "Sony",
            "signature": "audio-peripheral",
            "confidence": 0.95,
            "connectable": True
        })

        # Start server on dynamic port
        self.port = 18080
        self.httpd = run_server(self.db, gateway_url="http://127.0.0.1:9999", port=self.port)
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        time.sleep(0.1)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.db.close()
        self.temp_dir.cleanup()

    def test_get_dashboard_index(self):
        url = f"http://127.0.0.1:{self.port}/"
        with urllib.request.urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("Fieldwatch Central Collector", content)

    def test_get_api_stats(self):
        url = f"http://127.0.0.1:{self.port}/api/stats"
        with urllib.request.urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["total_observations"], 1)
            self.assertEqual(data["total_devices"], 1)
            self.assertEqual(data["ble_devices"], 1)
            self.assertEqual(data["signatures"].get("audio-peripheral"), 1)

    def test_get_api_devices(self):
        url = f"http://127.0.0.1:{self.port}/api/devices?radio=ble"
        with urllib.request.urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["count"], 1)
            dev = data["devices"][0]
            self.assertEqual(dev["address"], "a8:e6:e8:d0:6b:74")
            self.assertEqual(dev["manufacturer"], "Sony")

    def test_get_api_device_history(self):
        url = f"http://127.0.0.1:{self.port}/api/device/a8:e6:e8:d0:6b:74/history"
        with urllib.request.urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["address"], "a8:e6:e8:d0:6b:74")
            self.assertEqual(len(data["history"]), 1)
            self.assertEqual(data["history"][0]["signature"], "audio-peripheral")


if __name__ == "__main__":
    unittest.main()
