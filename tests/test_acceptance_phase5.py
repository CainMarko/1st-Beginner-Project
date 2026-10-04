"""Phase 5 Acceptance Tests: Central Laptop Collector & SQLite Database.

Tests verify:
- AC-21: SQLite Ingestion Reliability (1,000 observations, WAL mode, transactional integrity)
- AC-22: Duplicate Handling Policy (re-sync cache drops duplicate packets, retains valid rollup)
- AC-23: Sub-Second Query Performance Benchmark (100,000 records, indexed queries < 1.0s)
"""
import os
import random
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))

from collector.database import Database
from collector.ingest import fetch_observations, sync_gateway


class Phase5AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "acceptance_fieldwatch.db")
        self.db = Database(self.db_path)
        self.db.init_schema()

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_ac21_sqlite_ingestion_reliability_and_wal_mode(self):
        """AC-21: Ingest 1,000 observations with >=99% reliability, WAL mode, transactional integrity."""
        # 1. Verify WAL mode
        cursor = self.db.conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        cursor.close()
        self.assertEqual(journal_mode.lower(), "wal", "Database must be operating in WAL mode")

        # 2. Generate 1,000 synthetic observations
        batch_size = 200
        total_records = 1000
        records = []
        base_ts = 1760000000
        for i in range(total_records):
            mac = f"aa:bb:cc:{(i // 256):02x}:{(i % 256):02x}:01"
            records.append({
                "schema_version": 1,
                "node_id": f"esp32-node-{(i % 3) + 1}",
                "timestamp": base_ts + i,
                "radio": "wifi" if i % 2 == 0 else "ble",
                "address": mac,
                "rssi": -40 - (i % 50),
                "channel": (i % 11) + 1 if i % 2 == 0 else None,
                "ssid": f"FieldAP-{(i % 10)}" if i % 2 == 0 else None,
                "manufacturer": "Espressif" if i % 2 == 0 else "Sony",
                "signature": "router-ap" if i % 2 == 0 else "audio-peripheral",
                "confidence": 0.85,
                "connectable": True if i % 2 != 0 else None
            })

        # Ingest in chunks
        total_inserted = 0
        for start in range(0, total_records, batch_size):
            chunk = records[start:start + batch_size]
            inserted = self.db.insert_batch(chunk)
            total_inserted += inserted

        # Assert 100% ingested (1,000 / 1,000 >= 99%)
        self.assertEqual(total_inserted, total_records)

        stats = self.db.get_stats()
        self.assertEqual(stats["total_observations"], 1000)
        self.assertGreater(stats["total_devices"], 0)
        self.assertGreater(stats["wifi_devices"], 0)
        self.assertGreater(stats["ble_devices"], 0)

    def test_ac22_duplicate_handling_policy(self):
        """AC-22: Re-syncing gateway cache safely ignores duplicate sighting packets and keeps rollups valid."""
        # Create 50 initial records
        cache_records = []
        base_ts = 1760001000
        for i in range(50):
            cache_records.append({
                "schema_version": 1,
                "node_id": "esp32-001",
                "timestamp": base_ts + i,
                "radio": "ble",
                "address": f"10:20:30:40:50:{i:02x}",
                "rssi": -75,
                "signature": "smart-home",
                "confidence": 0.75,
                "manufacturer": "Levoit",
                "connectable": True
            })

        # Mock gateway HTTP response
        with patch("collector.ingest.fetch_observations", return_value=cache_records):
            # Sync 1: All 50 are new
            fetched1, inserted1 = sync_gateway("http://192.168.1.152", self.db)
            self.assertEqual(fetched1, 50)
            self.assertEqual(inserted1, 50)

            stats1 = self.db.get_stats()
            self.assertEqual(stats1["total_observations"], 50)
            self.assertEqual(stats1["total_devices"], 50)

            dev = self.db.get_device("10:20:30:40:50:00")
            self.assertEqual(dev["sighting_count"], 1)

            # Sync 2: Re-sync exact same 50 records from gateway cache
            fetched2, inserted2 = sync_gateway("http://192.168.1.152", self.db)
            self.assertEqual(fetched2, 50)
            self.assertEqual(inserted2, 0, "Duplicate observations must result in 0 net new rows")

            # Verify devices stats remain valid and are not phantom inflated
            stats2 = self.db.get_stats()
            self.assertEqual(stats2["total_observations"], 50)
            self.assertEqual(stats2["total_devices"], 50)
            dev_after = self.db.get_device("10:20:30:40:50:00")
            self.assertEqual(dev_after["sighting_count"], 1)

            # Sync 3: Partial overlap (25 old, 25 new sightings of same devices at later timestamps)
            partial_records = cache_records[:25] + [
                {
                    "schema_version": 1,
                    "node_id": "esp32-001",
                    "timestamp": base_ts + 500 + i,
                    "radio": "ble",
                    "address": f"10:20:30:40:50:{i:02x}",
                    "rssi": -62,  # Stronger RSSI
                    "signature": "smart-home",
                    "confidence": 0.75,
                    "manufacturer": "Levoit",
                    "connectable": True
                }
                for i in range(25)
            ]

        with patch("collector.ingest.fetch_observations", return_value=partial_records):
            fetched3, inserted3 = sync_gateway("http://192.168.1.152", self.db)
            self.assertEqual(fetched3, 50)
            self.assertEqual(inserted3, 25, "Exactly 25 new observations should be inserted")

            stats3 = self.db.get_stats()
            self.assertEqual(stats3["total_observations"], 75)
            self.assertEqual(stats3["total_devices"], 50)

            # For device 0, sighting_count is now 2 and best_rssi is -62
            dev_updated = self.db.get_device("10:20:30:40:50:00")
            self.assertEqual(dev_updated["sighting_count"], 2)
            self.assertEqual(dev_updated["best_rssi"], -62)
            self.assertEqual(dev_updated["last_seen"], base_ts + 500)

    def test_ac23_subsecond_query_performance_100k_records(self):
        """AC-23: Sub-second query performance over 100,000 records (< 1.0s query latency)."""
        print("\n--- Running AC-23 Benchmark: Populating 100,000 records ---")
        total_records = 100000
        batch_size = 5000
        base_ts = 1760000000

        # Pre-generate 1000 distinct device addresses to simulate real-world repetition
        devices_pool = [
            (
                f"c0:ff:ee:{(i // 256):02x}:{(i % 256):02x}:01",
                "wifi" if i % 2 == 0 else "ble",
                "router-ap" if i % 2 == 0 else "audio-peripheral"
            )
            for i in range(1000)
        ]

        t0 = time.time()
        for batch_idx in range(total_records // batch_size):
            chunk = []
            for i in range(batch_size):
                global_idx = batch_idx * batch_size + i
                dev_meta = devices_pool[global_idx % len(devices_pool)]
                chunk.append({
                    "schema_version": 1,
                    "node_id": f"esp32-node-{(global_idx % 4) + 1}",
                    "timestamp": base_ts + global_idx,
                    "radio": dev_meta[1],
                    "address": dev_meta[0],
                    "rssi": -30 - (global_idx % 65),
                    "signature": dev_meta[2],
                    "confidence": 0.9,
                    "manufacturer": "BenchmarkCorp"
                })
            self.db.insert_batch(chunk)

        pop_elapsed = time.time() - t0
        print(f"100,000 records ingested in {pop_elapsed:.2f}s ({total_records / pop_elapsed:.0f} rec/s)")

        # Verify record count
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM observations;")
        count = cursor.fetchone()[0]
        self.assertEqual(count, total_records)

        # 1. Benchmark: Device history lookup (address index)
        target_addr = devices_pool[42][0]
        t_start = time.perf_counter()
        history = self.db.get_device_history(target_addr, limit=50)
        t_addr = time.perf_counter() - t_start
        print(f"Query 1 (Address history, 50 rows): {t_addr * 1000:.3f} ms (Target < 1000 ms)")
        self.assertLess(t_addr, 1.0, "Address query took longer than 1.0s")
        self.assertGreater(len(history), 0)

        # 2. Benchmark: Node history lookup (node_id index)
        t_start = time.perf_counter()
        cursor.execute("SELECT * FROM observations WHERE node_id = ? ORDER BY timestamp DESC LIMIT 50;", ("esp32-node-2",))
        node_rows = cursor.fetchall()
        t_node = time.perf_counter() - t_start
        print(f"Query 2 (Node history, 50 rows): {t_node * 1000:.3f} ms (Target < 1000 ms)")
        self.assertLess(t_node, 1.0, "Node query took longer than 1.0s")
        self.assertEqual(len(node_rows), 50)

        # 3. Benchmark: Signature archetype lookup (signature index)
        t_start = time.perf_counter()
        cursor.execute("SELECT * FROM observations WHERE signature = ? ORDER BY timestamp DESC LIMIT 50;", ("audio-peripheral",))
        sig_rows = cursor.fetchall()
        t_sig = time.perf_counter() - t_start
        print(f"Query 3 (Signature filter, 50 rows): {t_sig * 1000:.3f} ms (Target < 1000 ms)")
        self.assertLess(t_sig, 1.0, "Signature query took longer than 1.0s")
        self.assertEqual(len(sig_rows), 50)

        # 4. Benchmark: Radio filter lookup (radio index)
        t_start = time.perf_counter()
        cursor.execute("SELECT * FROM observations WHERE radio = ? ORDER BY timestamp DESC LIMIT 50;", ("ble",))
        radio_rows = cursor.fetchall()
        t_radio = time.perf_counter() - t_start
        print(f"Query 4 (Radio filter, 50 rows): {t_radio * 1000:.3f} ms (Target < 1000 ms)")
        self.assertLess(t_radio, 1.0, "Radio query took longer than 1.0s")
        self.assertEqual(len(radio_rows), 50)

        # 5. Benchmark: Devices table search with sorting
        t_start = time.perf_counter()
        devices = self.db.get_devices(limit=100)
        t_dev = time.perf_counter() - t_start
        print(f"Query 5 (Devices rollup, 100 rows): {t_dev * 1000:.3f} ms (Target < 1000 ms)")
        self.assertLess(t_dev, 1.0, "Devices rollup query took longer than 1.0s")
        self.assertEqual(len(devices), 100)

        cursor.close()


if __name__ == "__main__":
    unittest.main()
