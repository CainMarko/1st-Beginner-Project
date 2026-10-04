"""Device Signature Engine for Fieldwatch Sensing Nodes.

Enriches raw Wi-Fi and Bluetooth Low Energy (BLE) observations with hardware
vendor identification, functional archetype classification, and numeric
confidence scoring (0.0 to 1.0) while satisfying AC-18, AC-19, and AC-20.
"""

# Wi-Fi OUI Table: maps 3-byte hex prefix (xx:xx:xx) to (manufacturer, signature_hint, confidence)
OUI_TABLE = {
    # Actiontec / Verizon Fios Routers & Extenders
    "b8:f8:53": ("Actiontec", "router-ap", 0.95),
    "00:0f:94": ("Actiontec", "router-ap", 0.95),
    "00:15:05": ("Actiontec", "router-ap", 0.95),
    "00:18:01": ("Actiontec", "router-ap", 0.95),
    "00:1d:ce": ("Actiontec", "router-ap", 0.95),
    "00:26:b8": ("Actiontec", "router-ap", 0.95),

    # Espressif IoT Silicon
    "24:4c:ab": ("Espressif", "iot-microcontroller", 0.85),
    "30:ae:a4": ("Espressif", "iot-microcontroller", 0.85),
    "ac:67:b2": ("Espressif", "iot-microcontroller", 0.85),
    "bc:dd:c2": ("Espressif", "iot-microcontroller", 0.85),
    "ec:62:60": ("Espressif", "iot-microcontroller", 0.85),
    "70:b8:f6": ("Espressif", "iot-microcontroller", 0.85),
    "84:0d:8e": ("Espressif", "iot-microcontroller", 0.85),

    # Raspberry Pi Trading Ltd
    "b8:27:eb": ("Raspberry Pi", "iot-microcontroller", 0.85),
    "dc:a6:32": ("Raspberry Pi", "iot-microcontroller", 0.85),
    "d8:3a:dd": ("Raspberry Pi", "iot-microcontroller", 0.85),
    "e4:5f:01": ("Raspberry Pi", "iot-microcontroller", 0.85),
    "28:cd:c1": ("Raspberry Pi", "iot-microcontroller", 0.85),

    # Cisco / Linksys
    "00:14:bf": ("Linksys", "router-ap", 0.95),
    "c0:56:27": ("Linksys", "router-ap", 0.95),
    "e0:46:9a": ("Linksys", "router-ap", 0.95),
    "f4:6b:ef": ("Linksys", "router-ap", 0.95),

    # Netgear
    "00:09:5b": ("Netgear", "router-ap", 0.95),
    "00:11:50": ("Netgear", "router-ap", 0.95),
    "00:14:04": ("Netgear", "router-ap", 0.95),
    "08:02:8e": ("Netgear", "router-ap", 0.95),
    "20:4e:7f": ("Netgear", "router-ap", 0.95),

    # Arris / CommScope
    "00:15:d1": ("Arris", "router-ap", 0.95),
    "00:1d:d3": ("Arris", "router-ap", 0.95),
    "20:73:55": ("Arris", "router-ap", 0.95),
    "94:87:70": ("Arris", "router-ap", 0.95),

    # TP-Link
    "50:c7:bf": ("TP-Link", "router-ap", 0.95),
    "60:32:b1": ("TP-Link", "router-ap", 0.95),
    "98:48:27": ("TP-Link", "router-ap", 0.95),
    "ac:84:c6": ("TP-Link", "router-ap", 0.95),

    # Ubiquiti
    "00:1a:22": ("Ubiquiti", "router-ap", 0.95),
    "00:26:4a": ("Ubiquiti", "router-ap", 0.95),
    "78:8a:20": ("Ubiquiti", "router-ap", 0.95),

    # Philips Lighting
    "00:17:88": ("Philips Lighting", "smart-home", 0.90),
    "ec:b5:fa": ("Philips Lighting", "smart-home", 0.90),

    # Amazon
    "00:24:e4": ("Amazon", "smart-home", 0.85),
    "44:65:0d": ("Amazon", "smart-home", 0.85),
    "a0:02:dc": ("Amazon", "smart-home", 0.85),
    "3c:5c:c4": ("Amazon", "smart-home", 0.85),

    # Apple
    "00:03:93": ("Apple", "mobile-personal", 0.80),
    "00:1e:c2": ("Apple", "mobile-personal", 0.80),
    "fc:65:de": ("Apple", "mobile-personal", 0.80),
    "f0:99:b6": ("Apple", "mobile-personal", 0.80),
    "a4:c3:61": ("Apple", "mobile-personal", 0.80),

    # Samsung
    "00:12:fb": ("Samsung", "mobile-personal", 0.80),
    "00:15:99": ("Samsung", "mobile-personal", 0.80),
    "00:17:c4": ("Samsung", "mobile-personal", 0.80),
    "00:21:19": ("Samsung", "mobile-personal", 0.80),
}

