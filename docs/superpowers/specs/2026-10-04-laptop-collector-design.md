# Design Specification: Phase 5 Laptop Collector & SQLite Database

**Date:** 2026-10-04  
**Status:** Approved  
**Target:** `collector/` on Laptop / Development Host, syncing from Pico W Gateway (`http://192.168.1.152/observations`)  
**PRD Milestones:** PRD Section 29 (Phase 5: Laptop Collector), Section 39.6 (AC-21: SQLite Ingestion, AC-22: Duplicate Handling, AC-23: Query Performance).

---

## 1. Overview & Objectives

Build a high-performance central collector service on the laptop that aggregates, deduplicates, and permanently archives observations collected by edge sensing nodes and buffered by the Pico W gateway.

* **AC-21 (SQLite Ingestion)**: Ingest observations with >=99% reliability, zero corruption across unexpected shutdowns, and full retention of `node_id`, `timestamp`, `radio`, `address`, `rssi`, `ssid`, `manufacturer`, `signature`, and `confidence`.
* **AC-22 (Deduplication Policy)**: Enforce a Dual-Table architecture:
  * `observations`: Historical time-series table deduplicating identical sync packets (`UNIQUE(node_id, timestamp, address, radio)`).
  * `devices`: Live rollup table aggregating unique hardware identities, tracking `first_seen`, `last_seen`, `sighting_count`, `best_rssi`, and latest metadata.
* **AC-23 (Sub-Second Query Performance)**: Maintain composite B-tree indexes guaranteeing that queries over 100,000+ observations return in less than 1.0 second on local hardware.
* **Dual Interface**: Provide both a PowerShell CLI (`py -3 -m collector`) and a zero-dependency local browser dashboard (`http://localhost:8080`) for live monitoring and search.

---

## 2. Directory Structure

```text
collector/
├── __init__.py
├── __main__.py      # Entrypoint for `py -3 -m collector` CLI
├── database.py      # SQLite connection, schema creation, indexed queries, upserts
├── ingest.py        # HTTP client polling Pico W, transaction management, sync daemon
├── models.py        # Observation & Device data classes and schema validation
├── server.py        # Lightweight stdlib HTTP server for local web dashboard & REST API
└── static/
    └── index.html   # Responsive dark-mode single-page dashboard
```

---

## 3. Database Schema (`collector/database.py`)

Database file: `collector/fieldwatch.db` (configured with `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`).

### 3.1 `observations` Table (Time-Series History)

```sql
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    radio TEXT NOT NULL,
    address TEXT NOT NULL,
    rssi INTEGER,
    channel INTEGER,
    ssid TEXT,
    manufacturer TEXT,
    signature TEXT,
    confidence REAL,
    connectable INTEGER,
    latitude REAL,
    longitude REAL,
    ingested_at INTEGER NOT NULL,
    UNIQUE(node_id, timestamp, address, radio) ON CONFLICT IGNORE
);

CREATE INDEX IF NOT EXISTS idx_obs_address_ts ON observations (address, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_obs_node_ts ON observations (node_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_obs_sig_ts ON observations (signature, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_obs_radio_ts ON observations (radio, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_obs_ts ON observations (timestamp DESC);
```

### 3.2 `devices` Table (Rollup Summary)

```sql
CREATE TABLE IF NOT EXISTS devices (
    address TEXT PRIMARY KEY,
    radio TEXT NOT NULL,
    manufacturer TEXT,
    signature TEXT,
    confidence REAL,
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    sighting_count INTEGER NOT NULL DEFAULT 1,
    best_rssi INTEGER,
    last_rssi INTEGER,
    last_ssid TEXT,
    last_channel INTEGER,
    is_connectable INTEGER
);

CREATE INDEX IF NOT EXISTS idx_dev_sig ON devices (signature);
CREATE INDEX IF NOT EXISTS idx_dev_last_seen ON devices (last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_dev_mfg ON devices (manufacturer);
```

