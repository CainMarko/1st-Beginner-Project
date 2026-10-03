import network
import socket
import time
import json
import gc

import secrets
import config
import storage


# ==================================================
# Wi-Fi
# ==================================================

def connect_wifi():

    # Set country code if provided, otherwise default to US
    try:
        country = getattr(secrets, "WIFI_COUNTRY", "US")
        network.country(country)
    except Exception:
        pass

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():

        print("Connecting to Wi-Fi...")

        wlan.connect(
            secrets.WIFI_SSID,
            secrets.WIFI_PASSWORD
        )

        timeout = 30

        while not wlan.isconnected() and timeout > 0:

            time.sleep(1)

            print(".", end="")

            timeout -= 1

    if not wlan.isconnected():

        print()
        raise RuntimeError("Wi-Fi connection failed. Check SSID, password, and router.")

    ip = wlan.ifconfig()[0]

    print()
    print("Connected!")
    print("IP address:", ip)

    return wlan, ip


# ==================================================
# Status
# ==================================================

def get_status(wlan):

    return {
        "node_id": config.NODE_ID,
        "firmware": config.FIRMWARE_VERSION,
        "schema_version": config.SCHEMA_VERSION,
        "wifi_connected": wlan.isconnected(),
        "ip": wlan.ifconfig()[0],
        "uptime": time.ticks_ms() // 1000,
        "observation_count": storage.count_observations()
    }


# ==================================================
# Observation validation
# ==================================================

def validate_observation(observation):

    if not isinstance(observation, dict):
        return False, "observation must be a JSON object"

    required_fields = [
        "schema_version",
        "node_id",
        "timestamp",
        "radio"
    ]

    for field in required_fields:

        if field not in observation:

            return False, "missing field: " + field

    return True, None


# ==================================================
# Store observation
# ==================================================

def store_observation(observation):

    valid, error = validate_observation(
        observation
    )

    if not valid:

        return False, error

    return storage.save_observation(observation)


# ==================================================
# HTTP response
# ==================================================

def send_response(
    client,
    body,
    status="200 OK",
    content_type="application/json"
):

    body_bytes = body.encode("utf-8") if isinstance(body, str) else body
    header = (
        "HTTP/1.1 " + status + "\r\n"
        "Content-Type: " + content_type + "\r\n"
        "Content-Length: " + str(len(body_bytes)) + "\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("utf-8")

    try:
        client.sendall(header)
        # Stream body in 512-byte slices to prevent buffer exhaustion on large payloads
        offset = 0
        while offset < len(body_bytes):
            chunk = body_bytes[offset:offset + 512]
            client.sendall(chunk)
            offset += 512
    except OSError as e:
        print("Send error:", e)


# ==================================================
# Home page
# ==================================================

def home_page(wlan):

    status = get_status(wlan)

    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head><title>Pico W Field Node</title></head>\n"
        "<body>\n"
        "<h1>Pico W Field Node</h1>\n"
        "<h2>Status: ONLINE</h2>\n"
        "<p><b>Node:</b> " + str(status["node_id"]) + "</p>\n"
        "<p><b>Firmware:</b> " + str(status["firmware"]) + "</p>\n"
        "<p><b>IP:</b> " + str(status["ip"]) + "</p>\n"
        "<p><b>Uptime:</b> " + str(status["uptime"]) + " seconds</p>\n"
        "<p><b>Observations:</b> " + str(status["observation_count"]) + "</p>\n"
        "<hr>\n"
        "<p><a href=\"/status\">Status JSON</a></p>\n"
        "<p><a href=\"/observations\">Observations JSON</a></p>\n"
        "</body>\n"
        "</html>\n"
    )


# ==================================================
# HTTP parsing
# ==================================================

def get_content_length(request_text):

    lines = request_text.split("\r\n")

    for line in lines:

        if line.lower().startswith(
            "content-length:"
        ):

            try:

                return int(
                    line.split(
                        ":",
                        1
                    )[1].strip()
                )

            except Exception:

                return 0

    return 0


def get_request_body(request_text):

    separator = "\r\n\r\n"

    if separator not in request_text:

        return ""

    return request_text.split(
        separator,
        1
    )[1]


