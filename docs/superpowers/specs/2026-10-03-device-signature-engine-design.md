# Design Specification: Device Signature Engine

**Date:** 2026-10-03  
**Status:** Approved  
**Target:** `esp32_sensor/signatures.py`, integrating with `esp32_sensor/observation.py`, `wifi_scanner.py`, `ble_scanner.py`  
**PRD Milestones:** PRD Section 11 (Objective 6: Build a Device Signature Engine), Section 28 (Phase 4: Signature Engine), Section 39.5 (AC-18: Deterministic Signature Generation, AC-19: Unknown Device Handling, AC-20: Confidence Representation).

---

## 1. Overview & Objectives

Transform raw Wi-Fi and Bluetooth Low Energy (BLE) observations into enriched, structured device profiles with deterministic classification and confidence scoring.

* **AC-18 (Deterministic Signature Generation)**: The same input characteristics must deterministically produce the exact same signature and confidence across repeated executions.
* **AC-19 (Unknown Device Handling)**: The engine must never invent or hallucinate device identities or models. Unknown devices explicitly receive `manufacturer: "unknown"`, `signature: "unknown"`, `confidence: 0.0`.
* **AC-20 (Confidence Representation)**: All classifications include a numerical confidence score bounded between `0.0` and `1.0`.
* **Microcontroller-Friendly Memory Footprint**: Uses an embedded lookup dictionary tailored for ESP32 RAM (~100-200 KB free heap) covering standard consumer, router, and IoT identifiers, deferring full IEEE database queries (50,000+ entries) to the laptop collector in Phase 5.

---

## 2. Standardized Taxonomy

Device signatures are classified into seven canonical functional archetypes:

| Signature Archetype | Description | Examples |
| :--- | :--- | :--- |
| `router-ap` | Wi-Fi Access Points, routers, gateways, extenders | Actiontec, Netgear, Eero, Arris, Asus, TP-Link |
| `mobile-personal` | Smartphones, tablets, smartwatches, fitness trackers | Apple iPhone/Watch, Samsung Galaxy, Google Fitbit |
| `audio-peripheral` | Wireless headphones, earbuds, speakers | Sony WH/WF series, Bose, JBL, Beats |
| `smart-home` | Smart appliances, plugs, bulbs, Matter/Thread nodes | Levoit air purifiers, Tuya switches, Matter commissioning nodes |
| `tracking-beacon` | One-way advertising tags & location beacons | Apple Find My / AirTag, Samsung SmartTag, Tile |
| `iot-microcontroller` | Development boards, raw silicon modules | Espressif ESP32/ESP8266, Raspberry Pi |
| `unknown` | Devices with randomized MACs or unrecognized characteristics | Unregistered OUIs with empty payloads |

---

## 3. Schema v1 Extension: `confidence`

Schema v1 dictionaries are extended to include a top-level `confidence` float field (as anticipated in PRD Section 7):

```json
{
  "schema_version": 1,
  "node_id": "esp32-001",
  "timestamp": 1760000000,
  "radio": "ble",
  "address": "a8:e6:e8:d0:6b:74",
  "rssi": -81,
  "channel": null,
  "ssid": "WH-CH720N",
  "manufacturer": "Sony",
  "signature": "audio-peripheral",
  "confidence": 0.95,
  "connectable": true,
  "latitude": null,
  "longitude": null
}
```

---

## 4. Multi-Signal Evidence & Classification Engine

`signatures.classify(observation)` evaluates evidence in prioritized order:

### 4.1 Lookup Tables

#### Wi-Fi OUI Dictionary (`OUI_TABLE`):
Maps 3-byte lowercase hex prefixes (`xx:xx:xx`) to `(manufacturer, signature_hint, base_confidence)`:
* `b8:f8:53`, `00:0f:94`, `00:15:05`, `00:18:01`, `00:1d:ce` $\rightarrow$ `("Actiontec", "router-ap", 0.95)`
* `24:4c:ab`, `30:ae:a4`, `ac:67:b2`, `bc:dd:c2`, `ec:62:60` $\rightarrow$ `("Espressif", "iot-microcontroller", 0.85)`
* `b8:27:eb`, `dc:a6:32`, `d8:3a:dd`, `e4:5f:01`, `28:cd:c1` $\rightarrow$ `("Raspberry Pi", "iot-microcontroller", 0.85)`
* `00:14:bf`, `c0:56:27`, `e0:46:9a`, `f4:6b:ef` $\rightarrow$ `("Linksys", "router-ap", 0.95)`
* `00:09:5b`, `00:11:50`, `00:14:04`, `08:02:8e`, `20:4e:7f` $\rightarrow$ `("Netgear", "router-ap", 0.95)`
* `00:17:88`, `ec:b5:fa` $\rightarrow$ `("Philips Lighting", "smart-home", 0.90)`
* `00:1a:22`, `00:26:4a` $\rightarrow$ `("Ubiquiti", "router-ap", 0.95)`
* `00:24:e4`, `44:65:0d`, `a0:02:dc` $\rightarrow$ `("Amazon", "smart-home", 0.85)`
* `00:03:93`, `00:1e:c2`, `fc:65:de`, `f0:99:b6` $\rightarrow$ `("Apple", "mobile-personal", 0.80)`
* `00:12:fb`, `00:15:99`, `00:17:c4`, `00:21:19` $\rightarrow$ `("Samsung", "mobile-personal", 0.80)`

