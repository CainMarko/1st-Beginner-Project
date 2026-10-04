"""Ingestion engine for Fieldwatch Central Collector."""
import json
import logging
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from .database import Database

logger = logging.getLogger("fieldwatch.ingest")


def fetch_observations(gateway_url: str, timeout: int = 10) -> List[Dict[str, Any]]:
    """Fetches observations from the Edge Gateway via HTTP GET /observations.
    
    Args:
        gateway_url: Base URL (e.g., 'http://192.168.1.152')
        timeout: HTTP request timeout in seconds.
        
    Returns:
        List of observation dictionaries.
    """
    clean_url = gateway_url.rstrip("/")
    if not clean_url.endswith("/observations"):
        clean_url = f"{clean_url}/observations"

    req = urllib.request.Request(
        clean_url,
        headers={"User-Agent": "Fieldwatch-Collector/1.0", "Accept": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                raise urllib.error.HTTPError(
                    clean_url, response.status, f"HTTP Error {response.status}", response.headers, None
                )
            payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, dict):
                return payload.get("observations", [])
            elif isinstance(payload, list):
                return payload
            return []
    except urllib.error.URLError as e:
        logger.warning(f"Failed to connect to gateway at {clean_url}: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Malformed JSON from gateway at {clean_url}: {e}")
        raise


def sync_gateway(gateway_url: str, db: Database, timeout: int = 10) -> Tuple[int, int]:
    """Polls the gateway and ingests all returned observations into the database.
    
    Returns:
        Tuple of (total_fetched, newly_inserted).
    """
    observations = fetch_observations(gateway_url, timeout=timeout)
    total_fetched = len(observations)
    if total_fetched == 0:
        return (0, 0)

    newly_inserted = db.insert_batch(observations)
    logger.info(f"Sync complete: {newly_inserted} new observations inserted out of {total_fetched} fetched.")
    return (total_fetched, newly_inserted)


class SyncDaemon(threading.Thread):
    """Background polling thread that synchronizes with the gateway at a fixed interval."""
    def __init__(
        self,
        gateway_url: str,
        db: Database,
        interval_sec: int = 15,
        stop_event: Optional[threading.Event] = None
    ):
        super().__init__(daemon=True, name="SyncDaemon")
        self.gateway_url = gateway_url
        self.db = db
        self.interval_sec = interval_sec
        self.stop_event = stop_event or threading.Event()
        self.last_sync_time: Optional[float] = None
        self.last_sync_status: str = "initialized"
        self.total_synced: int = 0
        self.consecutive_failures: int = 0

    def run(self):
        logger.info(f"SyncDaemon started for {self.gateway_url} (interval={self.interval_sec}s)")
        while not self.stop_event.is_set():
            try:
                fetched, inserted = sync_gateway(self.gateway_url, self.db)
                self.last_sync_time = time.time()
                self.last_sync_status = f"success ({inserted}/{fetched} new)"
                self.total_synced += inserted
                self.consecutive_failures = 0
            except Exception as e:
                self.last_sync_time = time.time()
                self.last_sync_status = f"failed: {e}"
                self.consecutive_failures += 1
                logger.warning(f"Sync failed ({self.consecutive_failures}x): {e}")

            # Sleep in small slices so stop_event can terminate promptly
            for _ in range(self.interval_sec * 10):
                if self.stop_event.is_set():
                    break
                time.sleep(0.1)

        logger.info("SyncDaemon stopped.")

    def stop(self):
        self.stop_event.set()
