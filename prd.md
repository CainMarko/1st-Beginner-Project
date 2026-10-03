# Fieldwatch-Inspired Distributed RF/IoT Sensing Platform

**Document:** `PRD.md`
**Version:** 0.1
**Status:** Active Development
**Architecture:** Distributed edge sensing + gateway + local data platform
**Primary Firmware:** MicroPython
**Primary Development Hardware:** Raspberry Pi Pico W + ESP32-CAM
**Future Field Hardware:** ESP32-S3 + SX1262 LoRa + L76 GNSS

---

# 1. Product Overview

## 1.1 Working Name

**Fieldwatch-Inspired Distributed RF/IoT Sensing Platform**

The project is a modular, distributed sensing platform inspired by the general capabilities of RF observation and field-monitoring systems.

The system will use inexpensive ESP32-class microcontrollers and Raspberry Pi hardware to detect, normalize, store, transmit, analyze, and eventually visualize observations from multiple radio and sensor sources.

The initial system will focus on:

* Wi-Fi observation
* Bluetooth/BLE observation
* RSSI measurements
* Device signatures
* Time-based observations
* Geographic observations
* Distributed field nodes
* LoRa communications
* Local/self-hosted data storage
* Graph-based relationships
* Local/edge AI for higher-level analysis

The project is intentionally being developed in layers.

The hardware performs deterministic sensing.

The gateway performs collection and buffering.

The database performs durable storage.

The graph layer represents relationships.

AI operates above these layers to analyze and reason over the resulting information.

---

# 2. Problem Statement

Low-cost microcontrollers can collect substantial amounts of environmental and radio information, but individual boards are generally isolated systems.

A useful sensing platform requires:

1. Reliable sensor acquisition
2. A standardized observation format
3. Communication between nodes
4. Persistent storage
5. Data synchronization
6. Device/signature normalization
7. Geographic and temporal context
8. Relationship modeling
9. Visualization and analysis
10. Optional AI-assisted reasoning

The project aims to combine these capabilities into a modular system that can be built incrementally using inexpensive hardware and open-source software.

---

# 3. Goal

## Primary Goal

Build a low-cost, modular, self-hosted distributed sensing platform capable of deploying multiple field nodes that collect radio and environmental observations and transmit those observations to a local gateway for persistent storage, analysis, graph modeling, and eventually AI-assisted reasoning.

The system should be:

* inexpensive
* modular
* open-source friendly
* self-hosted
* expandable
* understandable by the developer
* usable without proprietary cloud infrastructure
* capable of operating with intermittent connectivity
* capable of supporting multiple types of sensing nodes

---

# 4. Scope

## 4.1 In Scope

### Hardware

* Raspberry Pi Pico W
* ESP32
* ESP32-CAM
* ESP32-S3
* SX1262 LoRa
* L76 GNSS
* OLED displays
* microSD storage
* battery-powered nodes
* solar-powered nodes
* Raspberry Pi computers
* laptop-based central collector

### Radio/Sensor Sources

* Wi-Fi
* BLE
* GNSS/GPS
* LoRa
* camera imagery
* RSSI
* future environmental sensors

### Software

* MicroPython firmware
* HTTP APIs
* JSON/JSONL
* SQLite
* graph database
* local data processing
* device signature engine
* visualization
* optional local LLM/SLM integration
* GraphRAG
* node management
* synchronization
* store-and-forward operation

### Architecture

The target architecture is:

```text
                    FIELD NODES
        ┌────────────┬────────────┬────────────┐
        │            │            │            │
     ESP32        ESP32-CAM    ESP32-S3     Pico W
     Wi-Fi/BLE    Wi-Fi/BLE     Wi-Fi/BLE    Gateway
                              GNSS/LoRa
        │            │            │
        └────────────┴──────┬─────┘
                            │
                       Wi-Fi / LoRa
                            │
                            ▼
                     EDGE GATEWAY
                            │
                            ▼
                         SQLite
                            │
                    ┌───────┴───────┐
                    ▼               ▼
                  Graph          Analytics
                    │               │
                    └───────┬───────┘
                            ▼
                     Local AI / SLM
                            │
                            ▼
                     Visualization
```

---

# 5. Out of Scope

The initial project will not include:

* Wi-Fi deauthentication
* packet injection
* credential capture
* unauthorized network access
* exploitation of discovered devices
* intrusive surveillance
* breaking encryption
* offensive cyber operations

The system will focus on passive observation and authorized experimentation.

---

# 6. Core Objectives

## Objective 1: Build a Reliable Edge Gateway

Create a Raspberry Pi Pico W service capable of:

* connecting to Wi-Fi
* exposing an HTTP API
* accepting observations
* validating observations
* buffering observations
* persisting observations
* reporting node status

### Success Criteria

The Pico must:

1. Boot successfully.
2. Connect to Wi-Fi.
3. Report its IP address.
4. Serve `/status`.
5. Accept `POST /observation`.
6. Return HTTP `200 OK` for valid observations.
7. Reject malformed observations.
8. Persist observations.
9. Recover observations after reboot.

