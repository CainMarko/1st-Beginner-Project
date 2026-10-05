"""Tests for the LoRa SX1262 driver and GNSS L76 driver.

These run on the dev machine (CPython), not on the ESP32. They test
parsing logic and config correctness; hardware SPI/UART is mocked.
"""

import sys
import struct
import unittest
from pathlib import Path

# Add project dirs to sys.path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "esp32_sensor_lora"))


class ConfigTests(unittest.TestCase):
    """Verify config pin assignments match the Heltec V4 S3R2 pinout."""

    def test_lora_pins_match_heltec_v4(self):
        import config
        self.assertEqual(config.LORA_NSS, 8)
        self.assertEqual(config.LORA_SCK, 9)
        self.assertEqual(config.LORA_MOSI, 10)
        self.assertEqual(config.LORA_MISO, 11)
        self.assertEqual(config.LORA_RST, 12)
        self.assertEqual(config.LORA_BUSY, 13)
        self.assertEqual(config.LORA_DIO1, 14)

    def test_gnss_pins_match_heltec_v4(self):
        import config
        self.assertEqual(config.GNSS_RX_PIN, 39)  # ESP RX = GNSS TX
        self.assertEqual(config.GNSS_TX_PIN, 38)  # ESP TX = GNSS RX
        self.assertEqual(config.GNSS_RST_PIN, 42)
        self.assertEqual(config.GNSS_POWER_PIN, 34)

    def test_lora_params_sane(self):
        import config
        self.assertEqual(config.LORA_FREQUENCY, 915_000_000)
        self.assertIn(config.LORA_SPREADING_FACTOR, range(7, 13))
        self.assertIn(config.LORA_BANDWIDTH, [125000, 250000, 500000])
        self.assertGreater(config.LORA_TX_POWER, 0)
        self.assertLessEqual(config.LORA_TX_POWER, 28)


class GNSSParseTests(unittest.TestCase):
    """Test NMEA parsing logic without hardware."""

    def _make_gnss(self):
        """Create a GNSS instance with mocked machine module."""
        # We can't import gnss_driver normally because it imports machine.
        # Instead, parse the NMEA parsing methods directly.
        import importlib
        import types

        # Create a fake machine module
        fake_machine = types.ModuleType("machine")
        Pin = type("Pin", (), {
            "OUT": 1, "IN": 0,
            "__init__": lambda self, *a, **k: None,
            "value": lambda self, *a: 0,
        })
        fake_machine.Pin = Pin
        fake_machine.UART = type("UART", (), {
            "__init__": lambda self, *a, **k: None,
            "readline": lambda self: None,
        })
        sys.modules["machine"] = fake_machine

        # Force reimport
        if "gnss_driver" in sys.modules:
            del sys.modules["gnss_driver"]
        import gnss_driver
        importlib.reload(gnss_driver)

        gps = gnss_driver.GNSS()
        return gps, gnss_driver

    def test_parse_gga_valid_fix(self):
        gps, _ = self._make_gnss()
        # $GPGGA,time,lat,N,lon,E,fix_quality,sats,hdop,alt,M,...
        sentence = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
        gps._parse(sentence)

        self.assertTrue(gps.has_fix)
        self.assertEqual(gps._latitude, round(48 + 7.038/60, 6))
        self.assertEqual(gps._longitude, round(11 + 31.0/60, 6))
        self.assertEqual(gps._satellites, 8)
        self.assertAlmostEqual(gps._hdop, 0.9)
        self.assertAlmostEqual(gps._altitude, 545.4)

    def test_parse_gga_no_fix(self):
        gps, _ = self._make_gnss()
        sentence = "$GPGGA,123519,,,,,0,00,99.0,,,,,,*48"
        gps._parse(sentence)
        self.assertFalse(gps.has_fix)
        self.assertIsNone(gps._latitude)

    def test_parse_rmc_active(self):
        gps, _ = self._make_gnss()
        sentence = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
        gps._parse(sentence)

        self.assertTrue(gps.has_fix)
        self.assertEqual(gps._latitude, round(48 + 7.038/60, 6))
        self.assertEqual(gps._longitude, round(11 + 31.0/60, 6))
        self.assertAlmostEqual(gps._speed, 22.4)
        self.assertAlmostEqual(gps._course, 84.4)
        self.assertIsNotNone(gps._datetime)
        self.assertEqual(gps._datetime, (1994, 3, 23, 12, 35, 19))

    def test_parse_rmc_void(self):
        gps, _ = self._make_gnss()
        sentence = "$GPRMC,123519,V,,,,,,,230394,,*33"
        gps._parse(sentence)
        self.assertFalse(gps.has_fix)

    def test_parse_coord_south_west(self):
        gps, _ = self._make_gnss()
        result = gps._parse_coord("4807.038", "S")
        self.assertAlmostEqual(result, round(-(48 + 7.038/60), 6))
        result = gps._parse_coord("01131.000", "W")
        self.assertAlmostEqual(result, round(-(11 + 31.0/60), 6))

    def test_parse_coord_empty(self):
        gps, _ = self._make_gnss()
        self.assertIsNone(gps._parse_coord("", "N"))
        self.assertIsNone(gps._parse_coord("4807.038", ""))

    def test_parse_gsv_satellite_count(self):
        gps, _ = self._make_gnss()
        # Last message in a GSV sequence reports total sats in view
        # $GPGSV,total_msgs,msg_num,sats_in_view,...
        sentence = "$GPGSV,3,3,11,22,42,087,45,24,14,023,35,25,40,120,40*7A"
        gps._parse(sentence)
        self.assertEqual(gps.satellites, 11)

    def test_parse_datetime(self):
        gps, _ = self._make_gnss()
        dt = gps._parse_datetime("123519", "230394")
        self.assertEqual(dt, (1994, 3, 23, 12, 35, 19))

    def test_parse_datetime_empty(self):
        gps, _ = self._make_gnss()
        self.assertIsNone(gps._parse_datetime("", ""))
        self.assertIsNone(gps._parse_datetime("abc", "xyz"))

    def tearDown(self):
        # Clean up mocked machine module
        if "machine" in sys.modules:
            del sys.modules["machine"]
        if "gnss_driver" in sys.modules:
            del sys.modules["gnss_driver"]