---

## 4. Ingestion Engine & Deduplication Pipeline (`collector/ingest.py`)

### 4.1 Sync Pipeline
1. Fetch latest JSON observations from `http://192.168.1.152/observations`.
2. Validate each item against Schema v1 structure.
3. Open a single SQLite transaction (`BEGIN IMMEDIATE`):
   * Insert observation into `observations` (duplicate packets ignored via `ON CONFLICT IGNORE`).
   * For inserted observations, execute atomic upsert into `devices`:
     ```sql
     INSERT INTO devices (
         address, radio, manufacturer, signature, confidence,
         first_seen, last_seen, sighting_count, best_rssi,
         last_rssi, last_ssid, last_channel, is_connectable
     ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
     ON CONFLICT(address) DO UPDATE SET
         last_seen = excluded.last_seen,
         sighting_count = devices.sighting_count + 1,
         best_rssi = MAX(devices.best_rssi, excluded.best_rssi),
         last_rssi = excluded.last_rssi,
         last_ssid = CASE WHEN excluded.last_ssid != '' THEN excluded.last_ssid ELSE devices.last_ssid END,
         manufacturer = CASE WHEN excluded.manufacturer != 'unknown' THEN excluded.manufacturer ELSE devices.manufacturer END,
         signature = CASE WHEN excluded.signature != 'unknown' THEN excluded.signature ELSE devices.signature END,
         confidence = MAX(devices.confidence, excluded.confidence),
         is_connectable = COALESCE(excluded.is_connectable, devices.is_connectable);
     ```
4. Commit transaction and return ingestion metrics: `(total_fetched, new_inserted, duplicates_skipped)`.

### 4.2 Background Polling Daemon
* Runs on a configurable interval (default: 30 seconds).
* Tolerates gateway downtime or laptop sleep/wake events with automatic backoff and reconnection.

---

## 5. Web Dashboard & REST API (`collector/server.py`)

Local HTTP server listening on `http://localhost:8080`:
* **UI**: Clean, dark-mode single-page HTML/CSS/JS interface.
  * Real-time metrics cards: Total Sightings, Unique Devices, Wi-Fi APs, BLE Peripherals, Active Gateways.
  * Filterable table of devices with live search by MAC, SSID, Manufacturer, and Signature archetype.
  * Modal/expander showing sighting history & RSSI timeline for any selected device.
* **REST Endpoints**:
  * `GET /api/stats`: Aggregate counters & signature archetype breakdown.
  * `GET /api/devices`: Paginated list of devices with query parameters (`radio`, `signature`, `search`, `limit`, `offset`).
  * `GET /api/device/<address>/history`: Historical time-series sightings for a specific device.
  * `POST /api/sync`: Manually trigger gateway sync from the browser.

---

## 6. CLI Command Line Interface (`collector/__main__.py`)

* `py -3 -m collector sync`: Trigger single sync from Pico W gateway and print result.
* `py -3 -m collector run [--port 8080] [--interval 30]`: Launch background polling daemon + web dashboard.
* `py -3 -m collector stats`: Print database metrics in the terminal.
* `py -3 -m collector devices [--signature <sig>] [--limit 25]`: Print formatted table of devices.
* `py -3 -m collector export [--output data.csv] [--table devices|observations]`: Export to CSV.

---

## 7. Acceptance Criteria Verification

* **AC-21 (SQLite Ingestion)**: Ingest 1,000 observations; assert >=990 (99%) stored without error or corruption.
* **AC-22 (Duplicate Handling)**: Resubmit identical 1,000 observations; assert `observations` table count remains exactly 1,000 while `devices` table increments `sighting_count` or maintains integrity.
* **AC-23 (Query Benchmark over 100,000 Records)**: Populate database with 100,000 synthetic observations across 5,000 devices. Measure query latencies for lookups by node, address, timestamp range, and signature. Assert all queries execute in < 1.0 second.
