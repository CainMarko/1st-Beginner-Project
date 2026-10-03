"""Status lines for the Pico heartbeat.

Hardware-free so the log format can be checked on a computer. The Pico reports
its own Wi-Fi link and its own messages.
"""

PLACEHOLDER_SSID = "your-network-name"
PLACEHOLDER_PASSWORD = "your-password"


class Counters:
    def __init__(self):
        self.tx_msgs = 0
        self.rx_msgs = 0
        self.tx_bytes = 0
        self.rx_bytes = 0


def wifi_configured(ssid, password):
    if not isinstance(ssid, str) or not isinstance(password, str):
        return False
    if ssid.strip() == "" or password == "":
        return False
    if ssid == PLACEHOLDER_SSID or password == PLACEHOLDER_PASSWORD:
        return False
    return True


def own_rssi(scan_rows, ssid):
    """Return the signal strength of ssid, or None.

    Other rows in scan_rows are ignored.
    """
    if not isinstance(ssid, str) or ssid == "":
        return None
    target = ssid.encode("utf-8")
    found = None
    for row in scan_rows:
        if not row or len(row) < 4:
            continue
        if row[0] == target:
            found = row[3]
    return found


def _format_line(ticks_ms, node, up, rssi, window, total):
    state = "WIFI_UP" if up else "WIFI_DOWN"
    rssi_text = "" if rssi is None else str(rssi)
    return "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s" % (
        ticks_ms,
        node,
        state,
        rssi_text,
        window.tx_msgs,
        window.rx_msgs,
        window.tx_bytes,
        window.rx_bytes,
        total.tx_msgs,
        total.rx_msgs,
        total.tx_bytes,
        total.rx_bytes,
    )


def status_line(ticks_ms, node, up, rssi, window, total):
    """Build one CSV line and count that line as outgoing traffic.

    The first four traffic fields are the 30-minute window. The last four are
    totals since boot. Both include this line and its newline.
    """
    window.tx_msgs += 1
    total.tx_msgs += 1
    base_window_bytes = window.tx_bytes
    base_total_bytes = total.tx_bytes
    line = ""
    while True:
        extra = len(line) + 1 if line else 0
        window.tx_bytes = base_window_bytes + extra
        total.tx_bytes = base_total_bytes + extra
        new_line = _format_line(ticks_ms, node, up, rssi, window, total)
        if new_line == line:
            return line
        line = new_line