# BLE SIG 16-bit Company Identifiers: maps 4-char hex string to (manufacturer, default_signature)
BLE_COMPANY_TABLE = {
    "004c": ("Apple", "mobile-personal"),
    "0075": ("Samsung", "mobile-personal"),
    "0006": ("Microsoft", "mobile-personal"),
    "6068": ("Sony", "audio-peripheral"),
    "06d0": ("Levoit / VeSync", "smart-home"),
    "06a8": ("Tencent", "mobile-personal"),
    "012d": ("Sony Video", "audio-peripheral"),
    "02d2": ("Espressif", "iot-microcontroller"),
    "000a": ("Qualcomm", "audio-peripheral"),
    "0059": ("Nordic Semi", "iot-microcontroller"),
    "00e0": ("Google", "mobile-personal"),
    "0157": ("Huami / Amazfit", "mobile-personal"),
    "0087": ("Garmin", "mobile-personal"),
}

# Substring Keyword Rules: (keyword, manufacturer_override, signature, confidence)
KEYWORD_RULES = [
    # Audio peripherals
    ("WH-", "Sony", "audio-peripheral", 0.95),
    ("WF-", "Sony", "audio-peripheral", 0.95),
    ("WI-", "Sony", "audio-peripheral", 0.95),
    ("AirPods", "Apple", "audio-peripheral", 0.95),
    ("Beats", "Apple / Beats", "audio-peripheral", 0.95),
    ("Bose", "Bose", "audio-peripheral", 0.95),
    ("JBL", "JBL", "audio-peripheral", 0.95),
    ("Buds", None, "audio-peripheral", 0.90),
    ("Headphone", None, "audio-peripheral", 0.90),

    # Smart home appliances
    ("LAP-", "Levoit / VeSync", "smart-home", 0.90),
    ("Core 200S", "Levoit / VeSync", "smart-home", 0.90),
    ("Core 300", "Levoit / VeSync", "smart-home", 0.90),
    ("Purifier", None, "smart-home", 0.85),
    ("MATTER", None, "smart-home", 0.90),
    ("Plug", None, "smart-home", 0.80),
    ("Socket", None, "smart-home", 0.80),
    ("Switch", None, "smart-home", 0.80),
    ("Bulb", None, "smart-home", 0.80),

    # Wearable & fitness
    ("Fitbit", "Google Fitbit", "mobile-personal", 0.90),
    ("Garmin", "Garmin", "mobile-personal", 0.90),
    ("Watch", None, "mobile-personal", 0.85),
    ("Band", None, "mobile-personal", 0.80),

    # IoT Development Boards
    ("ESP32", "Espressif", "iot-microcontroller", 0.95),
    ("ESP8266", "Espressif", "iot-microcontroller", 0.95),
    ("Pico", "Raspberry Pi", "iot-microcontroller", 0.95),
    ("Arduino", "Arduino", "iot-microcontroller", 0.95),
]


def classify(observation):
    """Analyze observation and return (manufacturer, signature, confidence).

    Guaranteed deterministic: identical inputs yield identical outputs (AC-18).
    Never invents models or brands (AC-19).
    Returns confidence between 0.0 and 1.0 (AC-20).
    """
    address = (observation.get("address") or "").lower().strip()
    ssid = (observation.get("ssid") or "").strip()
    radio = (observation.get("radio") or "").lower().strip()
    mfg_raw = (observation.get("manufacturer") or "").lower().strip()
    connectable = observation.get("connectable")

    # 1. Check OUI prefix (first 8 chars: "xx:xx:xx")
    oui_mfg, oui_sig, oui_conf = None, None, None
    if len(address) >= 8:
        prefix = address[:8]
        if prefix in OUI_TABLE:
            oui_mfg, oui_sig, oui_conf = OUI_TABLE[prefix]

    # 2. Check BLE SIG Company ID
    ble_mfg, ble_sig = None, None
    if mfg_raw in BLE_COMPANY_TABLE:
        ble_mfg, ble_sig = BLE_COMPANY_TABLE[mfg_raw]

    # 3. Check Keyword Rules against SSID / Local Name
    kw_mfg, kw_sig, kw_conf = None, None, None
    if ssid:
        for keyword, mfg_override, sig, conf in KEYWORD_RULES:
            if keyword in ssid:
                kw_mfg = mfg_override
                kw_sig = sig
                kw_conf = conf
                break

    # 4. Multi-Signal Synthesis
    if kw_sig:
        manufacturer = kw_mfg or ble_mfg or oui_mfg or "unknown"
        return manufacturer, kw_sig, kw_conf

    if radio == "ble":
        if ble_mfg:
            manufacturer = ble_mfg
            if ble_mfg in ("Apple", "Samsung"):
                # Non-connectable advertisement with empty name behaves as a tracking/presence beacon
                if connectable is False and not ssid:
                    return manufacturer, "tracking-beacon", 0.75
                return manufacturer, "mobile-personal", 0.70
            return manufacturer, ble_sig, 0.85

        if oui_mfg:
            return oui_mfg, oui_sig, oui_conf

        # AC-19: Unrecognized BLE broadcast
        return "unknown", "unknown", 0.0

    if radio == "wifi":
        if oui_mfg:
            return oui_mfg, oui_sig, oui_conf
        # An observed 802.11 beacon frame from an unknown OUI is inherently an Access Point
        return "unknown", "router-ap", 0.60

    if oui_mfg:
        return oui_mfg, oui_sig, oui_conf

    return "unknown", "unknown", 0.0


def enrich_observation(observation):
    """Mutate and return observation with manufacturer, signature, and confidence."""
    mfg, sig, conf = classify(observation)
    observation["manufacturer"] = mfg
    observation["signature"] = sig
    observation["confidence"] = conf
    return observation