---

# 7. Objective 2: Establish a Standard Observation Schema

Every sensing node should produce a common observation structure.

Initial schema:

```json
{
    "schema_version": 1,
    "node_id": "esp32-001",
    "timestamp": 0,
    "radio": "wifi",
    "address": "",
    "rssi": null,
    "channel": null,
    "ssid": "",
    "manufacturer": "",
    "signature": "",
    "latitude": null,
    "longitude": null
}
```

The schema must remain extensible.

Future fields may include:

```text
altitude
accuracy
device_type
frequency
band
lo_ra_rssi
snr
battery
temperature
camera_reference
session_id
location_id
confidence
```

---

# 8. Objective 3: Build Persistent Edge Storage

The Pico currently stores observations only in RAM.

The next objective is persistent storage.

Initial implementation:

```text
storage.py
       │
       ▼
observations.jsonl
```

Each observation will occupy one JSON line.

Example:

```json
{"schema_version":1,"node_id":"esp32-001","radio":"wifi","rssi":-57}
{"schema_version":1,"node_id":"esp32-001","radio":"wifi","rssi":-63}
```

## Requirements

The storage layer must support:

* initialization
* append
* loading
* bounded RAM usage
* observation counting
* corruption tolerance
* storage statistics

---

# 9. Objective 4: Build the ESP32 Sensor Node

The ESP32-CAM will initially be used primarily as a radio sensing platform.

The first sensor capability will be Wi-Fi scanning.

Pipeline:

```text
ESP32
  │
  ├── Wi-Fi scan
  │
  ├── SSID
  ├── BSSID
  ├── channel
  └── RSSI
        │
        ▼
   observation
        │
        ▼
    HTTP POST
        │
        ▼
      Pico W
```

The camera will be integrated later rather than making it a prerequisite for radio sensing.

---

# 10. Objective 5: Add BLE Observation

The ESP32 will subsequently scan for BLE advertisements.

The BLE scanner will collect information such as:

* address
* RSSI
* advertisement metadata
* manufacturer data where appropriate
* service information where available

The BLE subsystem must use a queue so that heavy processing is not performed directly inside the BLE callback.

Architecture:

```text
BLE radio
   │
   ▼
IRQ callback
   │
   ▼
event queue
   │
   ▼
normalization
   │
   ▼
observation
```

---

# 11. Objective 6: Build a Device Signature Engine

Raw observations will eventually be normalized into reusable signatures.

Example:

```text
Wi-Fi observation
       │
       ▼
BSSID / OUI
       │
       ▼
Manufacturer
       │
       ▼
Observed characteristics
       │
       ▼
Signature
```

A signature should not imply certainty.

Instead, the system should maintain confidence and evidence.

Example:

```json
{
    "manufacturer": "Example",
    "signature": "example-device-family",
    "confidence": 0.72
}
```

---

# 12. Objective 7: Add GNSS

The ESP32-S3 field node will use the L76 GNSS module.

The GNSS subsystem will provide:

* latitude
* longitude
* altitude where available
* fix status
* satellite information where available
* timestamp
* location accuracy where available

GNSS information will be attached to observations.

Example:

```json
{
    "radio": "wifi",
    "address": "...",
    "rssi": -62,
    "latitude": 40.123,
    "longitude": -74.123
}
```

---

# 13. Objective 8: Add LoRa

The ESP32-S3 + SX1262 board will become the primary mobile/remote field node.

LoRa will provide long-range, low-power communication between nodes and gateways where Wi-Fi is unavailable or undesirable.

Target architecture:

```text
Remote Field Node
        │
   Wi-Fi/BLE
        │
    observation
        │
       LoRa
        │
        ▼
     Gateway
        │
        ▼
     storage
```

LoRa will primarily transmit compact observation metadata rather than large payloads.

Camera images and other large data should generally be transferred through Wi-Fi, microSD, or another higher-bandwidth mechanism.

---

# 14. Objective 9: Add Store-and-Forward Networking

Field nodes cannot assume continuous connectivity.

Nodes should therefore support:

```text
collect
   ↓
store locally
   ↓
connectivity available?
   │
 ┌─┴─────┐
 no      yes
 │        │
 ▼        ▼
store    transmit
          │
          ▼
       gateway
```

This is particularly important for:

* battery-powered nodes
* mobile nodes
* remote deployments
* LoRa-only environments

---

# 15. Objective 10: Build the Central Data Platform

The laptop or later Raspberry Pi will become the central data platform.

Initial stack:

```text
Python
SQLite
```

The collector will:

* receive observations
* validate them
* deduplicate where appropriate
* store raw observations
* index timestamps
* index node IDs
* index addresses
* index locations
* track sessions

---

# 16. Objective 11: Build the Graph Layer

Once sufficient observations exist, the system will represent relationships as a graph.

Conceptual graph:

