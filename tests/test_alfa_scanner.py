"""Unit tests for ALFA Dual-Band Scanner and Channel Handling."""
import os
import tempfile
import unittest
from pathlib import Path

import sys
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))

from collector.database import Database
from collector.alfa_scanner import parse_netsh_output


MOCK_NETSH_OUTPUT = """
Interface name : Wi-Fi 2 
There are 2 networks currently visible. 

SSID 1 : Test2G_Router
    Network type            : Infrastructure
    Authentication          : WPA2-Personal
    Encryption              : CCMP 
    BSSID 1                 : 00:14:bf:11:22:33
         Signal             : 80%  
         Radio type         : 802.11n
         Band               : 2.4 GHz
         Channel            : 6 

SSID 2 : Test5G_Network
    Network type            : Infrastructure
    Authentication          : WPA2-Personal
    Encryption              : CCMP 
    BSSID 1                 : b8:f8:53:aa:bb:cc
         Signal             : 90%  
         Radio type         : 802.11ax
         Band               : 5 GHz
         Channel            : 149 
"""


class AlfaScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_alfa.db")
        self.db = Database(self.db_path)
        self.db.init_schema()

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_parse_netsh_output(self):
        obs = parse_netsh_output(MOCK_NETSH_OUTPUT, node_id="laptop-alfa-01", timestamp=1760000000)
        self.assertEqual(len(obs), 2)

        # 2.4 GHz observation
        dev1 = obs[0]
        self.assertEqual(dev1["address"], "00:14:bf:11:22:33")
        self.assertEqual(dev1["ssid"], "Test2G_Router")
        self.assertEqual(dev1["channel"], 6)
        self.assertEqual(dev1["rssi"], -60)  # (80 / 2) - 100 = -60
        self.assertEqual(dev1["radio"], "wifi")
        self.assertEqual(dev1["signature"], "router-ap")
        self.assertEqual(dev1["manufacturer"], "Linksys")

        # 5 GHz observation
        dev2 = obs[1]
        self.assertEqual(dev2["address"], "b8:f8:53:aa:bb:cc")
        self.assertEqual(dev2["ssid"], "Test5G_Network")
        self.assertEqual(dev2["channel"], 149)
        self.assertEqual(dev2["rssi"], -55)  # (90 / 2) - 100 = -55
        self.assertEqual(dev2["radio"], "wifi")
        self.assertEqual(dev2["signature"], "router-ap")
        self.assertEqual(dev2["manufacturer"], "Actiontec")

    def test_database_stores_channel_and_band_filtering(self):
        obs = parse_netsh_output(MOCK_NETSH_OUTPUT, node_id="laptop-alfa-01", timestamp=1760000000)
        inserted = self.db.insert_batch(obs)
        self.assertEqual(inserted, 2)

        stats = self.db.get_stats()
        self.assertEqual(stats["total_devices"], 2)
        self.assertEqual(stats["ghz2_devices"], 1)
        self.assertEqual(stats["ghz5_devices"], 1)

        # Filter 2.4 GHz
        devs_2g = self.db.get_devices(band="2.4g")
        self.assertEqual(len(devs_2g), 1)
        self.assertEqual(devs_2g[0]["last_channel"], 6)

        # Filter 5 GHz
        devs_5g = self.db.get_devices(band="5g")
        self.assertEqual(len(devs_5g), 1)
        self.assertEqual(devs_5g[0]["last_channel"], 149)


if __name__ == "__main__":
    unittest.main()
