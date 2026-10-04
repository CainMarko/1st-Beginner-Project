# Fieldwatch-Inspired Distributed RF/IoT Sensing Platform

This project is a modular, distributed sensing platform for environmental and radio observation. It uses inexpensive MicroPython-powered ESP32 and Raspberry Pi Pico W microcontrollers as field sensors and edge gateways, integrated with a Python-based central collector for data ingestion, storage, analysis, and visualization.

## ✨ Key Features

*   **Multi-Node RF Sensing**: Utilizes both ESP32 (Wi-Fi & BLE) and Raspberry Pi Pico W (Wi-Fi) for wide-spectrum RF observation.
*   **RF-Triggered Visual Sentry**: ESP32-CAM field sensors automatically capture images when high-proximity RF signals (mobile devices, tracking beacons, new devices) are detected, filtering out stationary Wi-Fi access points.
*   **Edge Gateway**: Raspberry Pi Pico W acts as a local HTTP server, ingesting observations from field nodes and providing store-and-forward capabilities for robust data collection.
*   **Central Collector**: A Python-based server on your laptop for:
    *   **Data Ingestion**: High-speed SQLite database (WAL mode) for thousands of observations.
    *   **Device Fingerprinting**: Automated classification and signature generation for Wi-Fi and BLE devices.
    *   **Real-time Dashboard**: Interactive web dashboard (`http://localhost:8080/`) with live stats, device tables, observation timelines, and a Visual Sentry gallery.
*   **Autonomous Operation**: Field sensors operate independently on 5V USB power after initial setup, communicating wirelessly.
*   **Extensible Architecture**: Designed for future expansion with LoRa, GNSS, and AI integration.

## 🚀 Getting Started

This project is built using MicroPython for the microcontroller nodes and Python 3 for the collector.

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/CainMarko/1st-Beginner-Project.git
    cd 1st-Beginner-Project
    ```
2.  **Python Environment**:
    Ensure you have Python 3.x installed. It's recommended to use a virtual environment:
    ```bash
    python -m venv venv
    ./venv/Scripts/activate # On Windows
    source venv/bin/activate # On macOS/Linux
    pip install -r requirements.txt
    ```
3.  **Microcontroller Setup**:
    *   **ESP32-WROVER-DEV (or ESP32-CAM)**: Flash MicroPython firmware with BLE and Camera support. Upload `esp32_sensor/` contents (config.py, secrets.py, main.py, camera_trap.py, etc.) to the device's filesystem.
    *   **Raspberry Pi Pico W**: Flash MicroPython firmware. Upload `pico-hub/` contents (main.py, report.py, secrets.py) to the device's filesystem.
    *   *Detailed flashing and file transfer instructions are available in the `docs/` directory.*

4.  **Running the Collector**:
    Start the central collector server on your laptop:
    ```bash
    python -m collector run
    ```
    Access the dashboard at `http://localhost:8080/`.

## 📐 Architecture Overview

```mermaid
graph TD
    ESP32_Sensor[ESP32 Field Sensor: Wi-Fi, BLE, Camera] -->|Observations, Images (HTTP POST)| Pico_Hub
    Pico_Hub[Raspberry Pi Pico W: Edge Gateway] -->|Observations (HTTP POST)| Laptop_Collector
    Laptop_Collector[Laptop Collector: Python Server, SQLite DB, Web UI] --o|Views Dashboard| Browser[Web Browser]
    Laptop_Collector -->|ALFA Scanner (Wi-Fi 2.4/5 GHz)| RF_Environment[RF Environment]
    Pico_Hub -->|Wi-Fi| RF_Environment
    ESP32_Sensor -->|Wi-Fi & BLE| RF_Environment
    ESP32_Sensor -->|Camera View| Physical_Environment[Physical Environment]
```

## 🗺️ Roadmap

The project is being developed in phases. Key upcoming phases include:

*   **Phase 6: GNSS + LoRa Node**: Integration of GPS (GNSS) and Long-Range (LoRa) communication for advanced field nodes.
*   **Phase 7: Distributed Field Testing**: Deployment and testing of multiple autonomous field nodes.
*   **Phase 8: Graph Platform**: Building a graph database layer to model relationships between devices and observations.
*   **Phase 9: Analytics**: Implementing advanced analytics for pattern-of-life, co-occurrence, and dwell-time detection.
*   **Phase 10: AI / GraphRAG**: Integrating local LLMs for AI-assisted reasoning and situational reporting.

For more details, refer to the [Product Requirements Document (PRD)](./prd.md) and the `docs/` directory.