```text
Node
 │
 └── observed ──► Device
                    │
                    ├── manufacturer ──► Manufacturer
                    │
                    └── signature ──► Signature

Observation
 │
 ├── location ──► Location
 │
 ├── session ──► Session
 │
 └── generated-by ──► Node
```

Potential relationships:

```text
Device A
   │
   └── co-observed-with ──► Device B
```

The graph will allow temporal and spatial relationships to be analyzed.

---

# 17. Objective 12: Add Local AI

AI will operate above the deterministic sensing and database layers.

The intended architecture is:

```text
Sensors
   ↓
Observations
   ↓
Database
   ↓
Graph
   ↓
Retrieval
   ↓
LLM / SLM
```

AI may eventually answer questions such as:

* What devices have been repeatedly observed together?
* What changed in this area over time?
* Which nodes observed the same device?
* What patterns exist across observation sessions?
* Which observations are anomalous?
* What locations have unusual activity patterns?

AI should not replace deterministic data collection.

---

# 18. Objective 13: Build GraphRAG

GraphRAG will combine:

* structured observations
* graph relationships
* vector/search retrieval
* LLM reasoning

Conceptually:

```text
User question
      │
      ▼
Query planner
      │
 ┌────┴─────┐
 ▼          ▼
Graph     SQLite
query      query
 │          │
 └────┬─────┘
      ▼
 Evidence
      │
      ▼
    LLM
      │
      ▼
 Answer + evidence
```

---

# 19. Current Hardware

## Raspberry Pi Pico W

Role:

**Initial edge gateway**

Capabilities:

* Wi-Fi
* HTTP server
* observation ingestion
* validation
* buffering
* persistent storage

---

## Freenove ESP32-CAM

Role:

**Primary experimental sensor node**

Capabilities:

* Wi-Fi
* BLE
* camera
* microSD
* local processing

Future capabilities:

* Wi-Fi observation
* BLE observation
* camera events
* local signatures
* observation transmission

---

## ESP32-S3 + SX1262 + L76 GNSS

Role:

**Future mobile field node**

Capabilities:

* ESP32-S3
* Wi-Fi
* BLE
* SX1262 LoRa
* GNSS
* OLED
* battery
* solar input

This board will eventually become the primary autonomous field node.

---

# 20. Software Architecture

## Firmware

MicroPython initially.

Project structure:

```text
firmware/
│
├── pico_gateway/
│   ├── main.py
│   ├── config.py
│   ├── secrets.py
│   └── storage.py
│
├── esp32_sensor/
│   ├── main.py
│   ├── config.py
│   ├── secrets.py
│   ├── wifi_scanner.py
│   ├── ble_scanner.py
│   ├── observation.py
│   └── signatures.py
│
└── s3_field_node/
    ├── main.py
    ├── config.py
    ├── wifi_scanner.py
    ├── ble_scanner.py
    ├── gps.py
    ├── lora.py
    ├── power.py
    └── display.py
```

---

# 21. Current API

The Pico currently exposes:

## `GET /`

Human-readable status page.

## `GET /status`

Machine-readable node status.

Example:

```json
{
    "node_id": "pico-w-001",
    "firmware": "0.2.0",
    "schema_version": 1,
    "wifi_connected": true,
    "ip": "192.168.1.xxx",
    "uptime": 123,
    "observation_count": 1
}
```

## `GET /observations`

Returns observations currently held by the Pico.

## `POST /observation`

Accepts a JSON observation.

Example:

```json
{
    "schema_version": 1,
    "node_id": "test-client",
    "timestamp": 1760000000,
    "radio": "wifi",
    "address": "AA:BB:CC:DD:EE:FF",
    "rssi": -57,
    "channel": 6,
    "latitude": 40.0,
    "longitude": -74.0
}
```

---

# 22. Completed Work

## Phase 0: Hardware and Architecture

### Completed

* Selected Raspberry Pi Pico W as initial gateway.
* Selected Freenove ESP32-CAM as initial sensor platform.
* Identified ESP32-S3/SX1262/L76 board as future field node.
* Established distributed architecture.
* Established common observation schema.
* Chosen MicroPython as initial firmware platform.
* Defined future Wi-Fi/BLE/GNSS/LoRa architecture.

---

# 23. Completed Pico W Work

The Pico W has successfully:

* connected to home Wi-Fi
* obtained an IP address
* served a web page
* exposed `/status`
* exposed `/observations`
* accepted HTTP POST requests
* parsed JSON
* validated required observation fields
* stored observations in RAM
* returned JSON responses
* handled fragmented HTTP POST bodies
* returned HTTP `200 OK`
* successfully completed an end-to-end test from PowerShell

Current successful pipeline:

```text
PowerShell
    ↓
HTTP POST
    ↓
Wi-Fi
    ↓
Pico W
    ↓
HTTP parser
    ↓
JSON parser
    ↓
validation
    ↓
RAM observation buffer
    ↓
HTTP 200
```

---

# 24. Current Limitations

The Pico currently has several important limitations.

## Persistence

Observations disappear after reboot.

**Next task:** implement `storage.py`.

