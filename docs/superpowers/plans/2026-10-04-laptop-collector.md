# Laptop Collector & SQLite Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a robust, central SQLite-backed observation collector (`collector/`) on the laptop with transactional ingestion, dual-table deduplication (AC-21, AC-22), sub-second indexed queries over 100,000+ records (AC-23), a background poller, a rich dark-mode local web dashboard (`http://localhost:8080`), and a PowerShell CLI.

**Architecture:** Standard Python 3 standard library application (no external third-party dependencies required). SQLite with WAL journal mode stores historical observations and aggregates an atomic device rollup table. An ingestion engine polls or syncs from the Pico W gateway HTTP API (`/observations`), validates records against Schema v1, and executes batch upserts. A stdlib `http.server` provides a REST API and serves a responsive single-page dashboard.

**Tech Stack:** Python 3.12 (`sqlite3`, `urllib.request`, `http.server`, `json`, `argparse`, `unittest`), HTML5/CSS3/Vanilla JS (for dashboard).

---

## Global Constraints

* Database Engine: Standard library `sqlite3` only.
* Durability (AC-21): Must achieve >= 99% ingestion rate across test batches and zero database corruption under WAL mode.
* Deduplication (AC-22): Identical re-synced packets must be ignored in `observations` via `UNIQUE(node_id, timestamp, address, radio)`, while `devices` aggregates repeat sightings.
* Performance (AC-23): Queries over 100,000 indexed rows must complete in < 1.0 second on development laptop.
* Zero External Dependencies: Must run with standard Python 3.12 without requiring `pip install`.
* Test Coverage: All components must be covered by automated tests in `tests/test_collector.py`.

---

### Task 1: Models & SQLite Database Engine (`collector/database.py`, `models.py`)

**Files:**
* Create: `collector/__init__.py`
* Create: `collector/models.py`
* Create: `collector/database.py`
* Create: `tests/test_collector.py`

**Interfaces:**
* Produces:
  * `collector.database.Database(db_path)`
  * `db.init_schema()`
  * `db.insert_observation(obs_dict) -> bool`
  * `db.insert_observations_batch(obs_list) -> (inserted, duplicates)`
  * `db.get_stats() -> dict`
  * `db.get_devices(limit=50, offset=0, signature=None, radio=None, search=None) -> list`
  * `db.get_device_history(address, limit=100) -> list`

- [ ] **Step 1: Write failing tests for Database schema, insertion, and stats in `tests/test_collector.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m unittest tests/test_collector.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'collector'`

- [ ] **Step 3: Implement `collector/__init__.py`, `collector/models.py`, and `collector/database.py`**

Implement connection handling, table creation, batch insertion with `ON CONFLICT IGNORE`, and device rollup upserts.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m unittest tests/test_collector.py -v`  
Expected: PASS

---

### Task 2: Ingestion Engine & Acceptance Tests (AC-21, AC-22, AC-23)

**Files:**
* Create: `collector/ingest.py`
* Modify: `tests/test_collector.py`

**Interfaces:**
* Produces:
  * `collector.ingest.fetch_from_gateway(host, port, path) -> list`
  * `collector.ingest.ingest_observations(db, observations) -> (fetched, inserted, skipped)`
  * `collector.ingest.SyncDaemon(db, host, port, interval_seconds)`

- [ ] **Step 1: Write failing tests for AC-21, AC-22, and AC-23 in `tests/test_collector.py`**

```python
    def test_ac21_sqlite_ingestion_1000_records(self):
        """AC-21: Ingest 1,000 valid observations with >=99% storage and zero corruption."""
        self.db.init_schema()
        batch = []
        for i in range(1000):
            batch.append({
                "schema_version": 1,
                "node_id": "esp32-001",
                "timestamp": 1760000000 + i,
                "radio": "ble" if i % 2 == 0 else "wifi",
                "address": f"00:11:22:33:{(i // 256):02x}:{(i % 256):02x}",
                "rssi": -40 - (i % 50),
                "channel": 6 if i % 2 != 0 else None,
                "ssid": f"Net-{i % 20}",
                "manufacturer": "Apple" if i % 2 == 0 else "Actiontec",
                "signature": "mobile-personal" if i % 2 == 0 else "router-ap",
                "confidence": 0.85
            })
        inserted, skipped = self.db.insert_observations_batch(batch)
        self.assertEqual(inserted, 1000)
        self.assertEqual(skipped, 0)
        stats = self.db.get_stats()
        self.assertEqual(stats["total_observations"], 1000)

    def test_ac22_deduplication_policy(self):
        """AC-22: Repeatedly submitting duplicate observations preserves history and rolls up device count."""
        self.db.init_schema()
        obs = {
            "schema_version": 1,
            "node_id": "esp32-001",
            "timestamp": 1760000000,
            "radio": "wifi",
            "address": "b8:f8:53:37:c7:08",
            "rssi": -45,
            "channel": 1,
            "ssid": "Fios-4ZxCR",
            "manufacturer": "Actiontec",
            "signature": "router-ap",
            "confidence": 0.95
        }
        # First ingest
        ins1, skip1 = self.db.insert_observations_batch([obs])
        self.assertEqual(ins1, 1)
        self.assertEqual(skip1, 0)

        # Re-sync same observation (identical timestamp & address)
        ins2, skip2 = self.db.insert_observations_batch([obs])
        self.assertEqual(ins2, 0)
        self.assertEqual(skip2, 1)
        self.assertEqual(self.db.get_stats()["total_observations"], 1)

        # Later sighting (new timestamp) -> increases observation count and device sighting_count
        obs_later = dict(obs, timestamp=1760000030, rssi=-42)
        ins3, skip3 = self.db.insert_observations_batch([obs_later])
        self.assertEqual(ins3, 1)
        self.assertEqual(self.db.get_stats()["total_observations"], 2)
        dev = self.db.get_devices()[0]
        self.assertEqual(dev["sighting_count"], 2)
        self.assertEqual(dev["best_rssi"], -42)

    def test_ac23_query_performance_100k_records(self):
        """AC-23: Sub-second queries over 100,000 observations."""
        import time
        self.db.init_schema()
        # Insert 100,000 records in fast chunks
        cursor = self.db.conn.cursor()
        cursor.execute("PRAGMA synchronous = OFF")
        cursor.execute("BEGIN TRANSACTION")
        now = 1760000000
        for i in range(100000):
            dev_idx = i % 5000
            addr = f"00:50:56:00:{(dev_idx // 256):02x}:{(dev_idx % 256):02x}"
            cursor.execute(
                "INSERT INTO observations (node_id, timestamp, radio, address, rssi, signature, confidence, ingested_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("esp32-001", now + i, "wifi", addr, -50 - (i % 40), "router-ap", 0.9, now)
            )
        cursor.execute("COMMIT")
        self.db.conn.commit()
        cursor.execute("PRAGMA synchronous = NORMAL")

        # Benchmark Query 1: By address
        t0 = time.time()
        res1 = self.db.get_device_history("00:50:56:00:01:00", limit=100)
        dt1 = time.time() - t0
        self.assertLess(dt1, 1.0, f"Query by address took {dt1:.4f}s (> 1.0s)")

        # Benchmark Query 2: By signature
        t0 = time.time()
        res2 = self.db.query_observations(signature="router-ap", limit=100)
        dt2 = time.time() - t0
        self.assertLess(dt2, 1.0, f"Query by signature took {dt2:.4f}s (> 1.0s)")

        # Benchmark Query 3: By node and timestamp range
        t0 = time.time()
        res3 = self.db.query_observations(node_id="esp32-001", start_ts=now + 50000, end_ts=now + 60000, limit=100)
        dt3 = time.time() - t0
        self.assertLess(dt3, 1.0, f"Query by node/timestamp took {dt3:.4f}s (> 1.0s)")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m unittest tests/test_collector.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement `collector/ingest.py` and query functions in `collector/database.py`**

