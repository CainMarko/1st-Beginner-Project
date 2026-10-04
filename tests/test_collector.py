import os
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
import sys
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))

from collector.database import Database


class CollectorDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_fieldwatch.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_init_schema_creates_tables(self):
        self.db.init_schema()
        stats = self.db.get_stats()
        self.assertEqual(stats["total_observations"], 0)
        self.assertEqual(stats["total_devices"], 0)

    def test_insert_single_observation_and_device_rollup(self):
        self.db.init_schema()
        obs = {
            "schema_version": 1,
            "node_id": "esp32-001",
            "timestamp": 1760000000,
            "radio": "ble",
            "address": "a8:e6:e8:d0:6b:74",
            "rssi": -81,
            "channel": None,
            "ssid": "WH-CH720N",
            "manufacturer": "Sony",
            "signature": "audio-peripheral",
            "confidence": 0.95,
            "connectable": True
        }
        inserted = self.db.insert_observation(obs)
        self.assertTrue(inserted)

        stats = self.db.get_stats()
        self.assertEqual(stats["total_observations"], 1)
        self.assertEqual(stats["total_devices"], 1)

        devices = self.db.get_devices()
        self.assertEqual(len(devices), 1)
        dev = devices[0]
        self.assertEqual(dev["address"], "a8:e6:e8:d0:6b:74")
        self.assertEqual(dev["manufacturer"], "Sony")
        self.assertEqual(dev["signature"], "audio-peripheral")
        self.assertEqual(dev["sighting_count"], 1)
        self.assertEqual(dev["best_rssi"], -81)

    def test_duplicate_observations_ignored_in_observations_table(self):
        self.db.init_schema()
        obs = {
            "schema_version": 1,
            "node_id": "esp32-001",
            "timestamp": 1760000000,
            "radio": "ble",
            "address": "a8:e6:e8:d0:6b:74",
            "rssi": -81,
            "signature": "audio-peripheral",
            "confidence": 0.95
        }
        # First insert
        first = self.db.insert_observation(obs)
        self.assertTrue(first)

        # Second insert with identical (node_id, timestamp, address, radio)
        second = self.db.insert_observation(obs)
        self.assertFalse(second)

        # Verify observation count is 1, and device sighting_count is 1 (not phantom inflated)
        stats = self.db.get_stats()
        self.assertEqual(stats["total_observations"], 1)
        self.assertEqual(stats["total_devices"], 1)
        device = self.db.get_device("a8:e6:e8:d0:6b:74")
        self.assertEqual(device["sighting_count"], 1)

    def test_device_rollup_updates_on_new_timestamp(self):
        self.db.init_schema()
        # Sighting 1
        self.db.insert_observation({
            "schema_version": 1,
            "node_id": "esp32-001",
            "timestamp": 1760000010,
            "radio": "ble",
            "address": "a8:e6:e8:d0:6b:74",
            "rssi": -85,
            "signature": "unknown",
            "confidence": 0.0
        })

        # Sighting 2 with stronger RSSI and refined signature
        self.db.insert_observation({
            "schema_version": 1,
            "node_id": "esp32-001",
            "timestamp": 1760000020,
            "radio": "ble",
            "address": "a8:e6:e8:d0:6b:74",
            "rssi": -70,
            "manufacturer": "Sony",
            "signature": "audio-peripheral",
            "confidence": 0.95
        })

        device = self.db.get_device("a8:e6:e8:d0:6b:74")
        self.assertIsNotNone(device)
        self.assertEqual(device["sighting_count"], 2)
        self.assertEqual(device["best_rssi"], -70)
        self.assertEqual(device["last_rssi"], -70)
        self.assertEqual(device["first_seen"], 1760000010)
        self.assertEqual(device["last_seen"], 1760000020)
        self.assertEqual(device["signature"], "audio-peripheral")
        self.assertEqual(device["confidence"], 0.95)
        self.assertEqual(device["manufacturer"], "Sony")

    def test_batch_insert(self):
        self.db.init_schema()
        batch = [
            {
                "schema_version": 1,
                "node_id": "esp32-001",
                "timestamp": 1760000010,
                "radio": "wifi",
                "address": "aa:bb:cc:11:22:33",
                "rssi": -65,
                "ssid": "Test-AP",
                "signature": "router-ap",
                "confidence": 0.8
            },
            {
                "schema_version": 1,
                "node_id": "esp32-001",
                "timestamp": 1760000010,
                "radio": "ble",
                "address": "11:22:33:44:55:66",
                "rssi": -90,
                "signature": "smart-home",
                "confidence": 0.7
            },
            # Exact duplicate in same batch
            {
                "schema_version": 1,
                "node_id": "esp32-001",
                "timestamp": 1760000010,
                "radio": "wifi",
                "address": "aa:bb:cc:11:22:33",
                "rssi": -65,
                "ssid": "Test-AP",
                "signature": "router-ap",
                "confidence": 0.8
            }
        ]
        inserted = self.db.insert_batch(batch)
        self.assertEqual(inserted, 2)

        stats = self.db.get_stats()
        self.assertEqual(stats["total_observations"], 2)
        self.assertEqual(stats["total_devices"], 2)
        self.assertEqual(stats["wifi_devices"], 1)
        self.assertEqual(stats["ble_devices"], 1)


if __name__ == "__main__":
    unittest.main()