## Scalability

The current server handles one connection at a time.

This is acceptable for the prototype.

Later:

* asynchronous handling
* connection queue
* more robust HTTP implementation
* MQTT or another lightweight protocol

may be considered.

## Storage durability

The current system has no flash-storage management strategy.

Future requirements:

* file rotation
* queue management
* corruption recovery
* upload acknowledgment
* retry logic

## Security

The current HTTP server has no authentication or encryption.

This is acceptable on the isolated local development network.

Production deployments should use appropriate network isolation and/or authenticated transport.

---

# 25. Immediate Development Plan

## Phase 1: Persistent Pico Storage

### Step 1

Create:

```text
storage.py
```

### Step 2

Implement:

```text
initialize()
save_observation()
load_observations()
count_observations()
```

### Step 3

Modify `main.py`.

Replace:

```text
RAM-only storage
```

with:

```text
RAM buffer + persistent JSONL
```

### Step 4

Test:

```text
POST
 ↓
GET
 ↓
reboot
 ↓
GET
```

### Step 5

Verify observations survive a power cycle.

---

# 26. Phase 2: ESP32 Wi-Fi Scanner

Implement:

```text
wifi_scanner.py
```

Capabilities:

* scan nearby Wi-Fi networks
* obtain SSID
* obtain BSSID
* obtain channel
* obtain RSSI
* create observations
* POST observations to Pico

Target:

```text
ESP32
  ↓
Wi-Fi scan
  ↓
observation
  ↓
HTTP POST
  ↓
Pico W
  ↓
persistent storage
```

This will be the first complete real sensing pipeline.

---

# 27. Phase 3: ESP32 BLE Scanner

Add:

```text
ble_scanner.py
```

Architecture:

```text
BLE callback
      ↓
event queue
      ↓
processor
      ↓
observation
      ↓
Pico
```

---

# 28. Phase 4: Signature Engine

Add:

```text
signatures.py
```

Responsibilities:

* normalize identifiers
* identify manufacturers where possible
* calculate signatures
* assign confidence
* avoid overclaiming device identity

---

# 29. Phase 5: Laptop Collector

Build:

```text
collector/
├── server.py
├── database.py
├── models.py
└── ingest.py
```

Initial database:

```text
SQLite
```

The laptop becomes the durable central repository.

---

# 30. Phase 6: GNSS + LoRa Node

Bring up the ESP32-S3 board one subsystem at a time:

1. ESP32-S3
2. OLED
3. GNSS
4. Wi-Fi
5. BLE
6. SX1262
7. battery/power management
8. sleep/wake
9. field-node firmware

Do not attempt to bring all peripherals online simultaneously.

---

# 31. Phase 7: Distributed Field Testing

Deploy:

```text
Node A
Node B
Node C
```

Collect observations from multiple locations.

Measure:

* coverage
* RSSI
* battery consumption
* LoRa range
* packet loss
* observation throughput
* storage requirements
* synchronization reliability

---

# 32. Phase 8: Graph Platform

Import observations into the graph.

Initial entities:

```text
Node
Device
Observation
Location
Session
Manufacturer
Signature
```

Initial relationships:

```text
Node ──observed──> Device
Observation ──generated-by──> Node
Observation ──observed──> Device
Observation ──located-at──> Location
Observation ──part-of──> Session
Device ──manufactured-by──> Manufacturer
Device ──matches──> Signature
```

---

# 33. Phase 9: Analytics

Build deterministic analytics before AI.

Examples:

* observation frequency
* first/last seen
* RSSI trends
* device co-occurrence
* node coverage
* location clustering
* temporal patterns
* device mobility
* anomaly detection

---

# 34. Phase 10: AI / GraphRAG

Only after the underlying data platform is reliable.

Potential components:

```text
SQLite
Graph DB
Vector DB
Retrieval layer
Local SLM/LLM
GraphRAG
```

AI capabilities:

* natural-language querying
* relationship discovery
* summarization
* anomaly investigation
* temporal analysis
* spatial reasoning
* evidence-backed reports

---

# 35. Non-Functional Requirements

## Cost

The prototype should prioritize existing hardware and open-source software.

The architecture should avoid unnecessary recurring cloud costs.

## Offline Operation

Nodes should be capable of collecting data when the central server is unavailable.

## Modularity

Radio subsystems must be independently replaceable.

## Observability

Every component should provide:

* health information
* errors
* version information
* node ID
* timestamps
* storage statistics

## Reliability

The system should tolerate:

* Wi-Fi loss
* LoRa loss
* gateway reboot
* field-node reboot
* corrupted observation
* intermittent connectivity

## Privacy

The system should minimize unnecessary collection of personal information.

Observation identifiers should be treated carefully and access to collected data should be controlled.

---

# 36. Design Principles

## Principle 1: Deterministic systems first

Sensors collect facts.

Databases store facts.

AI interprets facts.

---

## Principle 2: Standardize observations early

Every node should speak the same observation language.

---

## Principle 3: Store raw data