def read_http_request(client):

    # Set client timeout so slow/empty connections do not block the server
    try:
        client.settimeout(5.0)
    except Exception:
        pass

    data = b""

    # Read until HTTP headers are complete
    while b"\r\n\r\n" not in data:

        try:
            chunk = client.recv(512)
        except OSError:
            break

        if not chunk:

            break

        data += chunk

        if len(data) > 8192:

            break

    header_end = data.find(
        b"\r\n\r\n"
    )

    if header_end == -1:

        return data

    header_end += 4

    headers = data[:header_end]

    body = data[header_end:]

    # Determine expected body size
    header_text = headers.decode(
        "utf-8",
        "ignore"
    )

    content_length = get_content_length(
        header_text
    )

    # Read remaining body
    while len(body) < content_length:

        try:
            chunk = client.recv(512)
        except OSError:
            break

        if not chunk:

            break

        body += chunk

    return headers + body


# ==================================================
# Request handler
# ==================================================

def handle_request(
    client,
    request,
    wlan
):

    request_text = request.decode(
        "utf-8",
        "ignore"
    )

    print()
    print("Request:")
    first_line = request_text.split("\r\n")[0] if "\r\n" in request_text else request_text[:80]
    print(first_line)

    # ==================================================
    # GET /
    # ==================================================

    if request_text.startswith(
        "GET / HTTP"
    ):

        send_response(
            client,
            home_page(wlan),
            content_type="text/html"
        )

        return

    # ==================================================
    # GET /status
    # ==================================================

    if request_text.startswith(
        "GET /status"
    ):

        status = get_status(
            wlan
        )

        send_response(
            client,
            json.dumps(status)
        )

        return

    # ==================================================
    # GET /observations
    # ==================================================

    if request_text.startswith(
        "GET /observations"
    ):

        send_response(
            client,
            json.dumps(storage.get_observations())
        )

        return

    # ==================================================
    # POST /observation
    # ==================================================

    if request_text.startswith(
        "POST /observation"
    ):

        try:

            # Extract HTTP body
            body = get_request_body(
                request_text
            )

            if not body:

                raise ValueError(
                    "Empty request body"
                )

            # Parse JSON
            observation = json.loads(
                body
            )

            # Validate and store
            success, error = store_observation(
                observation
            )

            if not success:

                response = {
                    "success": False,
                    "error": error
                }

                send_response(
                    client,
                    json.dumps(response),
                    status="400 Bad Request"
                )

                return

            response = {
                "success": True,
                "stored": observation,
                "observation_count": storage.count_observations()
            }

            send_response(
                client,
                json.dumps(response)
            )

            print("Observation stored. Total count:", storage.count_observations())

            return

        except Exception as e:

            print("POST error:", e)

            response = {
                "success": False,
                "error": str(e)
            }

            send_response(
                client,
                json.dumps(response),
                status="400 Bad Request"
            )

            return

    # ==================================================
    # Unknown endpoint
    # ==================================================

    send_response(
        client,
        json.dumps({
            "error": "unknown endpoint"
        }),
        status="404 Not Found"
    )


# ==================================================
# Web server
# ==================================================

def start_server(ip):

    addr = socket.getaddrinfo(
        "0.0.0.0",
        80
    )[0][-1]

    server = socket.socket()

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    try:
        server.bind(addr)
    except OSError as e:
        print("Initial bind failed (" + str(e) + "), releasing socket...")
        server.close()
        gc.collect()
        time.sleep(1)
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(addr)

    server.listen(2)

    print()
    print("Pico W Field Node")
    print("-----------------")
    print("Node:", config.NODE_ID)
    print("Firmware:", config.FIRMWARE_VERSION)
    print()
    print("Web server running at:")
    print("http://" + ip)

    return server


# ==================================================
# Main
# ==================================================

def main():

    total_stored = storage.initialize()
    print("Storage initialized. Stored observations on disk:", total_stored)

    wlan, ip = connect_wifi()

    server = start_server(ip)

    try:

        while True:

            client = None

            try:

                client, address = server.accept()

                request = read_http_request(
                    client
                )

                handle_request(
                    client,
                    request,
                    wlan
                )

            except Exception as e:

                print(
                    "Server error:",
                    e
                )

            finally:

                if client:
                    try:
                        client.close()
                    except Exception:
                        pass
                gc.collect()

    except KeyboardInterrupt:

        print()
        print("Server stopped by user.")

    finally:

        try:
            server.close()
            print("Server socket closed cleanly.")
        except Exception:
            pass


# ==================================================
# Start
# ==================================================

if __name__ == "__main__":
    main()
