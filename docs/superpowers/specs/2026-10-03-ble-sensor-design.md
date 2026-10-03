# Design Specification: Phase 4 BLE Sensor Node Subsystem

**Date:** 2026-10-03  
**Status:** Approved  
**Targets:** `esp32_sensor/` on ESP32 (`COM11`), forwarding to Pico W Gateway (`pico-hub/` on `192.168.1.152:80`)  
**PRD Milestones:** PRD Section 10 (Objective 5: Add BLE Observation), Section 27 (Phase 3: ESP32 BLE Scanner), AC-16 (BLE Discovery), AC-17 (BLE Observation Schema).

---

## 1. Overview & Objectives

Extend the ESP32 field sensing node from Wi-Fi-only monitoring to dual-radio (Wi-Fi + BLE) scanning.

* **AC-16 (BLE Discovery)**: Discover BLE advertising devices (smartphones, fitness trackers, smart home peripherals) in the local RF space, extracting MAC address, RSSI, and timestamp.
* **AC-17 (BLE Observation Schema)**: Normalize all BLE detections into the standardized Schema v1 JSON format with `radio: "ble"`.
* **IRQ Safety**: Isolate time-critical MicroPython BLE interrupt callbacks (`irq`) from computationally heavy JSON/string operations using a dedicated in-memory event queue.
* **Window Deduplication**: Aggregate multiple advertisements from the same physical device observed during a single 5-second scan window, recording the strongest RSSI reading.
* **Store-and-Forward Interleaving**: Interleave Wi-Fi passive scanning and active BLE scanning within the main loop, batching observations and transmitting them cleanly to the Pico W edge gateway.

---

## 2. Architecture & Queue Pipeline

The ESP32 radio switches between Wi-Fi and Bluetooth. To avoid blocking the lwIP network stack or causing MicroPython MemoryErrors inside interrupt contexts, the BLE subsystem follows this decoupled pipeline:

```text
       ┌──────────────────────┐
       │ MicroPython BLE Radio│
       └──────────┬───────────┘
                  │  (asynchronous events)
                  ▼
       ┌──────────────────────┐
       │   _ble_irq Callback  │
       └──────────┬───────────┘
                  │  Minimal copy: (bytes(addr), rssi, bytes(adv_data))
                  ▼
       ┌──────────────────────┐
       │   Raw Event Queue    │  _raw_event_queue: list
       └──────────┬───────────┘
                  │  (drain queue after gap_scan finishes)
                  ▼
       ┌──────────────────────┐
       │ Advertisement Parser │  Extract: Local Name (0x08, 0x09),
       └──────────┬───────────┘           Company ID (0xFF)
                  │
                  ▼
       ┌──────────────────────┐
       │  Window Deduplicator │  Map address -> observation
       └──────────┬───────────┘  Retain maximum RSSI per MAC
                  │
                  ▼
       ┌──────────────────────┐
       │ Standardized Schema  │  List of dicts (radio="ble", channel=None)
       └──────────┬───────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │ ESP32 retry_queue    │  Delivered to Pico W via POST /observation
       └──────────────────────┘
```

---

## 3. Component Specifications

### 3.1 `esp32_sensor/observation.py`
Add `create_ble_observation()` to complement `create_wifi_observation()`:
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

### 3.2 `esp32_sensor/ble_scanner.py`
New module managing MicroPython `bluetooth.BLE` lifecycle and advertisement decoding:

* **Constants**:
  * `_IRQ_SCAN_RESULT = 5`
  * `_IRQ_SCAN_DONE = 6`
  * `ADV_TYPE_NAME_SHORT = 0x08`
  * `ADV_TYPE_NAME_COMPLETE = 0x09`
  * `ADV_TYPE_MANUFACTURER_DATA = 0xFF`
* **`decode_adv_payload(payload_bytes)`**:
  * Safely traverses L-T-V (Length-Type-Value) structures.
  * Extracts UTF-8 device name if type is `0x08` or `0x09`.
  * Extracts 2-byte company ID (formatted as 4-character lowercase hex string, e.g. `"004c"`) if type is `0xFF`.
* **`BLEScanner` Class**:
  * `__init__()`: Initializes `bluetooth.BLE()`, registers `self._ble_irq`, maintains `self._raw_queue`.
  * `scan(duration_ms=5000, node_id="esp32-001", timestamp=0)`:
    * Activates BLE radio if not active.
    * Calls `ble.gap_scan(duration_ms, 30000, 30000, True)`.
    * Blocks until scan completes (`_scan_done` flag set or timeout elapsed).
    * Drains `self._raw_queue`, parses payloads, deduplicates by MAC address.
    * Returns list of standardized Schema v1 dictionaries.
    * Deactivates BLE radio to release RF hardware back to Wi-Fi.

### 3.3 `esp32_sensor/config.py`
Add BLE-specific configuration constants:
```python
BLE_SCAN_DURATION_MS = 5000
BLE_SCAN_ENABLED = True
```

### 3.4 `esp32_sensor/main.py`
Integrate BLE scanning into the main sensor execution loop:
1. Connect Wi-Fi if needed.
2. Run Wi-Fi scan: `wifi_obs = wifi_scanner.scan_networks(wlan, config.NODE_ID, timestamp)`.
3. If `config.BLE_SCAN_ENABLED`:
   * Run BLE scan: `ble_obs = ble_scanner_instance.scan(config.BLE_SCAN_DURATION_MS, config.NODE_ID, timestamp)`.
4. Enqueue all collected observations into `retry_queue`.
5. Flush `retry_queue` to Pico W via `post_observation()`.
6. Sleep for `config.SCAN_INTERVAL_SECONDS`.

---

## 4. Acceptance Criteria & Verification

| Code | Criterion | Verification Method |
| :--- | :--- | :--- |
| **AC-16** | BLE Discovery | ESP32 scanner discovers nearby BLE devices and records address, RSSI, and timestamp. Verified via unit test mock & live ESP32 execution. |
| **AC-17** | BLE Observation Schema | BLE observations match Schema v1 (`schema_version=1`, `radio="ble"`, `channel=None`, `address` lowercase hex). Verified via `tests/test_esp32_sensor.py`. |
| **AC-15** | Store-and-Forward Retained | If the gateway is offline, both Wi-Fi and BLE observations buffer safely in `retry_queue` up to `MAX_QUEUE_SIZE`. |
| **AC-11** | Gateway Ingestion | Pico W accepts `radio="ble"` records at `POST /observation` and persists them to `observations.jsonl`. |

---

## 5. Non-Goals
* Continuous 24/7 background BLE scanning (postponed until dual-core FreeRTOS task separation or dedicated ESP32-S3 firmware in Phase 6).
* Full GATT connection or pairing (passive discovery only).
* In-depth packet signature inference (deferred to Phase 5 Signature Engine).