Never rely solely on AI-generated interpretations.

Raw observations should remain available for later analysis.

---

## Principle 4: Edge first

Perform inexpensive processing on the node where practical.

---

## Principle 5: Local first

Use local infrastructure whenever practical.

---

## Principle 6: Fail gracefully

A disconnected node should collect and retry rather than lose everything.

---

## Principle 7: Build vertically

Every development stage should produce a working system.

Avoid building six disconnected subsystems before testing the first end-to-end workflow.

---

# 37. Current Project State

```text
                    PROJECT STATUS

Architecture             ██████████  Complete
Pico Wi-Fi               ██████████  Complete
Pico HTTP server         ██████████  Complete
Observation schema       ██████████  Complete
JSON ingestion           ██████████  Complete
Validation               ██████████  Complete
POST testing             ██████████  Complete

Persistent storage       ██████████  Complete
ESP32 Wi-Fi scanner      ██████████  Complete
ESP32 → Pico ingestion   ██████████  Complete
BLE scanner              ░░░░░░░░░░  NEXT
Signature engine         ░░░░░░░░░░
SQLite collector         ░░░░░░░░░░
GNSS                     ░░░░░░░░░░
LoRa                     ░░░░░░░░░░
Distributed nodes        ░░░░░░░░░░
Graph                    ░░░░░░░░░░
Analytics                ░░░░░░░░░░
GraphRAG                 ░░░░░░░░░░
Local AI                 ░░░░░░░░░░
```

---

# 38. Immediate Next Milestone

The immediate milestone is:

> **Make the Pico W a persistent observation gateway.**

Success looks like:

```text
ESP32 / test client
        │
        ▼
 POST /observation
        │
        ▼
    Pico W
        │
        ├── validate
        │
        ├── RAM buffer
        │
        └── JSONL storage
                │
                ▼
        observations.jsonl
```

Then:

```text
Pico reboot
     ↓
storage initialization
     ↓
load observations
     ↓
observations still available
```

Once this works, the next milestone becomes the first **real sensor-to-gateway pipeline**:

```text
ESP32
  ↓
Wi-Fi scan
  ↓
observation
  ↓
Pico W
  ↓
persistent storage
```

That is the point at which the project moves from a network-programming prototype into an actual distributed sensing platform.


# 39. Measurable Acceptance Criteria

Acceptance criteria define the minimum measurable conditions required to consider each project milestone complete.

A milestone is not considered complete merely because the code runs once. It must pass the associated functional and reliability tests.

---

## 39.1 Phase 1: Pico W Gateway

### AC-01: Wi-Fi Connectivity

**Requirement**

The Pico W must connect to the configured Wi-Fi network automatically at boot.

**Acceptance test**

1. Power-cycle the Pico W.
2. Allow up to 30 seconds for startup.
3. Pico must connect successfully.
4. Pico must print a valid IPv4 address.

**Pass criteria**

* Connection succeeds in ≤30 seconds.
* IPv4 address is assigned.
* `/status` reports:

```json
{
    "wifi_connected": true
}
```

---

### AC-02: HTTP Server

**Requirement**

The Pico W must expose its HTTP service after successful Wi-Fi connection.

**Acceptance test**

Request:

```text
GET /
```

**Pass criteria**

* HTTP response status = `200 OK`
* Response contains `Pico W Field Node`
* Response contains the configured node ID.

---

### AC-03: Status Endpoint

**Requirement**

`/status` must provide machine-readable node information.

**Acceptance test**

Request:

```text
GET /status
```

**Pass criteria**

Response is valid JSON and contains:

```text
node_id
firmware
schema_version
wifi_connected
ip
uptime
observation_count
```

---

### AC-04: Valid Observation Ingestion

**Requirement**

The Pico must accept a valid observation.

**Acceptance test**

Send a valid JSON observation using HTTP POST.

**Pass criteria**

* HTTP status = `200 OK`
* Response contains `"success": true`
* Response contains the submitted observation.
* `observation_count` increases by 1.

---

### AC-05: Invalid Observation Rejection

**Requirement**

Malformed observations must not be stored.

**Acceptance test**

Submit observations missing one or more required fields:

```text
schema_version
node_id
timestamp
radio
```

**Pass criteria**

* HTTP status = `400 Bad Request`
* Response contains `"success": false`
* Invalid observation is not added to the observation count.

---

### AC-06: Observation Retrieval

**Requirement**

Stored observations must be retrievable.

**Acceptance test**

1. POST one valid observation.
2. Request:

```text
GET /observations
```

**Pass criteria**

* HTTP status = `200 OK`
* Response is valid JSON.
* Submitted observation is present.
* All submitted fields are preserved.

---

# 39.2 Phase 2: Persistent Storage

### AC-07: Persistent Write

**Requirement**

Valid observations must be written to persistent storage.

**Acceptance test**

1. POST an observation.
2. Verify successful response.
3. Inspect the Pico filesystem.

**Pass criteria**

