# Phase 4 BLE Sensor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Bluetooth Low Energy (BLE) advertisement discovery to the ESP32 field node, normalizing advertisements into Schema v1 observations (`radio: "ble"`) and delivering them alongside Wi-Fi scans to the Pico W edge gateway.

**Architecture:** Interleaved dual-radio scanning on ESP32: Wi-Fi passive scan followed by a 5-second BLE scan window. A lightweight MicroPython BLE IRQ callback enqueues raw events into an in-memory queue, which is then drained, parsed for Local Name and Manufacturer Data, deduplicated by MAC address, and buffered in `retry_queue` for HTTP transmission to the Pico W gateway.

**Tech Stack:** MicroPython v1.29 (`bluetooth.BLE`), Python 3.12 `unittest`, ESP32 (`COM11`), Raspberry Pi Pico W Gateway (`COM10` / `192.168.1.152`).

## Global Constraints

* Schema Version: All observations MUST use `schema_version = 1`.
* Radio Identifier: All BLE observations MUST have `radio == "ble"`.
* Channel Field: BLE observations MUST set `channel: None`.
* MicroPython IRQ Safety: The BLE IRQ handler (`_ble_irq`) MUST NOT perform string decoding, heap-heavy formatting, or network calls.
* Unit Test Compatibility: All scanner and parser logic MUST run under standard desktop Python (`py -3 -m unittest`) without requiring hardware hardware drivers.

---

### Task 1: BLE Observation Factory & Schema Tests

**Files:**
* Modify: `esp32_sensor/observation.py`
* Modify: `tests/test_esp32_sensor.py`

**Interfaces:**
* Consumes: `observation.format_bssid(address)`
* Produces: `observation.create_ble_observation(node_id, address, rssi=None, name="", manufacturer="", timestamp=0, signature="", latitude=None, longitude=None)`

- [ ] **Step 1: Write failing unit tests for `create_ble_observation`**

In `tests/test_esp32_sensor.py`, add tests verifying Schema v1 compliance, `radio == "ble"`, `channel is None`, address formatting, and optional field defaults.

```python
    def test_create_ble_observation_schema(self):
        obs = observation.create_ble_observation(
            node_id="esp32-001",
            address="AA:BB:CC:11:22:33",
            name="FitnessBand",
            rssi=-72,
            manufacturer="004c",
            timestamp=1760000500
        )
        self.assertEqual(obs["schema_version"], 1)
        self.assertEqual(obs["node_id"], "esp32-001")
        self.assertEqual(obs["timestamp"], 1760000500)
        self.assertEqual(obs["radio"], "ble")
        self.assertEqual(obs["address"], "aa:bb:cc:11:22:33")
        self.assertEqual(obs["rssi"], -72)
        self.assertIsNone(obs["channel"])
        self.assertEqual(obs["ssid"], "FitnessBand")
        self.assertEqual(obs["manufacturer"], "004c")
        self.assertEqual(obs["signature"], "")
        self.assertIsNone(obs["latitude"])
        self.assertIsNone(obs["longitude"])

    def test_create_ble_observation_defaults(self):
        obs = observation.create_ble_observation(
            node_id="esp32-001",
            address=b"\x01\x02\x03\x04\x05\x06"
        )
        self.assertEqual(obs["radio"], "ble")
        self.assertEqual(obs["address"], "01:02:03:04:05:06")
        self.assertEqual(obs["ssid"], "")
        self.assertEqual(obs["manufacturer"], "")
        self.assertIsNone(obs["rssi"])
        self.assertIsNone(obs["channel"])
        self.assertEqual(obs["timestamp"], 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m unittest tests/test_esp32_sensor.py -v`  
Expected: FAIL with `AttributeError: module 'observation' has no attribute 'create_ble_observation'`

- [ ] **Step 3: Implement `create_ble_observation` in `esp32_sensor/observation.py`**

Add the function to `esp32_sensor/observation.py`:

