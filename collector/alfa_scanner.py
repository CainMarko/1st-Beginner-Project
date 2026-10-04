"""ALFA Dual-Band Wi-Fi Scanner Worker for Fieldwatch Central Collector.

Sweeps 2.4 GHz and 5 GHz spectrum using the ALFA AWUS036ACS USB adapter,
captures BSSIDs, signal strengths, channel allocations, and radio standards,
and enriches results with the Device Signature Engine.
"""

import logging
import os
import re
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

# Import Device Signature Engine
from esp32_sensor.signatures import enrich_observation
from .database import Database

logger = logging.getLogger("fieldwatch.alfa")


def find_alfa_interface() -> Optional[str]:
    """Auto-detects the Alfa adapter interface name in Windows."""
    try:
        out = subprocess.check_output(["netsh", "wlan", "show", "interfaces"], text=True, errors="replace")
        interfaces = []
        current_iface = {}

        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Name"):
                parts = line.split(":", 1)
                if len(parts) > 1:
                    current_iface["name"] = parts[1].strip()
            elif line.startswith("Description"):
                parts = line.split(":", 1)
                if len(parts) > 1:
                    current_iface["desc"] = parts[1].strip()
                    if "name" in current_iface:
                        interfaces.append(current_iface)
                        current_iface = {}

        # 1. Prefer interface with "Realtek", "RTL88", or "Alfa" in description
        for iface in interfaces:
            desc = iface.get("desc", "").lower()
            if "realtek" in desc or "8811" in desc or "8812" in desc or "alfa" in desc:
                return iface["name"]

        # 2. Check for standard secondary interface name
        for iface in interfaces:
            if iface.get("name") == "Wi-Fi 2":
                return iface["name"]

        return None
    except Exception as e:
        logger.warning(f"Failed to query wireless interfaces: {e}")
        return None


def parse_netsh_output(output: str, node_id: str = "laptop-alfa-01", timestamp: Optional[int] = None) -> List[Dict[str, Any]]:
    """Parses raw `netsh wlan show networks mode=bssid` output into Schema v1 observations."""
    if timestamp is None:
        timestamp = int(time.time())

    observations = []
    current_ssid = ""
    current_entry: Optional[Dict[str, Any]] = None

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("SSID "):
            parts = line.split(" : ", 1)
            current_ssid = parts[1].strip() if len(parts) > 1 else ""
        elif line.startswith("BSSID "):
            parts = line.split(" : ", 1)
            if len(parts) > 1:
                bssid = parts[1].strip().lower()
                current_entry = {
                    "schema_version": 1,
                    "node_id": node_id,
                    "timestamp": timestamp,
                    "radio": "wifi",
                    "address": bssid,
                    "ssid": current_ssid,
                    "rssi": -90,
                    "channel": None,
                    "signature": "unknown",
                    "confidence": 0.0,
                    "manufacturer": "unknown",
                }
                observations.append(current_entry)
        elif current_entry is not None:
            if "Signal" in line:
                m = re.search(r"(\d+)%", line)
                if m:
                    pct = int(m.group(1))
                    # Convert Windows signal quality (0-100%) to approximate dBm (-100 to -50 dBm)
                    current_entry["rssi"] = round((pct / 2.0) - 100)
            elif "Channel" in line:
                m = re.search(r"Channel\s*:\s*(\d+)", line)
                if m:
                    current_entry["channel"] = int(m.group(1))

    # Apply Device Signature Engine to all discovered BSSIDs
    for obs in observations:
        enrich_observation(obs)

    return observations


def scan_alfa(interface_name: Optional[str] = None, node_id: str = "laptop-alfa-01") -> List[Dict[str, Any]]:
    """Performs a 2.4 GHz & 5 GHz sweep using the Alfa adapter."""
    iface = interface_name or find_alfa_interface()
    if not iface:
        raise RuntimeError("No compatible ALFA/wireless secondary interface found.")

    cmd = ["netsh", "wlan", "show", "networks", "mode=bssid", f"interface={iface}"]
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=False)
    if res.returncode != 0:
        raise RuntimeError(f"netsh scan failed (code {res.returncode}): {res.stderr}")

    return parse_netsh_output(res.stdout, node_id=node_id)


class AlfaScannerDaemon(threading.Thread):
    """Background thread that continuously scans with the Alfa adapter."""

    def __init__(
        self,
        db: Database,
        interface_name: Optional[str] = None,
        node_id: str = "laptop-alfa-01",
        interval_sec: int = 15,
        stop_event: Optional[threading.Event] = None
    ):
        super().__init__(daemon=True, name="AlfaScannerDaemon")
        self.db = db
        self.interface_name = interface_name or find_alfa_interface()
        self.node_id = node_id
        self.interval_sec = interval_sec
        self.stop_event = stop_event or threading.Event()
        self.total_synced = 0

    def run(self):
        if not self.interface_name:
            logger.warning("AlfaScannerDaemon: No Alfa/Wi-Fi adapter detected. Thread exiting.")
            return

        logger.info(f"AlfaScannerDaemon active on interface '{self.interface_name}' (interval={self.interval_sec}s)")

        while not self.stop_event.is_set():
            try:
                obs_list = scan_alfa(self.interface_name, node_id=self.node_id)
                if obs_list:
                    inserted = self.db.insert_batch(obs_list)
                    self.total_synced += inserted
                    channels = set(o["channel"] for o in obs_list if o.get("channel"))
                    ghz5_count = sum(1 for c in channels if c > 14)
                    ghz2_count = sum(1 for c in channels if c <= 14)
                    logger.info(
                        f"[ALFA] Scanned {len(obs_list)} BSSIDs ({inserted} new) across "
                        f"{ghz2_count} 2.4GHz & {ghz5_count} 5GHz channels."
                    )
            except Exception as e:
                logger.warning(f"Alfa scan cycle error: {e}")

            # Sleep in slices for responsive stop
            for _ in range(self.interval_sec * 10):
                if self.stop_event.is_set():
                    break
                time.sleep(0.1)

        logger.info("AlfaScannerDaemon stopped.")

    def stop(self):
        self.stop_event.set()