* Storage file exists.
* Observation is present in the storage file.
* Observation remains readable after the HTTP request completes.

---

### AC-08: Persistence Across Soft Reboot

**Requirement**

Stored observations must survive a MicroPython reboot.

**Acceptance test**

1. POST 5 observations.
2. Verify `observation_count = 5`.
3. Trigger `Ctrl+D`.
4. Wait for the Pico to restart.
5. Request `/observations`.

**Pass criteria**

* All 5 observations are still present.
* No observation is duplicated.
* No observation is lost.

---

### AC-09: Persistence Across Power Cycle

**Requirement**

Stored observations must survive complete power loss.

**Acceptance test**

1. Store at least 10 observations.
2. Disconnect Pico power.
3. Wait at least 10 seconds.
4. Restore power.
5. Request `/observations`.

**Pass criteria**

* All 10 observations are recovered.
* No duplicate observations are introduced.

---

### AC-10: Storage Corruption Tolerance

**Requirement**

A malformed storage record must not prevent the gateway from starting.

**Acceptance test**

Introduce one malformed JSONL record into the storage file and reboot.

**Pass criteria**

* Pico successfully boots.
* HTTP server starts.
* Valid observations remain accessible.
* Malformed record is skipped or reported.

---

### AC-11: Bounded RAM Usage

**Requirement**

Persistent storage must not require loading an unlimited number of observations into RAM.

**Acceptance test**

Populate the storage file with at least 1,000 observations.

**Pass criteria**

* Pico boots successfully.
* Memory usage remains within the available RAM budget.
* HTTP service remains operational.

The implementation may use a bounded in-memory cache rather than loading the entire file.

---

# 39.3 Phase 3: ESP32 Wi-Fi Sensor

### AC-12: Wi-Fi Scanning

**Requirement**

The ESP32 must successfully perform passive Wi-Fi network discovery.

**Acceptance test**

Run a scan in an environment containing known Wi-Fi networks.

**Pass criteria**

Each discovered network contains, where provided by the hardware/API:

```text
SSID
BSSID
channel
RSSI
```

At least one known test network must be detected.

---

### AC-13: Observation Generation

**Requirement**

The ESP32 must convert scan results into the standard observation schema.

**Acceptance test**

Perform a Wi-Fi scan.

**Pass criteria**

Every generated observation contains:

```text
schema_version
node_id
timestamp
radio
address
rssi
channel
```

and:

```text
radio == "wifi"
```

---

### AC-14: ESP32-to-Pico Transmission

**Requirement**

The ESP32 must transmit observations to the Pico W.

**Acceptance test**

1. Start Pico gateway.
2. Start ESP32.
3. Perform Wi-Fi scan.
4. Send observations to Pico.
5. Query Pico `/observations`.

**Pass criteria**

* At least 90% of successfully generated test observations arrive at the Pico during a controlled 100-observation test.
* Received observations preserve the original node ID and radio type.
* No malformed observations are accepted.

---

### AC-15: Automatic Retry

**Requirement**

The ESP32 must tolerate temporary gateway unavailability.

**Acceptance test**

1. Start ESP32.
2. Disconnect or stop the Pico gateway.
3. Generate observations.
4. Restore Pico gateway.
5. Allow retry process to run.

**Pass criteria**

* Observations generated during the outage are retained locally.
* At least 90% of retained observations are delivered after connectivity returns.
* No observation is intentionally discarded solely because the gateway was temporarily unavailable.

---

# 39.4 Phase 4: BLE Sensor

### AC-16: BLE Discovery

**Requirement**

The ESP32 must detect BLE advertisements.

**Acceptance test**

Use at least one known BLE advertising device.

**Pass criteria**

The scanner records:

```text
address
RSSI
timestamp
```

for the test device.

---

### AC-17: BLE Observation Schema

**Requirement**

BLE observations must use the same common observation schema.

**Pass criteria**

Each BLE observation contains:

```text
schema_version
node_id
timestamp
radio
address
rssi
```

with:

```text
radio == "ble"
```

---

# 39.5 Phase 5: Device Signature Engine

### AC-18: Deterministic Signature Generation

**Requirement**

The same input characteristics must produce the same signature.

**Acceptance test**

Process the same test observation 100 times.

**Pass criteria**

All 100 executions produce the same signature.

---

### AC-19: Unknown Device Handling

**Requirement**

The system must not invent device identities.

**Acceptance test**

Process an observation that does not match a known signature.

**Pass criteria**

The system returns an explicit unknown/undetermined classification rather than claiming a specific device model.

---

### AC-20: Confidence Representation

**Requirement**

Probabilistic classifications must include confidence information.

**Pass criteria**

Any non-deterministic classification includes a confidence value between:

```text
0.0 and 1.0
```

---

# 39.6 Phase 6: Central Collector

### AC-21: SQLite Ingestion

**Requirement**

The central collector must persist observations into SQLite.

**Acceptance test**

Transmit 1,000 valid observations.

**Pass criteria**

