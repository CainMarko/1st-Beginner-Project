import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pico-hub"))

import report


class ReportTests(unittest.TestCase):
    def test_placeholder_wifi_is_not_configured(self):
        self.assertFalse(
            report.wifi_configured("your-network-name", "your-password")
        )
        self.assertFalse(report.wifi_configured("", "secret"))
        self.assertTrue(report.wifi_configured("Home", "secret"))

    def test_own_rssi_ignores_other_networks(self):
        rows = [
            (b"Neighbor", b"\x00", 1, -40, 0, 0),
            (b"Home", b"\x01", 6, -62, 0, 0),
            (b"Cafe", b"\x02", 11, -80, 0, 0),
        ]
        self.assertEqual(report.own_rssi(rows, "Home"), -62)
        self.assertIsNone(report.own_rssi(rows, "Missing"))

    def test_status_line_counts_itself(self):
        window = report.Counters()
        total = report.Counters()
        line = report.status_line(1000, "pico-hub", False, None, window, total)
        self.assertEqual(
            line,
            "1000,pico-hub,WIFI_DOWN,,1,0,%s,0,1,0,%s,0"
            % (len(line) + 1, len(line) + 1),
        )
        self.assertEqual(window.tx_bytes, len(line) + 1)
        self.assertEqual(total.tx_msgs, 1)

    def test_second_line_keeps_boot_total(self):
        window = report.Counters()
        total = report.Counters()
        first = report.status_line(1000, "pico-hub", True, -55, window, total)
        window.tx_msgs = 0
        window.rx_msgs = 0
        window.tx_bytes = 0
        window.rx_bytes = 0
        second = report.status_line(2000, "pico-hub", True, -55, window, total)
        self.assertTrue(second.startswith("2000,pico-hub,WIFI_UP,-55,1,0,"))
        self.assertEqual(total.tx_msgs, 2)
        self.assertEqual(total.tx_bytes, len(first) + 1 + len(second) + 1)


if __name__ == "__main__":
    unittest.main()
