"""Command-line interface for Fieldwatch Central Collector.

Usage:
    py -3 -m collector sync [--gateway URL] [--db PATH]
    py -3 -m collector run [--gateway URL] [--port PORT] [--interval SEC]
    py -3 -m collector stats [--db PATH]
    py -3 -m collector devices [--radio wifi|ble] [--signature SIG] [--search Q] [--limit N]
    py -3 -m collector export --format json|csv --output FILE
"""
import argparse
import csv
import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path

from .database import Database
from .ingest import SyncDaemon, sync_gateway
from .server import run_server

DEFAULT_GATEWAY_URL = "http://192.168.1.152"
DEFAULT_DB_PATH = "collector/fieldwatch.db"


def cmd_sync(args):
    db = Database(args.db)
    db.init_schema()
    print(f"Connecting to Gateway at {args.gateway}...")
    t0 = time.time()
    try:
        fetched, inserted = sync_gateway(args.gateway, db)
        elapsed = time.time() - t0
        print(f"[OK] Sync successful in {elapsed:.2f}s:")
        print(f"     Observations fetched: {fetched}")
        print(f"     New observations saved: {inserted}")
        print(f"     Duplicate/re-sync dropped: {fetched - inserted}")
        stats = db.get_stats()
        print(f"     Database totals: {stats['total_observations']} observations, {stats['total_devices']} unique devices")
    except Exception as e:
        print(f"[ERROR] Failed to sync with gateway: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def cmd_run(args):
    db = Database(args.db)
    db.init_schema()

    stop_event = threading.Event()

    # 1. Start background SyncDaemon
    daemon = SyncDaemon(args.gateway, db, interval_sec=args.interval, stop_event=stop_event)
    daemon.start()

    # 2. Start HTTP server
    server = run_server(db, gateway_url=args.gateway, host=args.host, port=args.port)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print("=" * 60)
    print("  FIELDWATCH CENTRAL COLLECTOR RUNNING")
    print(f"  Web Dashboard:   http://localhost:{args.port}/")
    print(f"  Edge Gateway:    {args.gateway}")
    print(f"  Database Path:   {args.db}")
    print(f"  Sync Interval:   {args.interval}s")
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    def handle_shutdown(signum, frame):
        print("\nStopping Fieldwatch Collector...")
        stop_event.set()
        server.shutdown()
        server.server_close()
        db.close()
        print("Collector stopped cleanly.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_shutdown)

    # Keep main thread alive
    while not stop_event.is_set():
        time.sleep(0.5)


def cmd_stats(args):
    db = Database(args.db)
    db.init_schema()
    stats = db.get_stats()
    db.close()

    print("\n--- Fieldwatch Database Summary ---")
    print(f"Total Observations:  {stats['total_observations']:,}")
    print(f"Discovered Devices:  {stats['total_devices']:,}")
    print(f"  - Wi-Fi Networks:  {stats['wifi_devices']:,}")
    print(f"  - BLE Peripherals: {stats['ble_devices']:,}")
    print(f"Latest Sighting TS:  {stats['latest_timestamp']}")

    print("\nDevice Archetypes:")
    if stats["signatures"]:
        for sig, count in sorted(stats["signatures"].items(), key=lambda x: x[1], reverse=True):
            pct = (count / max(1, stats['total_devices'])) * 100
            print(f"  - {sig:<20} {count:>5} ({pct:>5.1f}%)")
    else:
        print("  (None recorded yet)")

    print("\nTop Manufacturers:")
    if stats["top_manufacturers"]:
        for item in stats["top_manufacturers"]:
            print(f"  - {item['manufacturer']:<20} {item['count']:>5}")
    else:
        print("  (None identified yet)")
    print()


def cmd_devices(args):
    db = Database(args.db)
    db.init_schema()

    devices = db.get_devices(
        filter_text=args.search,
        radio=args.radio,
        signature=args.signature,
        sort_by=args.sort,
        sort_order=args.order,
        limit=args.limit
    )
    db.close()

    if not devices:
        print("No matching devices found.")
        return

    print(f"\nDiscovered Devices ({len(devices)} displayed):")
    header = f"{'Address':<18} {'Radio':<6} {'RSSI':<6} {'Count':<6} {'Conf':<6} {'Signature':<18} {'Manufacturer / Name'}"
    print(header)
    print("-" * len(header))

    for d in devices:
        ident = d.get("last_ssid") or d.get("manufacturer") or "Unknown"
        conf_pct = f"{int(d.get('confidence', 0) * 100)}%"
        rssi_str = f"{d.get('last_rssi')}dB"
        print(f"{d['address']:<18} {d['radio']:<6} {rssi_str:<6} {d['sighting_count']:<6} {conf_pct:<6} {d['signature']:<18} {ident}")
    print()


def cmd_export(args):
    db = Database(args.db)
    db.init_schema()

    cursor = db.conn.cursor()
    cursor.execute("SELECT * FROM observations ORDER BY timestamp ASC;")
    rows = cursor.fetchall()

    if not rows:
        print("Database is empty, nothing to export.")
        db.close()
        return

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "csv":
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(rows[0].keys())
            for row in rows:
                writer.writerow(list(row))
        print(f"Exported {len(rows)} observations to CSV: {out_path}")
    else:
        records = [dict(row) for row in rows]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        print(f"Exported {len(rows)} observations to JSON: {out_path}")

    db.close()


def main():
    parser = argparse.ArgumentParser(description="Fieldwatch Central Laptop Collector")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sync
    p_sync = subparsers.add_parser("sync", help="One-shot sync from edge gateway")
    p_sync.add_argument("--gateway", default=DEFAULT_GATEWAY_URL, help="Gateway URL")
    p_sync.add_argument("--db", default=DEFAULT_DB_PATH, help="Database path")
    p_sync.set_defaults(func=cmd_sync)

    # run
    p_run = subparsers.add_parser("run", help="Run background sync daemon and local web dashboard")
    p_run.add_argument("--gateway", default=DEFAULT_GATEWAY_URL, help="Gateway URL")
    p_run.add_argument("--db", default=DEFAULT_DB_PATH, help="Database path")
    p_run.add_argument("--port", type=int, default=8080, help="Web port (default 8080)")
    p_run.add_argument("--host", default="0.0.0.0", help="Web host (default 0.0.0.0)")
    p_run.add_argument("--interval", type=int, default=15, help="Sync interval seconds (default 15)")
    p_run.set_defaults(func=cmd_run)

    # stats
    p_stats = subparsers.add_parser("stats", help="Display summary stats from database")
    p_stats.add_argument("--db", default=DEFAULT_DB_PATH, help="Database path")
    p_stats.set_defaults(func=cmd_stats)

    # devices
    p_dev = subparsers.add_parser("devices", help="Query devices from database")
    p_dev.add_argument("--db", default=DEFAULT_DB_PATH, help="Database path")
    p_dev.add_argument("--radio", choices=["wifi", "ble"], help="Filter by radio")
    p_dev.add_argument("--signature", help="Filter by signature archetype")
    p_dev.add_argument("--search", help="Search query")
    p_dev.add_argument("--sort", default="last_seen", help="Sort column")
    p_dev.add_argument("--order", default="DESC", choices=["ASC", "DESC"], help="Sort order")
    p_dev.add_argument("--limit", type=int, default=50, help="Result limit")
    p_dev.set_defaults(func=cmd_devices)

    # export
    p_exp = subparsers.add_parser("export", help="Export observations to CSV or JSON")
    p_exp.add_argument("--db", default=DEFAULT_DB_PATH, help="Database path")
    p_exp.add_argument("--format", choices=["json", "csv"], default="json", help="Export format")
    p_exp.add_argument("--output", required=True, help="Output file path")
    p_exp.set_defaults(func=cmd_export)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