```python
def create_ble_observation(
    node_id,
    address,
    rssi=None,
    name="",
    manufacturer="",
    timestamp=0,
    signature="",
    latitude=None,
    longitude=None
):
    """Create a standardized BLE observation conforming to Schema v1."""
    return {
        "schema_version": 1,
        "node_id": str(node_id),
        "timestamp": int(timestamp) if timestamp is not None else 0,
        "radio": "ble",
        "address": format_bssid(address),
        "rssi": int(rssi) if rssi is not None else None,
        "channel": None,
        "ssid": str(name) if name is not None else "",
        "manufacturer": str(manufacturer) if manufacturer is not None else "",
        "signature": str(signature) if signature is not None else "",
        "latitude": latitude,
        "longitude": longitude
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m unittest tests/test_esp32_sensor.py -v`  
Expected: PASS (all tests pass)

---

### Task 2: Build `esp32_sensor/ble_scanner.py` & Parsing Unit Tests

**Files:**
* Create: `esp32_sensor/ble_scanner.py`
* Modify: `tests/test_esp32_sensor.py`

**Interfaces:**
* Consumes: `observation.create_ble_observation`, `observation.format_bssid`
* Produces: `decode_adv_payload(payload_bytes)`, `process_raw_events(raw_events, node_id, timestamp)`, `BLEScanner` class

- [ ] **Step 1: Write failing unit tests for payload decoding and event processing**

In `tests/test_esp32_sensor.py`, add tests for `decode_adv_payload` and `process_raw_events`:

```python
    def test_decode_adv_payload_name_and_mfg(self):
        import ble_scanner
        # AD 1: Flags (len 2, type 0x01, data 0x06)
        # AD 2: Complete Local Name (len 7, type 0x09, "Beacon")
        # AD 3: Manufacturer Data (len 5, type 0xFF, company 0x004c, data 0x02, 0x15)
        payload = (
            b"\x02\x01\x06"
            b"\x07\x09Beacon"
            b"\x05\xff\x4c\x00\x02\x15"
        )
        name, mfg = ble_scanner.decode_adv_payload(payload)
        self.assertEqual(name, "Beacon")
        self.assertEqual(mfg, "004c")

    def test_decode_adv_payload_malformed_and_empty(self):
        import ble_scanner
        self.assertEqual(ble_scanner.decode_adv_payload(b""), ("", ""))
        self.assertEqual(ble_scanner.decode_adv_payload(b"\x05"), ("", ""))

    def test_process_raw_events_deduplication(self):
        import ble_scanner
        raw_events = [
            (b"\xaa\xbb\xcc\x11\x22\x33", -80, b"\x05\x08Tag1"),
            (b"\xaa\xbb\xcc\x11\x22\x33", -65, b"\x05\x08Tag1"),  # Stronger RSSI
            (b"\x11\x22\x33\x44\x55\x66", -70, b"")
        ]
        obs_list = ble_scanner.process_raw_events(raw_events, node_id="esp32-001", timestamp=100)
        self.assertEqual(len(obs_list), 2)
        tag1_obs = [o for o in obs_list if o["address"] == "aa:bb:cc:11:22:33"][0]
        self.assertEqual(tag1_obs["rssi"], -65)
        self.assertEqual(tag1_obs["ssid"], "Tag1")
        self.assertEqual(tag1_obs["radio"], "ble")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m unittest tests/test_esp32_sensor.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'ble_scanner'`

- [ ] **Step 3: Implement `esp32_sensor/ble_scanner.py`**

Write `esp32_sensor/ble_scanner.py` with `decode_adv_payload`, `process_raw_events`, and the hardware `BLEScanner` class:

