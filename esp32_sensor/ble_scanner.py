"""BLE Scanner module for ESP32 Fieldwatch Sensing Node.

Performs passive and active Bluetooth Low Energy scanning, decouples IRQ event
capture via an in-memory event queue, and decodes advertisement payloads into
standard Schema v1 observations (AC-16, AC-17).
"""

import observation

try:
    import time
except ImportError:
    time = None

try:
    import bluetooth
except ImportError:
    bluetooth = None

_IRQ_SCAN_RESULT = 5
_IRQ_SCAN_DONE = 6

_ADV_TYPE_NAME_SHORT = 0x08
_ADV_TYPE_NAME_COMPLETE = 0x09
_ADV_TYPE_MANUFACTURER_DATA = 0xFF


def decode_adv_payload(payload):
    """Decode BLE advertising data (L-T-V format) into (name, manufacturer_id_hex)."""
    if not payload:
        return "", ""

    name = ""
    mfg = ""
    idx = 0
    total_len = len(payload)

    while idx < total_len:
        length = payload[idx]
        if length == 0 or (idx + 1 + length) > total_len:
            break

        ad_type = payload[idx + 1]
        data = payload[idx + 2 : idx + 1 + length]

        if ad_type in (_ADV_TYPE_NAME_SHORT, _ADV_TYPE_NAME_COMPLETE):
            try:
                name = data.decode("utf-8", "replace")
            except Exception:
                pass
        elif ad_type == _ADV_TYPE_MANUFACTURER_DATA and len(data) >= 2:
            # 2-byte SIG Company ID is little-endian in BLE payloads
            mfg_id = data[0] | (data[1] << 8)
            mfg = "%04x" % mfg_id

        idx += 1 + length

    return name, mfg


def is_connectable(adv_type):
    """Determine whether an advertisement type indicates connectability.

    0: ADV_IND (connectable undirected)
    1: ADV_DIRECT_IND (connectable directed)
    2: ADV_SCAN_IND (scannable undirected)
    3: ADV_NONCONN_IND (non-connectable undirected)
    4: SCAN_RSP (scan response)
    """
    if adv_type is None:
        return None
    if adv_type in (0, 1):
        return True
    if adv_type in (2, 3):
        return False
    return None


def process_raw_events(raw_events, node_id, timestamp=0):
    """Drain raw BLE events and deduplicate by MAC address, keeping the strongest RSSI."""
    dedup = {}

    for event_item in raw_events:
        addr_bytes = event_item[0]
        rssi = event_item[1]
        adv_payload = event_item[2] if len(event_item) > 2 else b""
        adv_type = event_item[3] if len(event_item) > 3 else None

        addr_str = observation.format_bssid(addr_bytes)
        if not addr_str:
            continue

        c = is_connectable(adv_type)

        if addr_str in dedup:
            if rssi > dedup[addr_str]["rssi"]:
                dedup[addr_str]["rssi"] = rssi
            if not dedup[addr_str]["name"] and adv_payload:
                n, m = decode_adv_payload(adv_payload)
                if n:
                    dedup[addr_str]["name"] = n
                if m and not dedup[addr_str]["mfg"]:
                    dedup[addr_str]["mfg"] = m
            # If any advertisement packet in this window was connectable, mark True
            if c is True:
                dedup[addr_str]["connectable"] = True
            elif dedup[addr_str]["connectable"] is None and c is not None:
                dedup[addr_str]["connectable"] = c
        else:
            name, mfg = decode_adv_payload(adv_payload) if adv_payload else ("", "")
            dedup[addr_str] = {
                "address": addr_str,
                "rssi": rssi,
                "name": name,
                "mfg": mfg,
                "connectable": c
            }

    observations = []
    for item in dedup.values():
        obs = observation.create_ble_observation(
            node_id=node_id,
            address=item["address"],
            rssi=item["rssi"],
            name=item["name"],
            manufacturer=item["mfg"],
            connectable=item["connectable"],
            timestamp=timestamp
        )
        observations.append(obs)

    return observations


class BLEScanner:
    """Manages MicroPython bluetooth.BLE scanning lifecycle."""

    def __init__(self):
        self._ble = None
        self._raw_queue = []
        self._scan_done = False

    def _ble_irq(self, event, data):
        """MicroPython BLE interrupt handler. Keep allocations minimal!"""
        if event == _IRQ_SCAN_RESULT:
            # data: (addr_type, addr, adv_type, rssi, adv_data)
            addr = bytes(data[1])
            adv_type = data[2]
            rssi = data[3]
            adv_data = bytes(data[4]) if data[4] else b""
            self._raw_queue.append((addr, rssi, adv_data, adv_type))
        elif event == _IRQ_SCAN_DONE:
            self._scan_done = True


    def scan(self, duration_ms=5000, node_id="esp32-001", timestamp=0):
        """Execute a BLE scan window and return a list of Schema v1 observations."""
        if bluetooth is None:
            return []

        if self._ble is None:
            self._ble = bluetooth.BLE()

        if not self._ble.active():
            self._ble.active(True)

        self._ble.irq(self._ble_irq)
        self._raw_queue = []
        self._scan_done = False

        # interval 30ms, window 30ms (100% duty cycle), active=True (scan response)
        try:
            self._ble.gap_scan(duration_ms, 30000, 30000, True)
        except Exception as e:
            print("BLE scan error:", e)
            return []

        start_time = time.ticks_ms()
        # Wait for scan done event or timeout
        while not self._scan_done:
            if time.ticks_diff(time.ticks_ms(), start_time) > (duration_ms + 1000):
                try:
                    self._ble.gap_scan(None)  # Stop scan
                except Exception:
                    pass
                break
            time.sleep_ms(50)

        raw_events = self._raw_queue
        self._raw_queue = []

        try:
            self._ble.active(False)
        except Exception:
            pass

        return process_raw_events(raw_events, node_id, timestamp)