Implement `ingest_observations()`, `query_observations()`, and `fetch_from_gateway()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m unittest tests/test_collector.py -v`  
Expected: PASS (All AC-21, AC-22, AC-23 tests pass in < 2 seconds)

---

### Task 3: Local Web Dashboard & REST API (`collector/server.py`, `collector/static/index.html`)

**Files:**
* Create: `collector/server.py`
* Create: `collector/static/index.html`
* Modify: `tests/test_collector.py`

**Interfaces:**
* Produces:
  * `create_server(db, host="0.0.0.0", port=8080) -> HTTPServer`
  * REST API: `/api/stats`, `/api/devices`, `/api/device/<addr>/history`, `/api/sync`
  * Web Dashboard: `GET /` serves responsive dark-mode HTML/CSS/JS

- [ ] **Step 1: Write unit tests for REST API endpoints**

In `tests/test_collector.py`, test that `/api/stats` and `/api/devices` return correct JSON payloads and status 200.

- [ ] **Step 2: Run test to verify failure**

Run: `py -3 -m unittest tests/test_collector.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement `collector/server.py` and `collector/static/index.html`**

Write standard library HTTP request handler with REST routing and embedded clean CSS/JS dashboard.

- [ ] **Step 4: Run test to verify pass**

Run: `py -3 -m unittest tests/test_collector.py -v`  
Expected: PASS

---

### Task 4: CLI Interface & Live Verification with Pico W Gateway

**Files:**
* Create: `collector/__main__.py`
* Modify: `tests/test_collector.py`
* Target: Live sync from Pico W Gateway (`http://192.168.1.152/observations`)

- [ ] **Step 1: Implement `collector/__main__.py`**

Supports:
* `sync`: One-shot pull from Pico W.
* `run`: Start poller + web dashboard.
* `stats`: Display summary table in terminal.
* `devices`: Display table of detected devices.
* `export`: Export observations or devices to CSV.

- [ ] **Step 2: Run full test suite on PC**

Run: `py -3 -m unittest discover -s tests -v`  
Expected: PASS (All tests pass)

- [ ] **Step 3: Perform live sync from Pico W Gateway**

Run: `py -3 -m collector sync`  
Verify: Ingests 50 records from gateway, creates `collector/fieldwatch.db`, populates `devices` and `observations`.

- [ ] **Step 4: Run `py -3 -m collector stats` and `py -3 -m collector devices`**

Verify terminal table output displays live enriched devices with signatures and confidence scores.

- [ ] **Step 5: Git commit and push to branch**

Stage, commit, and push changes to `cursor/phase4-ble-sensor` on private GitHub repository.
