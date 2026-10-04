# LoRa/GNSS Field Node Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a second field sensor node with LoRa and GNSS capabilities to extend the RF sensing and camera trap range, communicating back to the central collector.

**Architecture:** The new node will be based on an ESP32-S3 microcontroller, integrating an SX1262 LoRa module for long-range communication and an L76 GNSS module for location awareness. It will leverage the existing MicroPython codebase for Wi-Fi/BLE scanning and the central Python collector for data ingestion.

**Tech Stack:** MicroPython, ESP32-S3, SX1262 LoRa module, L76 GNSS module, existing Python collector (SQLite, FastAPI/Flask-like server).

## Global Constraints
*   inexpensive
*   modular
*   open-source friendly
*   self-hosted
*   expandable
*   understandable by the developer
*   usable without proprietary cloud infrastructure
*   capable of operating with intermittent connectivity
*   capable of supporting multiple types of sensing nodes

---

### Task 1: Hardware Selection & Initial Firmware Flash

**Goal:** Select an appropriate ESP32-S3 board with LoRa/GNSS compatibility and flash a MicroPython firmware capable of supporting these modules.

**Files:**
- Create: `docs/hardware_selection_lora_gnss.md`

**Interfaces:**
- Produces: Selected hardware model, compatible MicroPython firmware binary.

- [ ] **Step 1: Research ESP32-S3 boards with LoRa & GNSS compatibility.**
  Identify suitable development boards that integrate or are easily compatible with SX1262 LoRa and L76 GNSS modules.

- [ ] **Step 2: Document hardware selection.**
  Create `docs/hardware_selection_lora_gnss.md` with the chosen board, its pinout, required modules (if not integrated), and reasons for selection.

- [ ] **Step 3: Download/build MicroPython firmware.**
  Obtain or compile a MicroPython firmware `.bin` file that supports ESP32-S3, LoRa (usually via `machine.SPI` and `machine.Pin`), and GNSS (via `machine.UART`).

- [ ] **Step 4: Flash MicroPython to the new ESP32-S3 board.**
  Use `esptool.py` to flash the selected MicroPython firmware onto the new board via USB.
  Run: `py -3 -m esptool --port COMx --baud 460800 write_flash -z 0x1000 firmware.bin`
  Expected: Successful flash with verification.

- [ ] **Step 5: Test basic MicroPython functionality.**
  Connect to the board via `mpremote` and verify the MicroPython prompt is accessible.
  Run: `py -3 -m mpremote connect COMx`
  Expected: MicroPython REPL prompt `>>>`

- [ ] **Step 6: Commit**

```bash
git add docs/hardware_selection_lora_gnss.md
git commit -m "feat(lora-gnss): document hardware selection and initial firmware flash for new node"
```

### Task 2: LoRa Module Driver Integration & Basic Send/Receive Test

**Goal:** Integrate a MicroPython driver for the SX1262 LoRa module and verify basic point-to-point communication between two nodes (or a node and a listener).

**Files:**
- Create: `esp32_sensor_lora/lora_driver.py`
- Create: `esp32_sensor_lora/main_lora_test.py`

**Interfaces:**
- Consumes: `lora_driver.py` (provides `LoRa` class with `send` and `receive` methods).
- Produces: Functioning LoRa communication.

- [ ] **Step 1: Write LoRa driver (`lora_driver.py`).**
  Implement a MicroPython class to interface with the SX1262 LoRa module using SPI. Include initialization, send, and receive methods. This might involve adapting existing MicroPython LoRa libraries.

- [ ] **Step 2: Write basic LoRa sender test (`main_lora_test.py`).**
  Create a script that initializes the LoRa module and sends a simple "Hello, LoRa!" message periodically.

- [ ] **Step 3: Write basic LoRa receiver test (modifying `main_lora_test.py` or separate script).**
  Create a script that initializes the LoRa module and listens for incoming messages, printing them to the console.

