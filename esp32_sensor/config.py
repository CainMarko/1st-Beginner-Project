"""Configuration for ESP32 Fieldwatch Sensor Node."""

NODE_ID = "esp32-001"
GATEWAY_HOST = "192.168.1.152"
GATEWAY_PORT = 80
GATEWAY_PATH = "/observation"

# Scanning cadence in seconds
SCAN_INTERVAL_SECONDS = 30

# Maximum number of observations to buffer in RAM if gateway is offline (AC-15)
MAX_QUEUE_SIZE = 100

# Wi-Fi connection timeout in seconds
WIFI_TIMEOUT_SECONDS = 20

# BLE Scanning configuration
BLE_SCAN_DURATION_MS = 5000
BLE_SCAN_ENABLED = True
BLE_SCAN_INTERVAL_US = 100000  # 100ms interval
BLE_SCAN_WINDOW_US = 100000    # 100ms window (100% duty cycle: window == interval)

# Visual Sentry / RF-Triggered Camera Trap
CAMERA_TRAP_ENABLED = True
COLLECTOR_HOST = "192.168.1.156"
COLLECTOR_PORT = 8080



