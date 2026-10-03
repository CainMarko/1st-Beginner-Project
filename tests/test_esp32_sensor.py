import sys
import unittest
from pathlib import Path

# Add project root and esp32_sensor directory to sys.path
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir / "esp32_sensor"))

import observation
import wifi_scanner


class Esp32SensorTests(unittest.TestCase):
    def test_format_bssid_from_bytes(self):
        bssid_raw = b"\x12\x34\x56\x78\x9a\xbc"
        formatted = observation.format_bssid(bssid_raw)
        self.assertEqual(formatted, "12:34:56:78:9a:bc")

    def test_format_bssid_from_string(self):
        self.assertEqual(
            observation.format_bssid("AA:BB:CC:DD:EE:FF"),
            "aa:bb:cc:dd:ee:ff"
        )

    def test_create_wifi_observation_schema(self):
        obs = observation.create_wifi_observation(
            node_id="esp32-001",
            address="12:34:56:78:9a:bc",
            ssid="TestNetwork",
            rssi=-65,
            channel=6,
            timestamp=1760000000
        )
        self.assertEqual(obs["schema_version"], 1)
        self.assertEqual(obs["node_id"], "esp32-001")
        self.assertEqual(obs["timestamp"], 1760000000)
        self.assertEqual(obs["radio"], "wifi")
        self.assertEqual(obs["address"], "12:34:56:78:9a:bc")
        self.assertEqual(obs["rssi"], -65)
        self.assertEqual(obs["channel"], 6)
        self.assertEqual(obs["ssid"], "TestNetwork")

    def test_parse_scan_tuple(self):
        raw_tuple = (b"HomeWifi", b"\xaa\xbb\xcc\xdd\xee\xff", 1, -55, 3, False)
        obs = wifi_scanner.parse_scan_tuple(raw_tuple, node_id="esp32-001", timestamp=100)
        self.assertEqual(obs["ssid"], "HomeWifi")
        self.assertEqual(obs["address"], "aa:bb:cc:dd:ee:ff")
        self.assertEqual(obs["channel"], 1)
        self.assertEqual(obs["rssi"], -55)
        self.assertEqual(obs["node_id"], "esp32-001")
        self.assertEqual(obs["radio"], "wifi")

    def test_parse_scan_tuple_empty_or_hidden_ssid(self):
        raw_tuple = (b"", b"\x00\x11\x22\x33\x44\x55", 11, -82, 0, True)
        obs = wifi_scanner.parse_scan_tuple(raw_tuple, node_id="esp32-001", timestamp=200)
        self.assertEqual(obs["ssid"], "")
        self.assertEqual(obs["address"], "00:11:22:33:44:55")
        self.assertEqual(obs["channel"], 11)
        self.assertEqual(obs["rssi"], -82)

    def test_create_ble_observation_schema(self):
        obs = observation.create_ble_observation(
            node_id="esp32-001",
            address="AA:BB:CC:11:22:33",
            name="FitnessBand",
            rssi=-72,
            manufacturer="004c",
            timestamp=1760000500
        )
        self.assertEqual(obs["schema_version"], 1)
        self.assertEqual(obs["node_id"], "esp32-001")
        self.assertEqual(obs["timestamp"], 1760000500)
        self.assertEqual(obs["radio"], "ble")
        self.assertEqual(obs["address"], "aa:bb:cc:11:22:33")
        self.assertEqual(obs["rssi"], -72)
        self.assertIsNone(obs["channel"])
        self.assertEqual(obs["ssid"], "FitnessBand")
        self.assertEqual(obs["manufacturer"], "004c")
        self.assertEqual(obs["signature"], "")
        self.assertIsNone(obs["latitude"])
        self.assertIsNone(obs["longitude"])

    def test_create_ble_observation_defaults(self):
        obs = observation.create_ble_observation(
            node_id="esp32-001",
            address=b"\x01\x02\x03\x04\x05\x06"
        )
        self.assertEqual(obs["radio"], "ble")
        self.assertEqual(obs["address"], "01:02:03:04:05:06")
        self.assertEqual(obs["ssid"], "")
        self.assertEqual(obs["manufacturer"], "")
        self.assertIsNone(obs["rssi"])
        self.assertIsNone(obs["channel"])
        self.assertEqual(obs["timestamp"], 0)

    def test_decode_adv_payload_name_and_mfg(self):
        import ble_scanner
        # AD 1: Flags (len 2, type 0x01, data 0x06)
        # AD 2: Complete Local Name (len 7, type 0x09, "Beacon")
        # AD 3: Manufacturer Data (len 5, type 0xFF, company 0x004c, data 0x02, 0x15)
        payload = (
            b"\x02\x01\x06"
            b"\x07\x09Beacon"
            b"\x05\xff\x4c\x00\x02\x15"
        )
        name, mfg = ble_scanner.decode_adv_payload(payload)
        self.assertEqual(name, "Beacon")
        self.assertEqual(mfg, "004c")

    def test_decode_adv_payload_malformed_and_empty(self):
        import ble_scanner
        self.assertEqual(ble_scanner.decode_adv_payload(b""), ("", ""))
        self.assertEqual(ble_scanner.decode_adv_payload(b"\x05"), ("", ""))

    def test_process_raw_events_deduplication(self):
        import ble_scanner
        raw_events = [
            (b"\xaa\xbb\xcc\x11\x22\x33", -80, b"\x05\x08Tag1"),
            (b"\xaa\xbb\xcc\x11\x22\x33", -65, b"\x05\x08Tag1"),  # Stronger RSSI
            (b"\x11\x22\x33\x44\x55\x66", -70, b"")
        ]
        obs_list = ble_scanner.process_raw_events(raw_events, node_id="esp32-001", timestamp=100)
        self.assertEqual(len(obs_list), 2)
        tag1_obs = [o for o in obs_list if o["address"] == "aa:bb:cc:11:22:33"][0]
        self.assertEqual(tag1_obs["rssi"], -65)
        self.assertEqual(tag1_obs["ssid"], "Tag1")
        self.assertEqual(tag1_obs["radio"], "ble")
        self.assertEqual(tag1_obs["node_id"], "esp32-001")
        self.assertEqual(tag1_obs["timestamp"], 100)
        self.assertIsNone(tag1_obs["channel"])

    def test_create_ble_observation_connectable(self):
        obs = observation.create_ble_observation(
            node_id="esp32-001",
            address="11:22:33:44:55:66",
            connectable=True
        )
        self.assertTrue(obs.get("connectable"))

    def test_process_raw_events_connectable_types(self):
        import ble_scanner
        raw_events = [
            # ADV_IND (connectable)
            (b"\x01\x02\x03\x04\x05\x06", -70, b"", 0),
            # ADV_NONCONN_IND (broadcast only)
            (b"\x06\x05\x04\x03\x02\x01", -85, b"", 3),
            # ADV_SCAN_IND (scannable only)
            (b"\xaa\xbb\xcc\xdd\xee\xff", -60, b"", 2),
        ]
        obs_list = ble_scanner.process_raw_events(raw_events, node_id="esp32-001", timestamp=100)
        by_addr = {o["address"]: o for o in obs_list}
        self.assertTrue(by_addr["01:02:03:04:05:06"].get("connectable"))
        self.assertFalse(by_addr["06:05:04:03:02:01"].get("connectable"))
        self.assertFalse(by_addr["aa:bb:cc:dd:ee:ff"].get("connectable"))





if __name__ == "__main__":
    unittest.main()
