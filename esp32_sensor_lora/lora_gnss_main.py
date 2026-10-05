"""Unified LoRa/GNSS node application for the Heltec WiFi LoRa 32 V4.

Periodically collects GNSS location data, packages it into a compact JSON
message, and transmits via LoRa. Also runs Wi-Fi scans when possible and
includes RF observations in the LoRa payload for the collector to ingest.

Designed to run as main.py on the ESP32-S3.
"""

import time
import json
import gc

import config
from lora_driver import SX1262
from gnss_driver import GNSS

# Optional: Wi-Fi scanning (reuses the existing sensor codebase)
try:
    import network
    import wifi_scanner
    import observation
    import signatures
    _WIFI_AVAILABLE = True
except ImportError:
    _WIFI_AVAILABLE = False

# Optional: secrets
try:
    import secrets
except ImportError:
    secrets = None


def collect_wifi_observations(timestamp):
    """Run a Wi-Fi scan if WLAN is available. Returns list of observations."""
    if not _WIFI_AVAILABLE:
        return []
    try:
        wlan = network.WLAN(network.STA_IF)
        if not wlan.active():
            wlan.active(True)
        obs_list = wifi_scanner.scan_networks(wlan, node_id=config.NODE_ID, timestamp=timestamp)
        for obs in obs_list:
            signatures.enrich_observation(obs)
        return obs_list
    except Exception as e:
        print("Wi-Fi scan error:", e)
        return []


def build_payload(gnss_loc, wifi_obs, timestamp):
    """Build a compact JSON payload for LoRa transmission.

    LoRa payloads should stay small (<128 bytes) for reliable delivery.
    We send: node_id, timestamp, lat, lon, alt, sats, and a summary of
    Wi-Fi devices seen (count + top 3 by RSSI).
    """
    payload = {
        "n": config.NODE_ID,
        "t": timestamp,
    }

    if gnss_loc:
        payload["lat"] = gnss_loc["latitude"]
        payload["lon"] = gnss_loc["longitude"]
        if gnss_loc["altitude"] is not None:
            payload["alt"] = gnss_loc["altitude"]
        payload["sats"] = gnss_loc["satellites"]
    else:
        payload["lat"] = None
        payload["lon"] = None

    if wifi_obs:
        # Compact summary: total count + strongest 3
        payload["wifi_n"] = len(wifi_obs)
        # Sort by RSSI (strongest first) and take top 3
        sorted_obs = sorted(wifi_obs, key=lambda o: o.get("rssi") or -999, reverse=True)
        top3 = []
        for obs in sorted_obs[:3]:
            top3.append({
                "a": obs.get("address", ""),
                "r": obs.get("rssi"),
                "s": obs.get("signature", ""),
            })
        payload["wifi_top"] = top3

    return payload


def main():
    print("=== LoRa/GNSS Node starting ===")
    print("Node ID:", config.NODE_ID)
    print("LoRa freq:", config.LORA_FREQUENCY // 1_000_000, "MHz")

    # Initialise LoRa radio
    radio = SX1262()
    radio.init()

    # Initialise GNSS
    gps = GNSS()
    gps.power_on()

    cycle = 0
    while True:
        cycle += 1
        print("\n--- Cycle %d ---" % cycle)
        timestamp = int(time.time())

        # 1. Get GNSS fix (with timeout)
        print("GNSS: requesting fix...")
        loc = gps.get_location(timeout_ms=config.GNSS_FIX_TIMEOUT_MS)
        if loc:
            print("GNSS: fix OK — lat=%s lon=%s sats=%d"
                  % (loc["latitude"], loc["longitude"], loc["satellites"]))
        else:
            print("GNSS: no fix")

        # 2. Wi-Fi scan (optional, best-effort)
        wifi_obs = []
        if _WIFI_AVAILABLE:
            print("WiFi: scanning...")
            wifi_obs = collect_wifi_observations(timestamp)
            print("WiFi: found %d networks" % len(wifi_obs))

        # 3. Build and transmit LoRa payload
        payload = build_payload(loc, wifi_obs, timestamp)
        msg = json.dumps(payload, separators=(",", ":"))
        print("LoRa: TX payload (%d bytes):" % len(msg), msg)

        if len(msg) > 255:
            print("LoRa: payload too large (%d bytes), truncating..." % len(msg))
            msg = msg[:255]

        ok = radio.send(msg, timeout_ms=5000)
        if ok:
            print("LoRa: TX OK")
        else:
            print("LoRa: TX FAILED")

        # 4. Listen briefly for incoming commands (10s window)
        print("LoRa: listening for 10s...")
        rx = radio.receive(timeout_ms=10000)
        if rx is not None:
            print("LoRa: RX:", rx.decode("utf-8", "replace"))

        # 5. Sleep until next cycle
        gc.collect()
        print("Sleeping %ds..." % config.TELEMETRY_INTERVAL_SECONDS)
        time.sleep(config.TELEMETRY_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
