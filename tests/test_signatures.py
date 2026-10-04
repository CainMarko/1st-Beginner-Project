import sys
import unittest
from pathlib import Path

# Add project root and esp32_sensor directory to sys.path
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir / "esp32_sensor"))

import signatures


class SignaturesTests(unittest.TestCase):
    def test_ac18_deterministic_signature_generation(self):
        """AC-18: Same input characteristics produce identical signatures across 100 runs."""
        test_obs = {
            "schema_version": 1,
            "node_id": "esp32-001",
            "radio": "ble",
            "address": "a8:e6:e8:d0:6b:74",
            "ssid": "WH-CH720N",
            "manufacturer": "6068",
            "connectable": True
        }
        first_result = signatures.classify(test_obs)
        for _ in range(100):
            result = signatures.classify(test_obs)
            self.assertEqual(result, first_result)

    def test_ac19_unknown_device_handling(self):
        """AC-19: Unrecognized devices receive explicit unknown classification without inventing identities."""
        unknown_obs = {
            "schema_version": 1,
            "node_id": "esp32-001",
            "radio": "ble",
            "address": "da:11:22:33:44:55",  # Locally administered / random MAC
            "ssid": "",
            "manufacturer": "",
            "connectable": False
        }
        mfg, sig, conf = signatures.classify(unknown_obs)
        self.assertEqual(mfg, "unknown")
        self.assertEqual(sig, "unknown")
        self.assertEqual(conf, 0.0)

    def test_ac20_confidence_bounds(self):
        """AC-20: Classifications produce a confidence value between 0.0 and 1.0."""
        test_cases = [
            {"radio": "wifi", "address": "b8:f8:53:11:22:33", "ssid": "Fios-4ZxCR"},
            {"radio": "ble", "address": "cd:5c:e1:5b:37:b4", "manufacturer": "004c", "connectable": False},
            {"radio": "ble", "address": "98:88:e0:df:e1:1a", "ssid": "LAP-V102S-WUS", "manufacturer": "06d0"},
            {"radio": "wifi", "address": "00:99:88:77:66:55", "ssid": "RandomAP"},
            {"radio": "ble", "address": "12:34:56:78:9a:bc", "ssid": "Google Fitbit Air"}
        ]
        for obs in test_cases:
            _, _, conf = signatures.classify(obs)
            self.assertGreaterEqual(conf, 0.0)
            self.assertLessEqual(conf, 1.0)

    def test_oui_classification_router_ap(self):
        obs = {"radio": "wifi", "address": "b8:f8:53:aa:bb:cc", "ssid": "Fios-Test"}
        mfg, sig, conf = signatures.classify(obs)
        self.assertEqual(mfg, "Actiontec")
        self.assertEqual(sig, "router-ap")
        self.assertEqual(conf, 0.95)

    def test_oui_classification_espressif(self):
        obs = {"radio": "wifi", "address": "24:4c:ab:11:22:33", "ssid": "IoT-Device"}
        mfg, sig, conf = signatures.classify(obs)
        self.assertEqual(mfg, "Espressif")
        self.assertEqual(sig, "iot-microcontroller")
        self.assertEqual(conf, 0.85)

    def test_ble_sig_company_apple_beacon(self):
        obs = {"radio": "ble", "address": "aa:bb:cc:11:22:33", "manufacturer": "004c", "ssid": "", "connectable": False}
        mfg, sig, conf = signatures.classify(obs)
        self.assertEqual(mfg, "Apple")
        self.assertEqual(sig, "tracking-beacon")
        self.assertEqual(conf, 0.75)

    def test_ble_sig_company_apple_mobile(self):
        obs = {"radio": "ble", "address": "aa:bb:cc:11:22:33", "manufacturer": "004c", "ssid": "", "connectable": True}
        mfg, sig, conf = signatures.classify(obs)
        self.assertEqual(mfg, "Apple")
        self.assertEqual(sig, "mobile-personal")
        self.assertEqual(conf, 0.70)

    def test_keyword_smart_home_purifier(self):
        obs = {"radio": "ble", "address": "98:88:e0:df:e1:1a", "ssid": "LAP-V102S-WUS", "manufacturer": "06d0"}
        mfg, sig, conf = signatures.classify(obs)
        self.assertEqual(mfg, "Levoit / VeSync")
        self.assertEqual(sig, "smart-home")
        self.assertEqual(conf, 0.90)

    def test_keyword_audio_headphones(self):
        obs = {"radio": "ble", "address": "a8:e6:e8:d0:6b:74", "ssid": "WH-CH720N", "manufacturer": "6068"}
        mfg, sig, conf = signatures.classify(obs)
        self.assertEqual(mfg, "Sony")
        self.assertEqual(sig, "audio-peripheral")
        self.assertEqual(conf, 0.95)

    def test_wifi_generic_beacon_fallback(self):
        obs = {"radio": "wifi", "address": "12:34:56:78:9a:bc", "ssid": "SomeNeighborWifi"}
        mfg, sig, conf = signatures.classify(obs)
        self.assertEqual(mfg, "unknown")
        self.assertEqual(sig, "router-ap")
        self.assertEqual(conf, 0.60)

    def test_enrich_observation(self):
        obs = {
            "schema_version": 1,
            "node_id": "esp32-001",
            "radio": "ble",
            "address": "a8:e6:e8:d0:6b:74",
            "ssid": "WH-CH720N",
            "manufacturer": "6068"
        }
        enriched = signatures.enrich_observation(obs)
        self.assertEqual(enriched["manufacturer"], "Sony")
        self.assertEqual(enriched["signature"], "audio-peripheral")
        self.assertEqual(enriched["confidence"], 0.95)


if __name__ == "__main__":
    unittest.main()