* At least 99% of valid observations are stored.
* Database remains readable.
* No database corruption occurs.
* Each stored observation retains its source node ID and timestamp.

---

### AC-22: Duplicate Handling

**Requirement**

The collector must define and enforce a duplicate policy.

**Acceptance test**

Submit the same observation multiple times.

**Pass criteria**

The system behaves according to the documented deduplication policy.

The policy may be:

* preserve duplicates as raw observations, or
* identify and collapse exact duplicates.

The chosen policy must be explicit.

---

### AC-23: Query Performance

**Initial target**

The collector must retrieve recent observations from a database containing at least 100,000 observations.

**Pass criteria**

Common queries such as:

```text
observations by node
observations by timestamp
observations by address
observations by location
```

should return within 1 second on the development laptop under normal local conditions.

---

# 39.7 Phase 7: GNSS

### AC-24: GNSS Fix

**Requirement**

The ESP32-S3 field node must obtain a valid GNSS fix under suitable outdoor conditions.

**Pass criteria**

After acquisition, the node reports:

```text
latitude
longitude
fix status
timestamp
```

The recorded position must be within the expected accuracy reported by the GNSS receiver.

---

### AC-25: Location Association

**Requirement**

Observations generated while a valid GNSS fix exists must be associated with the current location.

**Pass criteria**

At least 95% of observations generated during a valid-fix test contain valid latitude and longitude values.

---

# 39.8 Phase 8: LoRa

### AC-26: LoRa Point-to-Point Communication

**Requirement**

Two compatible nodes must exchange valid test messages over LoRa.

**Acceptance test**

Send 100 numbered messages.

**Pass criteria**

* Receiver correctly receives at least 95 messages.
* Message numbering remains intact.
* Corrupted messages are detected and rejected.

Actual range will be measured separately because terrain, antennas, frequency configuration, and regulatory constraints materially affect performance.

---

### AC-27: LoRa Observation Transport

**Requirement**

The field node must transmit compact observations over LoRa.

**Pass criteria**

A transmitted observation can be reconstructed by the gateway with:

```text
node_id
timestamp
radio
address
RSSI
```

preserved.

---

# 39.9 Phase 9: Store-and-Forward

### AC-28: Offline Collection

**Requirement**

A field node must continue collecting observations while disconnected from the gateway.

**Acceptance test**

Disconnect the gateway for 10 minutes while the field node continues scanning.

**Pass criteria**

* Observations continue to be generated.
* Observations are stored locally.
* No intentional data loss occurs because of temporary gateway unavailability.

---

### AC-29: Synchronization

**Requirement**

The node must upload locally queued observations when connectivity returns.

**Pass criteria**

At least 95% of queued observations are successfully synchronized during a controlled test.

---

# 39.10 Phase 10: Graph Platform

### AC-30: Graph Representation

**Requirement**

The graph must represent core entities and relationships.

Minimum entities:

```text
Node
Observation
Device
Location
Session
Manufacturer
Signature
```

Minimum relationships:

```text
Node -> generated -> Observation
Observation -> observed -> Device
Observation -> located-at -> Location
Observation -> part-of -> Session
Device -> manufacturer -> Manufacturer
Device -> signature -> Signature
```

**Pass criteria**

A test dataset can be imported and queried through all required relationships.

---

### AC-31: Temporal Queries

**Requirement**

The graph/data platform must support temporal investigation.

**Acceptance test**

Query observations for a specific device over a specified time interval.

**Pass criteria**

Results include:

* observation timestamp
* node
* location where available
* signal information where available

---

### AC-32: Co-Occurrence Queries

**Requirement**

The platform must identify devices observed during the same session or observation window.

**Pass criteria**

Given a controlled test dataset, the system correctly identifies known co-occurring devices.

---

# 39.11 Phase 11: Analytics

### AC-33: First-Seen / Last-Seen

For a known device, the system must calculate:

```text
first_seen
last_seen
observation_count
```

**Pass criteria**

Values match the underlying observation dataset.

---

### AC-34: RSSI Analysis

The system must support RSSI statistics including:

```text
minimum
maximum
average
median
observation count
```

**Pass criteria**

Calculated values match independently calculated values from the same test dataset.

---

### AC-35: Spatial Analysis

The system must support observations grouped by geographic region.

**Pass criteria**

A controlled test dataset can be grouped by:

* node
* location
* time
* device

---

# 39.12 Phase 12: Local AI / GraphRAG

### AC-36: Evidence-Based Answers

AI-generated answers must be grounded in retrieved observations.

**Acceptance test**

Ask a question whose answer is explicitly contained in the test dataset.

**Pass criteria**

* AI returns the correct answer.
* Retrieved evidence can be identified.
* The system does not fabricate observations absent from the database.

---

### AC-37: Unknown Information

**Requirement**

The AI must distinguish between:

```text
known
unknown
inferred
```

**Pass criteria**

When the database lacks sufficient evidence, the system explicitly identifies the missing information rather than presenting speculation as fact.

---

### AC-38: Source Traceability

