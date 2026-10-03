"""Main entrypoint for ESP32 Fieldwatch Wi-Fi Sensing Node.

Periodically scans 2.4 GHz Wi-Fi channels, normalizes findings into standard
observations (schema v1), and transmits them via HTTP POST to the Pico W gateway.
Implements store-and-forward queuing to tolerate gateway outages (AC-15).
"""

import time
import socket
import json
import network
import gc

import config
import secrets
import observation
import wifi_scanner
import ble_scanner

# In-memory store-and-forward buffer
retry_queue = []

# BLE Scanner instance
ble = ble_scanner.BLEScanner()



def connect_wifi():
    """Ensure the ESP32 station interface is connected to the local network."""
    wlan = network.WLAN(network.STA_IF)
    if not wlan.active():
        wlan.active(True)

    if wlan.isconnected():
        return wlan, wlan.ifconfig()[0]

    try:
        country = getattr(secrets, "WIFI_COUNTRY", "US")
        if hasattr(network, "country"):
            network.country(country)
    except Exception:
        pass

    try:
        wlan.disconnect()
        time.sleep(0.5)
    except Exception:
        pass

    print("ESP32: Connecting to Wi-Fi", secrets.WIFI_SSID, "...")
    wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
    deadline = time.ticks_add(time.ticks_ms(), config.WIFI_TIMEOUT_SECONDS * 1000)
    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), deadline) > 0:
            print("ESP32: Wi-Fi connection timed out.")
            return wlan, None
        time.sleep(0.5)

    ip = wlan.ifconfig()[0]
    print("ESP32: Connected to Wi-Fi. IP:", ip)
    return wlan, ip


def post_observation(obs, host=config.GATEWAY_HOST, port=config.GATEWAY_PORT, path=config.GATEWAY_PATH):
    """Transmit a single observation via HTTP POST to the edge gateway."""
    payload = json.dumps(obs).encode("utf-8")
    s = socket.socket()
    s.settimeout(5.0)

    try:
        addr = socket.getaddrinfo(host, port)[0][-1]
        s.connect(addr)

        header = (
            "POST " + path + " HTTP/1.1\r\n"
            "Host: " + host + "\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: " + str(len(payload)) + "\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("utf-8")

        s.sendall(header + payload)

        # Read response status
        response = b""
        while True:
            chunk = s.recv(256)
            if not chunk:
                break
            response += chunk
            if b"\r\n\r\n" in response:
                break

        first_line = response.split(b"\r\n")[0].decode("utf-8", "ignore")
        if "200 OK" in first_line:
            return True, None
        return False, "Gateway returned: " + first_line

    except Exception as e:
        return False, str(e)
    finally:
        s.close()


def flush_queue():
    """Attempt to deliver all buffered observations to the gateway."""
    global retry_queue
    if not retry_queue:
        return 0

    print("ESP32: Flushing", len(retry_queue), "queued observations to gateway...")
    delivered = 0
    failed_index = -1

    for i, obs in enumerate(retry_queue):
        success, error = post_observation(obs)
        if success:
            delivered += 1
        else:
            print("ESP32: Delivery failed for observation", obs.get("address"), ":", error)
            failed_index = i
            break

    if failed_index >= 0:
        # Keep remaining un-sent items in the queue
        retry_queue = retry_queue[failed_index:]
    else:
        retry_queue = []

    print("ESP32: Delivered", delivered, "observations. Remaining in queue:", len(retry_queue))
    return delivered


def run_scan_cycle(wlan):
    """Execute interleaved Wi-Fi and BLE scans, then transmit results."""
    global retry_queue

    current_time = time.time()
    # MicroPython on RP2/ESP32 returns seconds since 2000-01-01 if RTC not synchronized
    timestamp = current_time

    print("\n--------------------------------------------------")
    print("ESP32: Starting Wi-Fi scan...")
    observations = wifi_scanner.scan_networks(wlan, node_id=config.NODE_ID, timestamp=timestamp)
    print("ESP32: Wi-Fi scan complete. Found", len(observations), "networks.")

    if getattr(config, "BLE_SCAN_ENABLED", False):
        scan_secs = getattr(config, "BLE_SCAN_DURATION_MS", 5000) // 1000
        print("ESP32: Starting BLE scan (" + str(scan_secs) + "s)...")
        ble_observations = ble.scan(
            duration_ms=getattr(config, "BLE_SCAN_DURATION_MS", 5000),
            node_id=config.NODE_ID,
            timestamp=timestamp
        )
        print("ESP32: BLE scan complete. Found", len(ble_observations), "devices.")
        observations.extend(ble_observations)

    # Enqueue new observations (capped at MAX_QUEUE_SIZE)
    for obs in observations:
        retry_queue.append(obs)
        if len(retry_queue) > config.MAX_QUEUE_SIZE:
            retry_queue.pop(0)

    print("ESP32: Total observations in buffer:", len(retry_queue))

    # Deliver to gateway
    flush_queue()
    gc.collect()



def main():
    print("ESP32 Fieldwatch Sensor Node starting up...")
    print("Node ID:", config.NODE_ID)
    print("Gateway:", config.GATEWAY_HOST, ":", config.GATEWAY_PORT)

    wlan, ip = connect_wifi()

    try:
        while True:
            # Reconnect Wi-Fi if dropped
            if not wlan.isconnected():
                print("ESP32: Wi-Fi dropped, reconnecting...")
                connect_wifi()

            run_scan_cycle(wlan)
            time.sleep(config.SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nESP32: Stopped by user.")


if __name__ == "__main__":
    main()
