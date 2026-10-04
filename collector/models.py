"""Data models for Fieldwatch Central Collector."""
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any


@dataclass
class Observation:
    node_id: str
    timestamp: int
    radio: str
    address: str
    rssi: int
    signature: str = "unknown"
    confidence: float = 0.0
    schema_version: int = 1
    channel: Optional[int] = None
    ssid: Optional[str] = None
    manufacturer: Optional[str] = None
    connectable: Optional[bool] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Observation":
        # Handle field mappings / conversions
        connectable_raw = data.get("connectable")
        connectable = None
        if connectable_raw is not None:
            connectable = bool(connectable_raw)

        return cls(
            schema_version=int(data.get("schema_version", 1)),
            node_id=str(data.get("node_id", "unknown")),
            timestamp=int(data.get("timestamp", 0)),
            radio=str(data.get("radio", "unknown")).lower(),
            address=str(data.get("address", "")).lower().strip(),
            rssi=int(data.get("rssi", -100)),
            channel=int(data["channel"]) if data.get("channel") is not None else None,
            ssid=str(data["ssid"]) if data.get("ssid") is not None else None,
            manufacturer=str(data["manufacturer"]) if data.get("manufacturer") is not None else None,
            signature=str(data.get("signature", "unknown")),
            confidence=float(data.get("confidence", 0.0)),
            connectable=connectable,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Device:
    address: str
    radio: str
    signature: str
    confidence: float
    first_seen: int
    last_seen: int
    sighting_count: int
    best_rssi: int
    last_rssi: int
    manufacturer: Optional[str] = None
    last_ssid: Optional[str] = None
    is_connectable: Optional[bool] = None
    last_channel: Optional[int] = None
    last_node_id: Optional[str] = None

    @classmethod
    def from_row(cls, row: Any) -> "Device":
        # Handle dict, sqlite3.Row, or tuple
        if hasattr(row, "keys"):
            return cls(
                address=row["address"],
                radio=row["radio"],
                manufacturer=row["manufacturer"],
                signature=row["signature"],
                confidence=row["confidence"],
                first_seen=row["first_seen"],
                last_seen=row["last_seen"],
                sighting_count=row["sighting_count"],
                best_rssi=row["best_rssi"],
                last_rssi=row["last_rssi"],
                last_ssid=row["last_ssid"],
                is_connectable=bool(row["is_connectable"]) if row["is_connectable"] is not None else None,
                last_channel=row["last_channel"] if "last_channel" in row.keys() else None,
                last_node_id=row["last_node_id"] if "last_node_id" in row.keys() else None,
            )
        return cls(
            address=row[0],
            radio=row[1],
            manufacturer=row[2],
            signature=row[3],
            confidence=row[4],
            first_seen=row[5],
            last_seen=row[6],
            sighting_count=row[7],
            best_rssi=row[8],
            last_rssi=row[9],
            last_ssid=row[10],
            is_connectable=bool(row[11]) if len(row) > 11 and row[11] is not None else None,
            last_channel=row[12] if len(row) > 12 else None,
            last_node_id=row[13] if len(row) > 13 else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