- [ ] **Step 4: Perform point-to-point LoRa communication test.**
  Flash one board with the sender script and another (or simulate with a second LoRa module connected to a PC) with the receiver script. Verify messages are exchanged.
  Run: `py -3 -m mpremote connect COMx cp esp32_sensor_lora/lora_driver.py :lora_driver.py esp32_sensor_lora/main_lora_test.py :main.py; py -3 -m mpremote connect COMx reset` (for sender/receiver)
  Expected: Messages printed on receiver console.

- [ ] **Step 5: Commit**

```bash
git add esp32_sensor_lora/lora_driver.py esp32_sensor_lora/main_lora_test.py
git commit -m "feat(lora-gnss): implement LoRa driver and basic send/receive test"
```

### Task 3: GNSS Module Driver Integration & Location Fix Test

**Goal:** Integrate a MicroPython driver for the L76 GNSS module and verify a successful location fix.

**Files:**
- Create: `esp32_sensor_lora/gnss_driver.py`
- Modify: `esp32_sensor_lora/main_gnss_test.py`

**Interfaces:**
- Consumes: `gnss_driver.py` (provides `GNSS` class with `get_location` method).
- Produces: Accurate GPS coordinates and fix status.

- [ ] **Step 1: Write GNSS driver (`gnss_driver.py`).**
  Implement a MicroPython class to interface with the L76 GNSS module using UART. Parse NMEA sentences to extract latitude, longitude, altitude, and fix quality.

- [ ] **Step 2: Write basic GNSS test (`main_gnss_test.py`).**
  Create a script that initializes the GNSS module and continuously tries to get a location fix, printing the coordinates and fix status.

- [ ] **Step 3: Perform outdoor GNSS location fix test.**
  Take the board outdoors (or near a window with clear sky view). Flash the GNSS test script and verify that it eventually obtains a valid fix and accurate coordinates.
  Run: `py -3 -m mpremote connect COMx cp esp32_sensor_lora/gnss_driver.py :gnss_driver.py esp32_sensor_lora/main_gnss_test.py :main.py; py -3 -m mpremote connect COMx reset`
  Expected: Latitude, longitude, and fix status printed, with coordinates matching actual location.

- [ ] **Step 4: Commit**

```bash
git add esp32_sensor_lora/gnss_driver.py esp32_sensor_lora/main_gnss_test.py
git commit -m "feat(lora-gnss): implement GNSS driver and location fix test"
```

### Task 4: Unified LoRa/GNSS Node MicroPython Application

**Goal:** Combine the LoRa and GNSS functionalities into a unified MicroPython application that periodically collects GNSS data and transmits it via LoRa, potentially along with RF observations from Wi-Fi/BLE (if implemented on this node).

**Files:**
- Create: `esp32_sensor_lora/lora_gnss_main.py`
- Modify: `esp32_sensor_lora/lora_driver.py` (if needed for integration)
- Modify: `esp32_sensor_lora/gnss_driver.py` (if needed for integration)

**Interfaces:**
- Consumes: `lora_driver.py`, `gnss_driver.py`.
- Produces: LoRa packets containing GNSS data and node ID.

- [ ] **Step 1: Create unified main application (`lora_gnss_main.py`).**
  This script will:
  - Initialize LoRa and GNSS modules.
  - Periodically obtain a GNSS fix.
  - Package location data (and potentially basic node status) into a compact LoRa message.
  - Transmit the LoRa message.

- [ ] **Step 2: Update Pico W Gateway to receive LoRa messages.**
  If the Pico W will act as the LoRa gateway, integrate a LoRa receiver into `pico-hub/main.py` that listens for incoming LoRa packets, extracts the GNSS and node data, and forwards it to the central collector.
  *Alternative: If using a dedicated LoRa gateway for the laptop, this step involves setting up that gateway software.*

- [ ] **Step 3: Test end-to-end LoRa/GNSS data flow.**
  Deploy the new ESP32-S3 node with `lora_gnss_main.py` and verify that the central collector receives GNSS data, along with its `node_id`.
  Expected: GNSS data (lat/lon) and node ID appearing in the collector's database/logs.

- [ ] **Step 4: Commit**

```bash
git add esp32_sensor_lora/lora_gnss_main.py
git commit -m "feat(lora-gnss): implement unified LoRa/GNSS node application and data flow"
```

---