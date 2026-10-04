"""Local HTTP server and REST API for Fieldwatch Central Collector."""
import json
import logging
import os
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Optional

from .database import Database
from .ingest import sync_gateway

logger = logging.getLogger("fieldwatch.server")

STATIC_DIR = Path(__file__).parent / "static"


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    daemon_threads = True


class FieldwatchRequestHandler(SimpleHTTPRequestHandler):
    """Custom request handler serving REST APIs and static dashboard assets."""
    db: Database
    gateway_url: str

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format, *args):
        # Format custom log or suppress spammy static requests if needed
        logger.debug("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), format % args))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/stats":
            self.handle_api_stats()
        elif path == "/api/devices":
            self.handle_api_devices(query)
        elif path.startswith("/api/device/") and path.endswith("/history"):
            self.handle_api_device_history(path)
        elif path == "/" or path == "/index.html":
            self.serve_index()
        else:
            # Fall back to static files in STATIC_DIR
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/sync":
            self.handle_api_sync()
        else:
            self.send_error(404, "Not Found")

    def serve_index(self):
        index_file = STATIC_DIR / "index.html"
        if not index_file.exists():
            self.send_error(404, "Dashboard HTML not found")
            return

        with open(index_file, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def handle_api_stats(self):
        try:
            stats = self.db.get_stats()
            self.send_json(stats)
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            self.send_json({"error": str(e)}, status=500)

    def handle_api_devices(self, query: dict):
        try:
            filter_text = query.get("q", [None])[0]
            radio = query.get("radio", [None])[0]
            signature = query.get("signature", [None])[0]
            band = query.get("band", [None])[0]
            node_id = query.get("node", [None])[0]
            sort_by = query.get("sort", ["last_seen"])[0]
            sort_order = query.get("order", ["DESC"])[0]
            limit = int(query.get("limit", [100])[0])
            offset = int(query.get("offset", [0])[0])

            devices = self.db.get_devices(
                filter_text=filter_text,
                radio=radio,
                signature=signature,
                band=band,
                node_id=node_id,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
                offset=offset,
            )
            stats = self.db.get_filtered_stats(
                filter_text=filter_text,
                radio=radio,
                signature=signature,
                band=band,
                node_id=node_id
            )
            self.send_json({
                "count": len(devices),
                "total_matching": stats["total_devices"],
                "stats": stats,
                "devices": devices
            })
        except Exception as e:
            logger.error(f"Error fetching devices: {e}")
            self.send_json({"error": str(e)}, status=500)

    def handle_api_device_history(self, path: str):
        try:
            parts = path.split("/")
            # path is /api/device/<address>/history
            if len(parts) >= 5:
                address = urllib.parse.unquote(parts[3])
                history = self.db.get_device_history(address, limit=50)
                device = self.db.get_device(address)
                self.send_json({"address": address, "device": device, "history": history})
            else:
                self.send_json({"error": "Invalid device path"}, status=400)
        except Exception as e:
            logger.error(f"Error fetching device history: {e}")
            self.send_json({"error": str(e)}, status=500)

    def handle_api_sync(self):
        try:
            fetched, inserted = sync_gateway(self.gateway_url, self.db)
            self.send_json({
                "status": "ok",
                "fetched": fetched,
                "inserted": inserted,
                "gateway_url": self.gateway_url
            })
        except Exception as e:
            logger.error(f"Manual sync error: {e}")
            self.send_json({
                "status": "error",
                "message": str(e),
                "gateway_url": self.gateway_url
            }, status=502)


def run_server(
    db: Database,
    gateway_url: str = "http://192.168.1.152",
    host: str = "0.0.0.0",
    port: int = 8080
) -> ThreadedHTTPServer:
    """Creates and starts the HTTP server."""
    FieldwatchRequestHandler.db = db
    FieldwatchRequestHandler.gateway_url = gateway_url

    server_address = (host, port)
    httpd = ThreadedHTTPServer(server_address, FieldwatchRequestHandler)
    logger.info(f"Fieldwatch Dashboard serving at http://localhost:{port}/")
    return httpd
