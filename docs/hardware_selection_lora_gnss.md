# Hardware Selection for LoRa & GNSS Node

## Chosen Board: LilyGO T-Beam-S3 Supreme

The LilyGO T-Beam-S3 Supreme has been selected for this project due to its integrated ESP32-S3, SX1262 LoRa module, and L76K GNSS module, directly meeting the project requirements. Its comprehensive features and available documentation make it an ideal development platform.

### Key Features:
-   **MCU:** ESP32-S3FN8 (dual-core LX7 @ 240 MHz)
-   **LoRa Module:** SX1262 (supports 433/868/915/923 MHz)
-   **GNSS Module:** L76K (selectable with MAX-M10S, but L76K is suitable for this project)
-   **Display:** 1.3-inch SH1106 OLED (128x64)
-   **Power Management:** AXP2101 PMU
-   **Memory:** 8 MB Flash + 8 MB PSRAM
-   **Connectivity:** Wi-Fi, Bluetooth 5.0 LE

### Pinout and Module Information:

The board utilizes an AXP2101 PMU for power management of the LoRa, GNSS, and OLED modules. Firmware will need to enable the relevant PMU rails before initializing these peripherals.

**SX1262 LoRa Module:**
-   `pin_lora_nss`: GPIO10
-   `pin_lora_rst`: GPIO5
-   `pin_lora_busy`: GPIO4
-   `pin_lora_dio1`: GPIO1
-   `pin_lora_sck`: GPIO12
-   `pin_lora_miso`: GPIO13
-   `pin_lora_mosi`: GPIO11

**L76K GNSS Module (UART):**
-   `pin_gps_uart_rx`: GPIO9
-   `pin_gps_uart_tx`: GPIO8
-   `gps_uart_baud`: 9600

**AXP2101 PMU (I2C):**
-   `i2c_sda`: GPIO42
-   `i2c_scl`: GPIO41
-   `aldo1`: True (sensor/OLED rail)
-   `aldo2`: True (I2C bus enable)
-   `aldo3`: True (LoRa radio rail)
-   `aldo4`: True (GNSS rail)

### Reasons for Selection:
-   **Integrated Components:** The board comes with both LoRa (SX1262) and GNSS (L76K) modules, simplifying hardware integration.
-   **ESP32-S3:** Powerful MCU with Wi-Fi and Bluetooth capabilities, suitable for IoT applications.
-   **Comprehensive Documentation:** LilyGO provides extensive documentation, including pinouts and firmware examples, which aids in development.
-   **MicroPython Compatibility:** The ESP32-S3 is well-supported by MicroPython, and the pinout information will be crucial for configuring the `machine.SPI` and `machine.UART` instances.
