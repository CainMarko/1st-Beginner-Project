"""Standard observation schema builder for Fieldwatch sensing nodes.

Generates schema version 1 dictionaries for radio observations.
"""

def format_bssid(bssid):
    """Format BSSID bytes, bytearray, or string into lowercase colon-separated hex."""
    if isinstance(bssid, (bytes, bytearray)):
        return ":".join("%02x" % b for b in bssid)
    if isinstance(bssid, str):
        return bssid.strip().lower()
    return ""


def create_wifi_observation(
    node_id,
    address,
    ssid="",
    rssi=None,
    channel=None,
    timestamp=0,
    manufacturer="",
    signature="",
    confidence=None,
    latitude=None,
    longitude=None
):
    """Create a standardized Wi-Fi observation conforming to Schema v1."""
    return {
        "schema_version": 1,
        "node_id": str(node_id),
        "timestamp": int(timestamp) if timestamp is not None else 0,
        "radio": "wifi",
        "address": format_bssid(address),
        "rssi": int(rssi) if rssi is not None else None,
        "channel": int(channel) if channel is not None else None,
        "ssid": str(ssid) if ssid is not None else "",
        "manufacturer": str(manufacturer) if manufacturer is not None else "",
        "signature": str(signature) if signature is not None else "",
        "confidence": float(confidence) if confidence is not None else None,
        "latitude": latitude,
        "longitude": longitude
    }


def create_ble_observation(
    node_id,
    address,
    rssi=None,
    name="",
    manufacturer="",
    timestamp=0,
    signature="",
    confidence=None,
    connectable=None,
    latitude=None,
    longitude=None
):
    """Create a standardized BLE observation conforming to Schema v1."""
    return {
        "schema_version": 1,
        "node_id": str(node_id),
        "timestamp": int(timestamp) if timestamp is not None else 0,
        "radio": "ble",
        "address": format_bssid(address),
        "rssi": int(rssi) if rssi is not None else None,
        "channel": None,
        "ssid": str(name) if name is not None else "",
        "manufacturer": str(manufacturer) if manufacturer is not None else "",
        "signature": str(signature) if signature is not None else "",
        "confidence": float(confidence) if confidence is not None else None,
        "connectable": bool(connectable) if connectable is not None else None,
        "latitude": latitude,
        "longitude": longitude
    }



