"""802.11 Monitor Mode Smartphone Probe Request Sniffer for ALFA AWUS036ACS.

Captures unassociated smartphone 802.11 Probe Request frames using Scapy + Npcap.
Identifies nearby mobile devices, requested SSIDs, RSSI, and ingests findings
directly into the Fieldwatch SQLite database.
"""

import logging
import os
import re
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from .database import Database
from .models import Observation

logger = logging.getLogger("fieldwatch.probe_sniffer")

# Common 2.4 GHz channels for probe sniffing
CHANNELS_24GHZ = [1, 6, 11, 2, 3, 4, 5, 7, 8, 9, 10]


def find_wlanhelper() -> Optional[str]:
    """Locates WlanHelper.exe installed by Npcap."""
    candidates = [
        r"C:\Windows\System32\WlanHelper.exe",
        r"C:\Program Files\Npcap\WlanHelper.exe",
        r"C:\Program Files (x86)\Npcap\WlanHelper.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def get_alfa_interface_details() -> Optional[Dict[str, str]]:
    """Detects ALFA RTL8811AU interface GUID, Scapy interface, and friendly name."""
    wlanhelper = find_wlanhelper()
    if not wlanhelper:
        return None

    try:
        res = subprocess.run([wlanhelper, "-i"], capture_output=True, text=True, timeout=5)
        output = res.stdout + res.stderr
    except Exception as e:
        logger.warning(f"Failed to query WlanHelper interfaces: {e}")
        return None

    # Parse WlanHelper output to locate RTL8811AU / ALFA interface GUID
    # Format:
    # 1. 41298fcc-c671-4c00-9a70-811d002b70c5
    #     Name: Wi-Fi 2
    #     Description: Realtek RTL8811AU Wireless LAN 802.11ac USB 2.0 Network Adapter
    guid = None
    friendly_name = "Wi-Fi 2"

    blocks = output.split("****************************************************")
    if len(blocks) > 1:
        target_section = blocks[1]
        lines = target_section.splitlines()
        current_guid = None
        for line in lines:
            guid_match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", line)
            if guid_match:
                current_guid = guid_match.group(1)
            if "RTL8811AU" in line or "Realtek" in line or "Alfa" in line:
                guid = current_guid
                break

    if not guid:
        # Fallback search
        m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", output)
        if m:
            guid = m.group(1)

    if not guid:
        return None

    # Match with Scapy interface
    try:
        import scapy.all as scapy
        scapy_iface = None
        guid_upper = guid.upper()
        for iface_obj in scapy.conf.ifaces.values():
            if guid_upper in str(getattr(iface_obj, "name", "")).upper() or guid_upper in str(getattr(iface_obj, "network_name", "")).upper():
                scapy_iface = iface_obj
                break
            if "RTL8811AU" in getattr(iface_obj, "description", ""):
                scapy_iface = iface_obj
                break
    except Exception:
        scapy_iface = None

    return {
        "guid": guid,
        "friendly_name": friendly_name,
        "scapy_iface": scapy_iface,
        "wlanhelper": wlanhelper,
    }


def get_interface_mode(guid: str) -> str:
    """Queries current operation mode (managed or monitor)."""
    wlanhelper = find_wlanhelper()
    if not wlanhelper:
        return "unknown"
    try:
        res = subprocess.run([wlanhelper, guid, "mode"], capture_output=True, text=True, timeout=5)
        return res.stdout.strip().lower()
    except Exception:
        return "unknown"


def set_interface_channel(guid: str, channel: int) -> bool:
    """Sets the wireless channel via WlanHelper."""
    wlanhelper = find_wlanhelper()
    if not wlanhelper:
        return False
    try:
        res = subprocess.run([wlanhelper, guid, "channel", str(channel)], capture_output=True, text=True, timeout=3)
        return "success" in res.stdout.lower() or res.returncode == 0
    except Exception:
        return False


class ChannelHopper(threading.Thread):
    """Periodically hops 802.11 channels in monitor mode to capture diverse probes."""

    def __init__(self, guid: str, channels: Optional[List[int]] = None, hop_interval: float = 2.0, stop_event: Optional[threading.Event] = None):
        super().__init__(daemon=True, name="ChannelHopper")
        self.guid = guid
        self.channels = channels or CHANNELS_24GHZ
        self.hop_interval = hop_interval
        self.stop_event = stop_event or threading.Event()
        self.current_channel = self.channels[0]

    def run(self):
        idx = 0
        while not self.stop_event.is_set():
            ch = self.channels[idx % len(self.channels)]
            self.current_channel = ch
            set_interface_channel(self.guid, ch)
            idx += 1
            # Sleep in slices
            for _ in range(int(self.hop_interval * 10)):
                if self.stop_event.is_set():
                    break
                time.sleep(0.1)


class ProbeSnifferDaemon(threading.Thread):
    """Background thread that captures Probe Requests and ingests them into SQLite."""

    def __init__(
        self,
        db: Database,
        node_id: str = "laptop-alfa-01",
        interface_details: Optional[Dict[str, Any]] = None,
        stop_event: Optional[threading.Event] = None
    ):
        super().__init__(daemon=True, name="ProbeSnifferDaemon")
        self.db = db
        self.node_id = node_id
        self.stop_event = stop_event or threading.Event()
        self.details = interface_details or get_alfa_interface_details()
        self.probes_captured = 0
        self.unique_macs = set()
        self.channel_hopper: Optional[ChannelHopper] = None

    def _packet_callback(self, pkt):
        if self.stop_event.is_set():
            return

        try:
            from scapy.layers.dot11 import Dot11, Dot11Elt, Dot11ProbeReq, RadioTap

            if not pkt.haslayer(Dot11ProbeReq):
                return

            dot11 = pkt.getlayer(Dot11)
            client_mac = getattr(dot11, "addr2", None)
            if not client_mac:
                return

            client_mac = client_mac.lower()

            # Extract requested SSID
            requested_ssid = ""
            elt = pkt.getlayer(Dot11Elt)
            while elt:
                if elt.ID == 0:
                    try:
                        raw_ssid = elt.info
                        if raw_ssid:
                            requested_ssid = raw_ssid.decode("utf-8", "ignore").strip()
                    except Exception:
                        pass
                    break
                elt = elt.payload.getlayer(Dot11Elt) if elt.payload else None

            # Extract RSSI from RadioTap if present
            rssi = -70
            if pkt.haslayer(RadioTap):
                rt = pkt.getlayer(RadioTap)
                if hasattr(rt, "dBm_AntSignal"):
                    rssi = int(rt.dBm_AntSignal)

            # Determine channel
            current_ch = self.channel_hopper.current_channel if self.channel_hopper else None

            # Generate Observation
            now_ts = int(time.time())
            obs = Observation(
                schema_version=1,
                node_id=self.node_id,
                timestamp=now_ts,
                radio="wifi",
                address=client_mac,
                rssi=rssi,
                channel=current_ch,
                ssid=requested_ssid or None,
                manufacturer=None,
                signature="mobile-personal",
                confidence=0.85,
                connectable=None
            )

            self.db.insert_observation(obs)
            self.probes_captured += 1
            if client_mac not in self.unique_macs:
                self.unique_macs.add(client_mac)
                logger.info(f"[PROBE] New mobile device: {client_mac} RSSI={rssi}dBm SSID='{requested_ssid}'")

        except Exception as e:
            logger.debug(f"Error parsing 802.11 packet: {e}")

    def run(self):
        if not self.details or not self.details.get("scapy_iface"):
            logger.error("[PROBE] Cannot start sniffer: ALFA Npcap interface not found.")
            return

        guid = self.details["guid"]
        mode = get_interface_mode(guid)
        if mode != "monitor":
            logger.warning(
                f"[PROBE] Interface {guid} is in '{mode}' mode, not 'monitor'. "
                "Raw 802.11 probe sniffing requires monitor mode. "
                "Run: WlanHelper.exe \"Wi-Fi 2\" mode monitor as Administrator."
            )

        # Start channel hopper
        self.channel_hopper = ChannelHopper(guid=guid, stop_event=self.stop_event)
        self.channel_hopper.start()

        import scapy.all as scapy
        scapy_iface = self.details["scapy_iface"]

        logger.info(f"[PROBE] Probe Request sniffer active on {getattr(scapy_iface, 'description', scapy_iface)}")

        try:
            while not self.stop_event.is_set():
                scapy.sniff(
                    iface=scapy_iface,
                    prn=self._packet_callback,
                    timeout=2,
                    store=False
                )
        except Exception as e:
            logger.error(f"[PROBE] Sniff loop encountered error: {e}")
        finally:
            if self.channel_hopper:
                self.channel_hopper.stop_event.set()
