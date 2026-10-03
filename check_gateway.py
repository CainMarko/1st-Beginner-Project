import urllib.request
import json

res = urllib.request.urlopen("http://192.168.1.152/observations")
obs = json.loads(res.read().decode())
ble = [o for o in obs if o.get("radio") == "ble"]
wifi = [o for o in obs if o.get("radio") == "wifi"]

print("================================================================================")
print("LIVE BLE OBSERVATIONS: CONNECTABLE vs BROADCASTING BREAKDOWN")
print("================================================================================")
print("Total observations in cache:", len(obs))
print("Wi-Fi APs:", len(wifi), "| BLE Devices:", len(ble))
print("--------------------------------------------------------------------------------")
print(f"{'MAC ADDRESS':<20} | {'RSSI':<5} | {'STATUS':<15} | {'NAME':<12} | {'MFG':<6}")
print("--------------------------------------------------------------------------------")

connectable_count = 0
broadcast_count = 0

for b in ble:
    is_conn = b.get("connectable")
    if is_conn is True:
        status = "CONNECTABLE"
        connectable_count += 1
    elif is_conn is False:
        status = "BROADCAST ONLY"
        broadcast_count += 1
    else:
        status = "UNKNOWN"

    name = b.get("ssid") or "—"
    mfg = b.get("manufacturer") or "—"
    rssi = str(b.get("rssi"))

    print(f"{b.get('address'):<20} | {rssi:<5} | {status:<15} | {name:<12} | {mfg:<6}")

print("================================================================================")
print(f"Summary: {connectable_count} Connectable Devices, {broadcast_count} Pure Broadcasters (Non-Connectable)")
print("================================================================================")
