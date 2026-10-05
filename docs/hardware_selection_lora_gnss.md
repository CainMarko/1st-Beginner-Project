# Hardware Selection for LoRa & GNSS Node

## Chosen Board: Heltec WiFi LoRa 32 V4 (ESP32-S3R2)

The Heltec WiFi LoRa 32 V4 is a fully upgraded version of the classic LoRa development
board, featuring an ESP32-S3R2 MCU, integrated SX1262 LoRa radio, and an SH1.25-8Pin
GNSS expansion interface for the L76 GNSS module. The board also includes a 0.96" OLED,
solar charging input, 3000mAh battery, and USB Type-C with ESD protection.

### Key Features:
- **MCU:** ESP32-S3R2 (dual-core LX7 @ 240 MHz, 2MB PSRAM, 16MB Flash)
- **LoRa Module:** SX1262 (433/868/915 MHz, up to 28 dBm TX power, -137 dBm sensitivity)
- **GNSS Module:** L76 (GPS, GLONASS, QZSS, SBAS; cold start <15s; ~2.6mA low-power)
- **Display:** 0.96-inch OLED (SSD1306, 128x64, I2C)
- **Power:** USB-C / solar (4.4-6V) / 3000mAh Li-ion battery, <20uA deep sleep
- **Antennas:** IPEX LoRa (915MHz) + FPC 2.4GHz Wi-Fi/BLE

### Pinout (S3R2 Variant)

#### SX1262 LoRa Module (SPI)
| Function   | GPIO | Notes                        |
|------------|------|------------------------------|
| NSS (CS)   | 8    | SPI chip select              |
| SCK        | 9    | SPI clock                    |
| MOSI       | 10   | SPI data out                 |
| MISO       | 11   | SPI data in                  |
| RST        | 12   | Hardware reset               |
| BUSY       | 13   | Busy indicator (read before SPI) |
| DIO1       | 14   | IRQ interrupt pin            |

#### LoRa FEM (Front-End Module) Control
| Function     | GPIO | Notes                              |
|--------------|------|------------------------------------|
| FEM_EN       | 2    | FEM enable                         |
| PA_CTX       | 5    | PA TX/RX control                   |
| VFEM_Ctrl    | 7    | FEM supply control                 |

#### L76 GNSS Module (UART via SH1.25-8Pin connector)
| Function       | GPIO | Direction (ESP perspective)  |
|----------------|------|------------------------------|
| GNSS_TX (RX)   | 39   | ESP RX — data from GNSS      |
| GNSS_RX (TX)   | 38   | ESP TX — data to GNSS        |
| GNSS_RST       | 42   | GNSS reset                   |
| GNSS_PPS       | 41   | 1 PPS pulse                 |
| GNSS_Wakeup    | 40   | GNSS wake-up control          |
| VGNSS_Ctrl     | 34   | GNSS power enable (HIGH = on) |

#### OLED Display (I2C)
| Function | GPIO |
|----------|------|
| SDA      | 17   |
| SCL      | 18   |
| RST      | 21   |

#### Power Control
| Function    | GPIO | Notes                              |
|-------------|------|------------------------------------|
| Vext_Ctrl   | 36   | LOW enables Ve 3.3V outputs        |
| LED         | 35   | White user LED                     |
| ADC_Ctrl    | 37   | Drive to enable battery read on GPIO1 |
| VBAT_Read   | 1    | ADC1_CH0, battery voltage sense     |

> **Firmware note:** The board was flashed with `ESP32_GENERIC_S3-SPIRAM_OCT` (S3R8
> build). On the S3R2 variant, GPIO33-GPIO37 are NOT used by PSRAM (quad, not octal).
> If the S3R8 firmware drives those pins for octal PSRAM access, it could conflict
> with VGNSS_Ctrl (GPIO34). If GNSS power issues arise, reflash with
> `ESP32_GENERIC_S3-SPIRAM` (quad PSRAM build).

### Reasons for Selection:
- **Integrated LoRa + GNSS:** SX1262 and L76 on one board, no external wiring needed
  for the core radio + location stack.
- **ESP32-S3:** Powerful MCU with Wi-Fi and BLE for the existing sensor codebase.
- **Solar + Battery:** Supports autonomous outdoor deployment.
- **MicroPython Compatible:** Well-supported by MicroPython 1.2x+ for ESP32-S3.
- **Pin Compatibility:** Backward compatible with WiFi LoRa 32 V3 pinouts.
