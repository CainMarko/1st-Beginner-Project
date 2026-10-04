"""RF-Triggered Visual Sentry & Camera Trap for ESP32-CAM.

Evaluates incoming RF observations from Wi-Fi and BLE scanners.
When high proximity (RSSI >= -65 dBm) or suspicious archetypes are detected,
triggers an OV2640 camera capture and uploads the JPEG to the Central Collector.
"""

import time

# Pinout configuration for standard AI-Thinker ESP32-CAM (with OV2640 sensor)
CAM_CONFIG = {
    "d0": 5, "d1": 18, "d2": 19, "d3": 21,
    "d4": 36, "d5": 39, "d6": 34, "d7": 35,
    "format": 2,          # camera.JPEG
    "framesize": 9,       # camera.FRAME_VGA (640x480) or SVGA (800x600)
    "xclk_freq": 20000000,# 20 MHz
    "href": 23, "vsync": 25, "reset": -1, "pwdn": 32,
    "sioc": 27, "siod": 26, "xclk": 0, "pclk": 22,
    "fb_location": 1      # camera.LOCATION_PSRAM
}

# Trap trigger thresholds
TRIGGER_RSSI_THRESHOLD = -65  # dBm (triggers when transmitter is in close proximity)
COOLDOWN_SECONDS = 10         # Minimum seconds between snapshots
SUSPICIOUS_ARCHETYPES = {"tracking-beacon"}

_camera_initialized = False
_camera_module = None
_last_capture_time = 0
_known_macs = set()


def init_camera():
    """Initializes the OV2640 camera driver if available on firmware."""
    global _camera_initialized, _camera_module
    if _camera_initialized:
        return True

    try:
        import camera
        _camera_module = camera
        # Initialize camera with AI-Thinker pinout
        camera.init(0, **CAM_CONFIG)
        _camera_initialized = True
        print("[CAM] Camera trap initialized successfully (OV2640 VGA JPEG)")
        return True
    except ImportError:
        print("[CAM] 'camera' C-module not present in standard MicroPython firmware.")
        return False
    except Exception as e:
        print("[CAM] Failed to initialize camera hardware:", e)
        return False


def should_trigger(observation):
    """Evaluates whether an observation triggers the camera trap.
    
    Returns:
        (trigger: bool, reason: str)
    """
    global _known_macs

    rssi = observation.get("rssi") or -100
    addr = observation.get("address", "").lower()
    signature = observation.get("signature", "unknown")

    # 1. Proximity spike trigger
    if rssi >= TRIGGER_RSSI_THRESHOLD:
        return True, "proximity-spike"

    # 2. Suspicious archetype trigger
    if signature in SUSPICIOUS_ARCHETYPES:
        return True, "suspicious-" + signature

    # 3. First-time seen MAC with strong signal
    if addr and addr not in _known_macs and rssi >= -75:
        _known_macs.add(addr)
        return True, "new-proximity-device"

    return False, ""


def trigger_and_upload(observation, collector_ip, collector_port=8080, node_id="esp32-001"):
    """Snaps a frame and uploads it via raw HTTP POST to collector."""
    global _last_capture_time, _camera_module

    now = time.time()
    if (now - _last_capture_time) < COOLDOWN_SECONDS:
        return False, "cooldown"

    trigger, reason = should_trigger(observation)
    if not trigger:
        return False, "no-trigger"

    if not init_camera() or not _camera_module:
        return False, "camera-unavailable"

    print("[CAM] TRAP TRIGGERED by", observation.get("address"), "Reason:", reason, "RSSI:", observation.get("rssi"))

    try:
        img_bytes = _camera_module.capture()
        if not img_bytes:
            return False, "empty-frame"
    except Exception as e:
        print("[CAM] Capture failed:", e)
        return False, str(e)

    _last_capture_time = now

    # Upload via raw socket HTTP POST
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((collector_ip, collector_port))

        addr = observation.get("address", "")
        rssi = str(observation.get("rssi", ""))
        path = "/api/camera/frame?node=" + node_id + "&addr=" + addr + "&rssi=" + rssi + "&reason=" + reason

        headers = (
            "POST " + path + " HTTP/1.1\r\n"
            "Host: " + collector_ip + ":" + str(collector_port) + "\r\n"
            "Content-Type: image/jpeg\r\n"
            "Content-Length: " + str(len(img_bytes)) + "\r\n"
            "X-Node-ID: " + node_id + "\r\n"
            "X-Trigger-Address: " + addr + "\r\n"
            "X-Trigger-RSSI: " + rssi + "\r\n"
            "X-Trigger-Reason: " + reason + "\r\n"
            "Connection: close\r\n\r\n"
        ).encode("utf-8")

        s.sendall(headers)
        s.sendall(img_bytes)

        resp = s.recv(256)
        s.close()
        print("[CAM] Snapshot successfully uploaded to Collector! (" + str(len(img_bytes)) + " bytes)")
        return True, "uploaded"
    except Exception as e:
        print("[CAM] Failed to upload capture to collector:", e)
        return False, str(e)