```python
"""BLE Scanner module for ESP32 Fieldwatch Sensing Node.

Performs passive and active Bluetooth Low Energy scanning, decouples IRQ event
capture via an in-memory event queue, and decodes advertisement payloads into
standard Schema v1 observations (AC-16, AC-17).
"""

import observation

try:
    import time
except ImportError:
    pass

try:
    import bluetooth
except ImportError:
    bluetooth = None

_IRQ_SCAN_RESULT = 5
_IRQ_SCAN_DONE = 6

_ADV_TYPE_NAME_SHORT = 0x08
_ADV_TYPE_NAME_COMPLETE = 0x09
_ADV_TYPE_MANUFACTURER_DATA = 0xFF


def decode_adv_payload(payload):
    """Decode BLE advertising data (L-T-V format) into (name, manufacturer_id_hex)."""
    if not payload:
        return "", ""

    name = ""
    mfg = ""
    idx = 0
    total_len = len(payload)

    while idx < total_len:
        length = payload[idx]
        if length == 0 or (idx + 1 + length) > total_len:
            break

        ad_type = payload[idx + 1]
        data = payload[idx + 2 : idx + 1 + length]

        if ad_type in (_ADV_TYPE_NAME_SHORT, _ADV_TYPE_NAME_COMPLETE):
            try:
                name = data.decode("utf-8", "replace")
            except Exception:
                pass
        elif ad_type == _ADV_TYPE_MANUFACTURER_DATA and len(data) >= 2:
            # 2-byte SIG Company ID is little-endian in BLE payloads
            mfg_id = data[0] | (data[1] << 8)
            mfg = "%04x" % mfg_id

        idx += 1 + length

    return name, mfg


def process_raw_events(raw_events, node_id, timestamp=0):
    """Drain raw BLE events and deduplicate by MAC address, keeping the strongest RSSI."""
    dedup = {}

    for addr_bytes, rssi, adv_payload in raw_events:
        addr_str = observation.format_bssid(addr_bytes)
        if not addr_str:
            continue

        if addr_str in dedup:
            if rssi > dedup[addr_str]["rssi"]:
                dedup[addr_str]["rssi"] = rssi
                if not dedup[addr_str]["name"] and adv_payload:
                    n, m = decode_adv_payload(adv_payload)
                    if n:
                        dedup[addr_str]["name"] = n
                    if m and not dedup[addr_str]["mfg"]:
                        dedup[addr_str]["mfg"] = m
        else:
            name, mfg = decode_adv_payload(adv_payload) if adv_payload else ("", "")
            dedup[addr_str] = {
                "address": addr_str,
                "rssi": rssi,
                "name": name,
                "mfg": mfg
            }

    observations = []
    for item in dedup.values():
        obs = observation.create_ble_observation(
            node_id=node_id,
            address=item["address"],
            rssi=item["rssi"],
            name=item["name"],
            manufacturer=item["mfg"],
            timestamp=timestamp
        )
        observations.append(obs)

    return observations


class BLEScanner:
    """Manages MicroPython bluetooth.BLE scanning lifecycle."""

    def __init__(self):
        self._ble = None
        self._raw_queue = []
        self._scan_done = False

    def _ble_irq(self, event, data):
        """MicroPython BLE interrupt handler. Keep allocations minimal!"""
        if event == _IRQ_SCAN_RESULT:
            # data: (addr_type, addr, adv_type, rssi, adv_data)
            addr = bytes(data[1])
            rssi = data[3]
            adv_data = bytes(data[4]) if data[4] else b""
            self._raw_queue.append((addr, rssi, adv_data))
        elif event == _IRQ_SCAN_DONE:
            self._scan_done = True

    def scan(self, duration_ms=5000, node_id="esp32-001", timestamp=0):
        """Execute a BLE scan window and return a list of Schema v1 observations."""
        if bluetooth is None:
            return []

        if self._ble is None:
            self._ble = bluetooth.BLE()

        if not self._ble.active():
            self._ble.active(True)

        self._ble.irq(self._ble_irq)
        self._raw_queue = []
        self._scan_done = False

        # interval 30ms, window 30ms (100% duty cycle), active=True (scan response)
        try:
            self._ble.gap_scan(duration_ms, 30000, 30000, True)
        except Exception as e:
            print("BLE scan error:", e)
            return []

        start_time = time.ticks_ms()
        # Wait for scan done event or timeout
        while not self._scan_done:
            if time.ticks_diff(time.ticks_ms(), start_time) > (duration_ms + 1000):
                try:
                    self._ble.gap_scan(None)  # Stop scan
                except Exception:
                    pass
                break
            time.sleep_ms(50)

        raw_events = self._raw_queue
        self._raw_queue = []

        try:
            self._ble.active(False)
        except Exception:
            pass

        return process_raw_events(raw_events, node_id, timestamp)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m unittest tests/test_esp32_sensor.py -v`  
