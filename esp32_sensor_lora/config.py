"""Configuration for ESP32-S3 LoRa/GNSS Field Node (Heltec WiFi LoRa 32 V4).

All pin assignments follow the S3R2 variant pinout from the Heltec datasheet.
"""

# Node identity
NODE_ID = "esp32-lora-01"

# ── SX1262 LoRa Module (SPI) ─────────────────────────────────────────
LORA_NSS = 8
LORA_SCK = 9
LORA_MOSI = 10
LORA_MISO = 11
LORA_RST = 12
LORA_BUSY = 13
LORA_DIO1 = 14

# LoRa FEM (Front-End Module) control
LORA_FEM_EN = 2
LORA_PA_CTX = 5
LORA_VFEM_CTRL = 7

# LoRa radio parameters
LORA_FREQUENCY = 915_000_000   # 915 MHz ISM (US)
LORA_SPREADING_FACTOR = 7      # SF7 (fastest, shortest range)
LORA_BANDWIDTH = 125000        # 125 kHz
LORA_CODING_RATE = 5           # 4/5
LORA_TX_POWER = 22             # dBm (max 28 with FEM)
LORA_PREAMBLE_LEN = 8
LORA_SYNC_WORD = 0x1424        # private network (0x3444 = LoRaWAN)

# ── L76 GNSS Module (UART) ──────────────────────────────────────────
GNSS_UART_BAUD = 9600
GNSS_RX_PIN = 39    # ESP RX — data from GNSS module
GNSS_TX_PIN = 38    # ESP TX — data to GNSS module
GNSS_RST_PIN = 42
GNSS_PPS_PIN = 41
GNSS_WAKEUP_PIN = 40
GNSS_POWER_PIN = 34   # VGNSS_Ctrl — HIGH = on

# GNSS fix parameters
GNSS_FIX_TIMEOUT_MS = 90000   # max wait for a cold-start fix
GNSS_FIX_RETRY_MS = 5000       # retry interval if no fix

# ── OLED Display (I2C) ──────────────────────────────────────────────
OLED_SDA = 17
OLED_SCL = 18
OLED_RST = 21

# ── Power Control ───────────────────────────────────────────────────
VEXT_CTRL = 36     # LOW = Ve outputs on
LED_PIN = 35
ADC_CTRL = 37      # drive HIGH to enable battery read on GPIO1
VBAT_READ = 1

# ── Collector ───────────────────────────────────────────────────────
# Central collector for HTTP reporting (same as existing sensor nodes)
COLLECTOR_HOST = "192.168.1.156"
COLLECTOR_PORT = 8080
COLLECTOR_PATH = "/observation"

# Wi-Fi for HTTP reporting to collector
WIFI_TIMEOUT_SECONDS = 20

# ── Telemetry cycle ─────────────────────────────────────────────────
# How often to collect GNSS + RF data and transmit via LoRa
TELEMETRY_INTERVAL_SECONDS = 60

# Maximum observations to buffer
MAX_QUEUE_SIZE = 100
