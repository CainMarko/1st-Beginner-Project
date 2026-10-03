import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add pico-hub directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pico-hub"))

import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        # Create a unique temporary file for each test
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        self.filename = self.temp_file.name

    def tearDown(self):
        if os.path.exists(self.filename):
            try:
                os.remove(self.filename)
            except OSError:
                pass

    def test_initialize_empty_or_new(self):
        count = storage.initialize(filename=self.filename, max_cache=10)
        self.assertEqual(count, 0)
        self.assertEqual(storage.count_observations(), 0)
        self.assertEqual(storage.get_observations(), [])

    def test_save_and_retrieve_observations(self):
        storage.initialize(filename=self.filename, max_cache=10)

        obs1 = {"schema_version": 1, "node_id": "esp32-001", "timestamp": 100, "radio": "wifi", "rssi": -65}
        obs2 = {"schema_version": 1, "node_id": "esp32-002", "timestamp": 101, "radio": "ble", "rssi": -72}

        ok1, err1 = storage.save_observation(obs1)
        self.assertTrue(ok1)
        self.assertIsNone(err1)

        ok2, err2 = storage.save_observation(obs2)
        self.assertTrue(ok2)
        self.assertIsNone(err2)

        self.assertEqual(storage.count_observations(), 2)
        cached = storage.get_observations()
        self.assertEqual(len(cached), 2)
        self.assertEqual(cached[0]["node_id"], "esp32-001")
        self.assertEqual(cached[1]["node_id"], "esp32-002")

        # Verify physical file contents
        with open(self.filename, "r") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(len(lines), 2)

    def test_bounded_cache(self):
        # Cache bounded at 3 records
        storage.initialize(filename=self.filename, max_cache=3)

        for i in range(10):
            obs = {"schema_version": 1, "node_id": "node-%d" % i, "timestamp": i, "radio": "wifi"}
            storage.save_observation(obs)

        # Total count must be 10, but in-memory cache must only hold the 3 newest
        self.assertEqual(storage.count_observations(), 10)
        cached = storage.get_observations()
        self.assertEqual(len(cached), 3)
        self.assertEqual([item["node_id"] for item in cached], ["node-7", "node-8", "node-9"])

    def test_reboot_recovery(self):
        # Simulate storing observations in session 1
        storage.initialize(filename=self.filename, max_cache=5)
        for i in range(5):
            storage.save_observation({"schema_version": 1, "node_id": "n%d" % i, "timestamp": i, "radio": "wifi"})

        # Simulate reboot: re-initialize from same file
        recovered_count = storage.initialize(filename=self.filename, max_cache=5)
        self.assertEqual(recovered_count, 5)
        self.assertEqual(storage.count_observations(), 5)
        cached = storage.get_observations()
        self.assertEqual(len(cached), 5)
        self.assertEqual(cached[0]["node_id"], "n0")
        self.assertEqual(cached[4]["node_id"], "n4")

    def test_corruption_tolerance(self):
        # Write 2 valid lines, 1 corrupted line, and 1 more valid line
        with open(self.filename, "w") as f:
            f.write('{"schema_version":1,"node_id":"valid-1","timestamp":1,"radio":"wifi"}\n')
            f.write('{"CORRUPT_JSON_DATA_HERE!!!\n')  # malformed JSON
            f.write('\n')  # empty line
            f.write('{"schema_version":1,"node_id":"valid-2","timestamp":2,"radio":"wifi"}\n')

        # AC-10: Must not crash, should load only valid lines
        count = storage.initialize(filename=self.filename, max_cache=10)
        self.assertEqual(count, 2)
        cached = storage.get_observations()
        self.assertEqual(len(cached), 2)
        self.assertEqual([o["node_id"] for o in cached], ["valid-1", "valid-2"])


if __name__ == "__main__":
    unittest.main()
