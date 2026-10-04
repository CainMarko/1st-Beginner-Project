import urllib.request
import json

res = urllib.request.urlopen("http://192.168.1.152/observations")
obs = json.loads(res.read().decode())
ble = [o for o in obs if o.get("radio") == "ble"]
wifi = [o for o in obs if o.get("radio") == "wifi"]

print("=========================================================================================================")
print("LIVE FIELDWATCH OBSERVATIONS WITH DEVICE SIGNATURES & CONFIDENCE")
print("=========================================================================================================")
print(f"Total Cached: {len(obs)} | Wi-Fi Access Points: {len(wifi)} | BLE Peripherals: {len(ble)}")
print("---------------------------------------------------------------------------------------------------------")
print(f"{'MAC ADDRESS':<19} | {'RADIO':<5} | {'RSSI':<5} | {'NAME / SSID':<18} | {'MANUFACTURER':<18} | {'SIGNATURE':<18} | {'CONF'}")
print("---------------------------------------------------------------------------------------------------------")

for o in obs:
    addr = o.get("address") or "—"
    radio = o.get("radio") or "—"
    rssi = str(o.get("rssi") if o.get("rssi") is not None else "—")
    name = (o.get("ssid") or "—")[:18]
    mfg = (o.get("manufacturer") or "unknown")[:18]
    sig = (o.get("signature") or "unknown")[:18]
    conf = f"{o.get('confidence'):.2f}" if o.get("confidence") is not None else "—"

    print(f"{addr:<19} | {radio:<5} | {rssi:<5} | {name:<18} | {mfg:<18} | {sig:<18} | {conf}")

print("=========================================================================================================")
# Archetype breakdown
signatures_count = {}
for o in obs:
    s = o.get("signature") or "unclassified"
    signatures_count[s] = signatures_count.get(s, 0) + 1

breakdown_str = ", ".join(f"{k}: {v}" for k, v in sorted(signatures_count.items()))
print("Archetype Breakdown:", breakdown_str)
print("=========================================================================================================")