#### BLE SIG Company ID Dictionary (`BLE_COMPANY_TABLE`):
Maps 4-character lowercase hex IDs to `(manufacturer, default_signature)`:
* `004c` $\rightarrow$ `("Apple", "mobile-personal")`
* `0075` $\rightarrow$ `("Samsung", "mobile-personal")`
* `0006` $\rightarrow$ `("Microsoft", "mobile-personal")`
* `6068` $\rightarrow$ `("Sony", "audio-peripheral")`
* `06d0` $\rightarrow$ `("Levoit / VeSync", "smart-home")`
* `06a8` $\rightarrow$ `("Tencent", "mobile-personal")`
* `012d` $\rightarrow$ `("Sony Video", "audio-peripheral")`
* `02d2` $\rightarrow$ `("Espressif", "iot-microcontroller")`
* `000a` $\rightarrow$ `("Qualcomm", "audio-peripheral")`
* `0059` $\rightarrow$ `("Nordic Semi", "iot-microcontroller")`

### 4.2 Name & Keyword Rules (`KEYWORD_RULES`)
If local name/SSID is available, regex/substring heuristics refine archetype and boost confidence:
* Contains `"WH-"`, `"WF-"`, `"AirPods"`, `"Beats"`, `"Bose"`, `"Buds"`, `"JBL"` $\rightarrow$ `signature: "audio-peripheral"`, `confidence: 0.95`
* Contains `"LAP-"`, `"Core 200S"`, `"Core 300"`, `"Purifier"`, `"Plug"`, `"Bulb"`, `"MATTER"` $\rightarrow$ `signature: "smart-home"`, `confidence: 0.90`
* Contains `"Fitbit"`, `"Band"`, `"Watch"`, `"Garmin"` $\rightarrow$ `signature: "mobile-personal"`, `confidence: 0.90`
* Contains `"ESP32"`, `"ESP8266"`, `"Pico"`, `"Arduino"` $\rightarrow$ `signature: "iot-microcontroller"`, `confidence: 0.95`

### 4.3 BLE Advertising Heuristics
* If `radio == "ble"` and `connectable == False` and name is empty and manufacturer in `("Apple", "Samsung")`:
  $\rightarrow$ `signature: "tracking-beacon"`, `confidence: 0.75`
* If `radio == "ble"` and `connectable == True` and manufacturer in `("Apple", "Samsung")`:
  $\rightarrow$ `signature: "mobile-personal"`, `confidence: 0.70`

### 4.4 Wi-Fi AP Heuristic
* If `radio == "wifi"` and no specific consumer OUI is matched:
  $\rightarrow$ Since the observation originated from an 802.11 beacon frame, it is inherently an AP:
  `signature: "router-ap"`, `confidence: 0.60`, `manufacturer: "unknown"`

### 4.5 Fallback (AC-19)
* If no characteristics match:
  `manufacturer: "unknown"`, `signature: "unknown"`, `confidence: 0.0`

---

## 5. Module Interface (`esp32_sensor/signatures.py`)

```python
def classify(observation):
    """Analyze observation and return (manufacturer, signature, confidence).
    
    Guaranteed deterministic: identical inputs yield identical outputs (AC-18).
    Never invents models or brands (AC-19).
    Returns confidence between 0.0 and 1.0 (AC-20).
    """
    ...

def enrich_observation(observation):
    """Mutate and return observation with manufacturer, signature, and confidence."""
    ...
```

---

## 6. Testing & Acceptance Criteria

1. **Deterministic Execution (AC-18)**: Test runs 100 iterations of identical input records and asserts identical output tuples.
2. **Strict Unknowns (AC-19)**: An observation with randomized MAC `da:00:11:22:33:44` and no name/payload returns `"unknown"`, `"unknown"`, `0.0`.
3. **Bounded Confidence (AC-20)**: Verify that `0.0 <= confidence <= 1.0` for all classified types.
4. **End-to-End Pipeline**: ESP32 delivers observations to Pico W gateway where `check_gateway.py` displays populated `manufacturer`, `signature`, and `confidence` fields.
