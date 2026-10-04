"""SQLite Database Engine for Fieldwatch Central Collector."""
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import Device, Observation


class Database:
    def __init__(self, db_path: Union[str, Path] = "collector/fieldwatch.db"):
        self.db_path = str(db_path)
        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._configure_pragmas()

    def _configure_pragmas(self):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.close()

    def init_schema(self):
        """Initializes tables and indexes if they do not already exist."""
        with self.conn:
            # 1. Observations time-series table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    node_id TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    radio TEXT NOT NULL,
                    address TEXT NOT NULL,
                    rssi INTEGER NOT NULL,
                    channel INTEGER,
                    ssid TEXT,
                    manufacturer TEXT,
                    signature TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    connectable INTEGER,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(node_id, timestamp, address, radio) ON CONFLICT IGNORE
                );
            """)

            # Composite indexes for sub-second queries
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_obs_address_ts 
                ON observations(address, timestamp DESC);
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_obs_node_ts 
                ON observations(node_id, timestamp DESC);
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_obs_sig_ts 
                ON observations(signature, timestamp DESC);
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_obs_radio_ts 
                ON observations(radio, timestamp DESC);
            """)

            # 2. Devices rollup summary table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    address TEXT PRIMARY KEY,
                    radio TEXT NOT NULL,
                    manufacturer TEXT,
                    signature TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    first_seen INTEGER NOT NULL,
                    last_seen INTEGER NOT NULL,
                    sighting_count INTEGER NOT NULL DEFAULT 1,
                    best_rssi INTEGER NOT NULL,
                    last_rssi INTEGER NOT NULL,
                    last_ssid TEXT,
                    is_connectable INTEGER
                );
            """)

            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_devices_last_seen 
                ON devices(last_seen DESC);
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_devices_signature 
                ON devices(signature);
            """)

    def insert_observation(self, obs_input: Union[Dict[str, Any], Observation]) -> bool:
        """Inserts a single observation and updates the devices rollup table.
        
        Returns:
            True if a new observation was inserted into observations,
            False if it was ignored as a duplicate.
        """
        obs = obs_input if isinstance(obs_input, Observation) else Observation.from_dict(obs_input)
        conn_changes_before = self.conn.total_changes

        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO observations (
                    schema_version, node_id, timestamp, radio, address,
                    rssi, channel, ssid, manufacturer, signature,
                    confidence, connectable
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                obs.schema_version,
                obs.node_id,
                obs.timestamp,
                obs.radio,
                obs.address,
                obs.rssi,
                obs.channel,
                obs.ssid,
                obs.manufacturer,
                obs.signature,
                obs.confidence,
                1 if obs.connectable is True else (0 if obs.connectable is False else None),
            ))

            is_new = (self.conn.total_changes > conn_changes_before)
            if is_new:
                # Update devices rollup atomically
                cursor.execute("""
                    INSERT INTO devices (
                        address, radio, manufacturer, signature, confidence,
                        first_seen, last_seen, sighting_count, best_rssi, last_rssi,
                        last_ssid, is_connectable
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                    ON CONFLICT(address) DO UPDATE SET
                        manufacturer = COALESCE(excluded.manufacturer, devices.manufacturer),
                        signature = CASE 
                            WHEN excluded.confidence >= devices.confidence THEN excluded.signature 
                            ELSE devices.signature 
                        END,
                        confidence = MAX(excluded.confidence, devices.confidence),
                        first_seen = MIN(devices.first_seen, excluded.first_seen),
                        last_seen = MAX(devices.last_seen, excluded.last_seen),
                        sighting_count = devices.sighting_count + 1,
                        best_rssi = MAX(devices.best_rssi, excluded.best_rssi),
                        last_rssi = excluded.last_rssi,
                        last_ssid = COALESCE(excluded.last_ssid, devices.last_ssid),
                        is_connectable = COALESCE(excluded.is_connectable, devices.is_connectable);
                """, (
                    obs.address,
                    obs.radio,
                    obs.manufacturer,
                    obs.signature,
                    obs.confidence,
                    obs.timestamp,
                    obs.timestamp,
                    obs.rssi,
                    obs.rssi,
                    obs.ssid,
                    1 if obs.connectable is True else (0 if obs.connectable is False else None),
                ))

            cursor.close()
            return is_new

    def insert_batch(self, observations: List[Union[Dict[str, Any], Observation]]) -> int:
        """Inserts a batch of observations inside a single transaction.
        
        Returns:
            Number of newly inserted unique observations.
        """
        if not observations:
            return 0

        inserted_count = 0
        with self.conn:
            cursor = self.conn.cursor()
            for item in observations:
                obs = item if isinstance(item, Observation) else Observation.from_dict(item)
                changes_before = self.conn.total_changes
                cursor.execute("""
                    INSERT INTO observations (
                        schema_version, node_id, timestamp, radio, address,
                        rssi, channel, ssid, manufacturer, signature,
                        confidence, connectable
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    obs.schema_version,
                    obs.node_id,
                    obs.timestamp,
                    obs.radio,
                    obs.address,
                    obs.rssi,
                    obs.channel,
                    obs.ssid,
                    obs.manufacturer,
                    obs.signature,
                    obs.confidence,
                    1 if obs.connectable is True else (0 if obs.connectable is False else None),
                ))

                if self.conn.total_changes > changes_before:
                    inserted_count += 1
                    cursor.execute("""
                        INSERT INTO devices (
                            address, radio, manufacturer, signature, confidence,
                            first_seen, last_seen, sighting_count, best_rssi, last_rssi,
                            last_ssid, is_connectable
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                        ON CONFLICT(address) DO UPDATE SET
                            manufacturer = COALESCE(excluded.manufacturer, devices.manufacturer),
                            signature = CASE 
                                WHEN excluded.confidence >= devices.confidence THEN excluded.signature 
                                ELSE devices.signature 
                            END,
                            confidence = MAX(excluded.confidence, devices.confidence),
                            first_seen = MIN(devices.first_seen, excluded.first_seen),
                            last_seen = MAX(devices.last_seen, excluded.last_seen),
                            sighting_count = devices.sighting_count + 1,
                            best_rssi = MAX(devices.best_rssi, excluded.best_rssi),
                            last_rssi = excluded.last_rssi,
                            last_ssid = COALESCE(excluded.last_ssid, devices.last_ssid),
                            is_connectable = COALESCE(excluded.is_connectable, devices.is_connectable);
                    """, (
                        obs.address,
                        obs.radio,
                        obs.manufacturer,
                        obs.signature,
                        obs.confidence,
                        obs.timestamp,
                        obs.timestamp,
                        obs.rssi,
                        obs.rssi,
                        obs.ssid,
                        1 if obs.connectable is True else (0 if obs.connectable is False else None),
                    ))
            cursor.close()

        return inserted_count

    def get_stats(self) -> Dict[str, Any]:
        """Returns summary statistics for the collected data."""
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM observations;")
        total_obs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM devices;")
        total_devices = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM devices WHERE radio = 'wifi';")
        wifi_devices = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM devices WHERE radio = 'ble';")
        ble_devices = cursor.fetchone()[0]

        cursor.execute("SELECT signature, COUNT(*) FROM devices GROUP BY signature;")
        signatures = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT manufacturer, COUNT(*) as count 
            FROM devices 
            WHERE manufacturer IS NOT NULL AND manufacturer != ''
            GROUP BY manufacturer 
            ORDER BY count DESC 
            LIMIT 10;
        """)
        top_manufacturers = [{"manufacturer": row[0], "count": row[1]} for row in cursor.fetchall()]

        cursor.execute("SELECT MAX(timestamp) FROM observations;")
        latest_ts = cursor.fetchone()[0]

        cursor.close()
        return {
            "total_observations": total_obs,
            "total_devices": total_devices,
            "wifi_devices": wifi_devices,
            "ble_devices": ble_devices,
            "signatures": signatures,
            "top_manufacturers": top_manufacturers,
            "latest_timestamp": latest_ts or 0,
        }

    def get_devices(
        self,
        filter_text: Optional[str] = None,
        radio: Optional[str] = None,
        signature: Optional[str] = None,
        sort_by: str = "last_seen",
        sort_order: str = "DESC",
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Queries devices with optional filtering, sorting, and pagination."""
        query = "SELECT * FROM devices WHERE 1=1"
        params: List[Any] = []

        if filter_text:
            query += " AND (address LIKE ? OR manufacturer LIKE ? OR last_ssid LIKE ?)"
            pattern = f"%{filter_text.strip()}%"
            params.extend([pattern, pattern, pattern])

        if radio:
            query += " AND radio = ?"
            params.append(radio.lower().strip())

        if signature:
            query += " AND signature = ?"
            params.append(signature.strip())

        valid_sort_cols = {
            "last_seen": "last_seen",
            "first_seen": "first_seen",
            "sighting_count": "sighting_count",
            "best_rssi": "best_rssi",
            "confidence": "confidence",
            "address": "address"
        }
        order_col = valid_sort_cols.get(sort_by, "last_seen")
        order_dir = "ASC" if sort_order.upper() == "ASC" else "DESC"
        query += f" ORDER BY {order_col} {order_dir} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        cursor.close()
        return results

    def get_device(self, address: str) -> Optional[Dict[str, Any]]:
        """Fetches a single device by address."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM devices WHERE address = ?;", (address.lower().strip(),))
        row = cursor.fetchone()
        cursor.close()
        return dict(row) if row else None

    def get_device_history(self, address: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetches recent observation history for a specific device."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM observations 
            WHERE address = ? 
            ORDER BY timestamp DESC 
            LIMIT ?;
        """, (address.lower().strip(), limit))
        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        cursor.close()
        return results

    def close(self):
        """Closes the underlying database connection."""
        if self.conn:
            self.conn.close()