Expected: PASS

---

### Task 3: Configuration & Main Sensor Loop Integration

**Files:**
* Modify: `esp32_sensor/config.py`
* Modify: `esp32_sensor/main.py`
* Modify: `tests/test_esp32_sensor.py`

**Interfaces:**
* Consumes: `ble_scanner.BLEScanner`, `config.BLE_SCAN_DURATION_MS`, `config.BLE_SCAN_ENABLED`
* Produces: Interleaved Wi-Fi and BLE execution cycle in `esp32_sensor/main.py`

- [ ] **Step 1: Add BLE configuration to `esp32_sensor/config.py`**

In `esp32_sensor/config.py`, add:
```python
# BLE Scanning configuration
BLE_SCAN_DURATION_MS = 5000
BLE_SCAN_ENABLED = True
```

- [ ] **Step 2: Update `esp32_sensor/main.py` to run interleaved scans**

Import `ble_scanner` and initialize a module-level `ble = ble_scanner.BLEScanner()`.
In `run_scan_cycle()`, after Wi-Fi scanning:
1. Print status: `"ESP32: Starting BLE scan (5s)..."`
2. If `config.BLE_SCAN_ENABLED`, run `ble_obs = ble.scan(config.BLE_SCAN_DURATION_MS, config.NODE_ID, timestamp)`.
3. Print status: `"ESP32: BLE scan complete. Found X devices."`
4. Buffer both Wi-Fi and BLE observations into `retry_queue`.
5. Post queued observations to the gateway.

- [ ] **Step 3: Run full automated test suite on PC**

Run: `py -3 -m unittest discover -s tests -v`  
Expected: PASS (All 17 tests pass cleanly)

---

### Task 4: Hardware Deployment & Live Verification (AC-16 & AC-17)

**Files:**
* Deploy to ESP32 (`COM11`): `observation.py`, `ble_scanner.py`, `config.py`, `main.py`
* Target Gateway: Raspberry Pi Pico W on `http://192.168.1.152`

- [ ] **Step 1: Upload updated modules to ESP32 via `mpremote`**

Command:
```powershell
py -3 -m mpremote connect COM11 fs cp esp32_sensor/observation.py :observation.py
py -3 -m mpremote connect COM11 fs cp esp32_sensor/ble_scanner.py :ble_scanner.py
py -3 -m mpremote connect COM11 fs cp esp32_sensor/config.py :config.py
py -3 -m mpremote connect COM11 fs cp esp32_sensor/main.py :main.py
```

- [ ] **Step 2: Trigger live scan cycle on ESP32**

Run one live cycle:
```powershell
py -3 -m mpremote connect COM11 exec "import main, network; wlan, ip = main.connect_wifi(); main.run_scan_cycle(wlan)"
```
Verify terminal output shows both Wi-Fi and BLE discovery counts:
```text
ESP32: Starting Wi-Fi scan...
ESP32: Scan complete. Found 36 networks.
ESP32: Starting BLE scan (5s)...
ESP32: BLE scan complete. Found X devices.
ESP32: Flushing observations to gateway...
ESP32: Delivered X observations. Remaining in queue: 0
```

- [ ] **Step 3: Validate observations at Pico W Gateway**

Query the Pico W gateway from PowerShell:
```powershell
$obs = Invoke-RestMethod -Uri "http://192.168.1.152/observations"
$obs | Where-Object { $_.radio -eq "ble" } | Select-Object -Last 5 address, ssid, manufacturer, rssi | Format-Table -AutoSize
```
Verify:
* At least one record has `radio: "ble"` (AC-16).
* All fields conform to Schema v1 with `channel: null` (AC-17).
