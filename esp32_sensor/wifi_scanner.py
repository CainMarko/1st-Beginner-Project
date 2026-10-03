"""Wi-Fi scanner module for ESP32 field sensing nodes.

Performs 2.4 GHz passive channel scanning and normalizes detected networks
into standard observations.
"""

import observation

try:
    import time
except ImportError:
    pass


def parse_scan_tuple(scan_tuple, node_id, timestamp=0):
    """Parse a single MicroPython wlan.scan() tuple into a standardized observation.

    MicroPython wlan.scan() returns:
        (ssid, bssid, channel, RSSI, authmode, hidden)
    """
    ssid_bytes = scan_tuple[0]
    bssid_bytes = scan_tuple[1]
    channel = scan_tuple[2]
    rssi = scan_tuple[3]

    if isinstance(ssid_bytes, (bytes, bytearray)):
        ssid = ssid_bytes.decode("utf-8", "replace")
    else:
        ssid = str(ssid_bytes)

    return observation.create_wifi_observation(
        node_id=node_id,
        address=bssid_bytes,
        ssid=ssid,
        rssi=rssi,
        channel=channel,
        timestamp=timestamp
    )


def scan_networks(wlan, node_id, timestamp=0):
    """Scan nearby Wi-Fi networks and return a list of standardized observations."""
    try:
        raw_results = wlan.scan()
    except Exception as e:
        print("Wi-Fi scan error:", e)
        return []

    observations = []
    for item in raw_results:
        try:
            obs = parse_scan_tuple(item, node_id, timestamp=timestamp)
            observations.append(obs)
        except Exception as e:
            print("Error parsing scan item:", e)

    return observations