class PayloadTests(unittest.TestCase):
    """Test the unified main app's payload builder."""

    def test_build_payload_with_fix_and_wifi(self):
        # Mock the imports needed by lora_gnss_main
        import types
        fake_machine = types.ModuleType("machine")
        sys.modules["machine"] = fake_machine

        if "lora_driver" in sys.modules:
            del sys.modules["lora_driver"]
        if "gnss_driver" in sys.modules:
            del sys.modules["gnss_driver"]
        if "lora_gnss_main" in sys.modules:
            del sys.modules["lora_gnss_main"]

        import lora_gnss_main

        gnss_loc = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 10.5,
            "satellites": 9,
        }
        wifi_obs = [
            {"address": "aa:bb:cc:dd:ee:ff", "rssi": -50, "signature": "router-ap"},
            {"address": "11:22:33:44:55:66", "rssi": -70, "signature": "iot-mcu"},
        ]

        payload = lora_gnss_main.build_payload(gnss_loc, wifi_obs, 1760000000)

        self.assertEqual(payload["n"], "esp32-lora-01")
        self.assertEqual(payload["t"], 1760000000)
        self.assertEqual(payload["lat"], 40.7128)
        self.assertEqual(payload["lon"], -74.0060)
        self.assertEqual(payload["sats"], 9)
        self.assertEqual(payload["wifi_n"], 2)
        self.assertEqual(len(payload["wifi_top"]), 2)
        # Strongest first
        self.assertEqual(payload["wifi_top"][0]["r"], -50)

    def test_build_payload_no_fix(self):
        import types
        fake_machine = types.ModuleType("machine")
        sys.modules["machine"] = fake_machine

        for mod in ("lora_driver", "gnss_driver", "lora_gnss_main"):
            if mod in sys.modules:
                del sys.modules[mod]

        import lora_gnss_main
        payload = lora_gnss_main.build_payload(None, [], 1234567890)

        self.assertEqual(payload["lat"], None)
        self.assertEqual(payload["lon"], None)
        self.assertNotIn("wifi_n", payload)

    def tearDown(self):
        for mod in ("machine", "lora_driver", "gnss_driver", "lora_gnss_main"):
            if mod in sys.modules:
                del sys.modules[mod]


if __name__ == "__main__":
    unittest.main()