AI responses must be traceable to underlying data.

**Pass criteria**

An answer can identify the observations, database records, or graph relationships supporting the conclusion.

---

# 39.13 System Reliability

### AC-39: Gateway Reboot Recovery

After a gateway reboot:

* Wi-Fi reconnects automatically.
* HTTP server starts automatically.
* Stored observations remain accessible.

Target:

**≥ 99% successful recovery across 20 controlled reboots.**

---

### AC-40: Sensor Reboot Recovery

After an ESP32 reboot:

* scanner restarts automatically
* node ID remains correct
* observations continue being generated
* gateway communication resumes

Target:

**≥ 95% successful recovery across 20 controlled reboots.**

---

### AC-41: Network Interruption

During controlled Wi-Fi interruptions:

* observations are not silently discarded
* queued observations remain available
* synchronization resumes after connectivity returns

Target:

**≥ 95% successful recovery of queued observations.**

---

# 39.14 Data Integrity

### AC-42: Schema Validation

100% of observations accepted by the central database must conform to the current schema version.

---

### AC-43: Timestamp Integrity

At least 99% of observations in a controlled test must contain valid timestamps.

Invalid timestamps must be rejected or explicitly marked invalid.

---

### AC-44: Node Identification

100% of accepted observations must contain a valid `node_id`.

---

# 39.15 Performance Targets

Initial performance targets:

| Component                       |                  Target |
| ------------------------------- | ----------------------: |
| Pico boot to Wi-Fi              |                ≤ 30 sec |
| Pico HTTP response              |                 ≤ 1 sec |
| Valid observation acceptance    |                   ≥ 99% |
| ESP32 test observation delivery |                   ≥ 90% |
| Central ingestion               |                   ≥ 99% |
| Offline synchronization         |                   ≥ 95% |
| LoRa test delivery              |                   ≥ 95% |
| Gateway reboot recovery         |                   ≥ 99% |
| Sensor reboot recovery          |                   ≥ 95% |
| Database common query           | ≤ 1 sec at 100k records |

These are engineering targets rather than guarantees for every deployment environment.

---

# 39.16 Security and Privacy Acceptance

### AC-45: No Credential Capture

The system must not intentionally collect Wi-Fi passwords, authentication credentials, or other secret authentication material.

---

### AC-46: Passive Observation

The initial sensing system must operate using passive observation techniques.

---

### AC-47: Local Data Protection

Collected observations must be stored on controlled infrastructure.

Production deployments must provide an appropriate access-control strategy.

---

# 39.17 Documentation Acceptance

Every major subsystem must have:

1. Installation instructions
2. Configuration instructions
3. API/schema documentation
4. Test procedure
5. Troubleshooting information
6. Version information

A subsystem is not considered production-ready until another person can reproduce its basic setup using the documentation.

---

# 39.18 Definition of Done

A development phase is considered complete when:

* Functional requirements pass.
* Acceptance tests pass.
* Failure behavior has been tested.
* Data format is documented.
* Configuration is documented.
* Recovery behavior is tested.
* No known critical errors remain.
* The implementation is committed to version control.
* The next subsystem can consume its documented interface without modifying its internal implementation.

---

# 40. Current Acceptance Status

| Capability                       | Status      |
| -------------------------------- | ----------- |
| Pico Wi-Fi connection            | PASS        |
| Pico HTTP server                 | PASS        |
| `/status`                        | PASS        |
| `/observations`                  | PASS        |
| JSON observation ingestion       | PASS        |
| Observation validation           | PASS        |
| Fragmented HTTP request handling | PASS        |
| HTTP `200 OK` ingestion          | PASS        |
| Persistent storage               | PASS        |
| Reboot persistence               | PASS        |
| ESP32 Wi-Fi scanner              | PASS        |
| ESP32 → Pico ingestion           | PASS        |
| BLE scanner                      | NEXT        |
| Signature engine                 | NOT STARTED |
| SQLite collector                 | NOT STARTED |
| GNSS                             | NOT STARTED |
| LoRa                             | NOT STARTED |
| Store-and-forward                | PASS        |
| Graph                            | NOT STARTED |
| Analytics                        | NOT STARTED |
| GraphRAG                         | NOT STARTED |
| Local AI                         | NOT STARTED |

---

# 41. Current Next Acceptance Gate

The immediate acceptance gate is **Persistent Pico Storage**.

The phase will pass only when this sequence succeeds:

```text
1. Start Pico
       ↓
2. POST 10 observations
       ↓
3. GET /observations
       ↓
4. Confirm 10 observations
       ↓
5. Reboot Pico
       ↓
6. Wait for Wi-Fi
       ↓
7. GET /observations
       ↓
8. Confirm same 10 observations
       ↓
9. Power-cycle Pico
       ↓
10. GET /observations
       ↓
11. Confirm same 10 observations
```

Expected result:

```text
Before reboot:       10
After soft reboot:   10
After power cycle:   10
```

Only after this gate passes should development proceed to the ESP32 Wi-Fi sensing node.

