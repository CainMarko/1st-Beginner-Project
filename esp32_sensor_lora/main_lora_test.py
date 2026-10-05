"""Basic LoRa send/receive test for the Heltec WiFi LoRa 32 V4.

Flash this as main.py to test SX1262 communication. One board should run
as sender, the other as receiver. Set MODE below accordingly.
"""

import time
import config
from lora_driver import SX1262

# Set to "sender" or "receiver"
MODE = "sender"

def main():
    radio = SX1262()
    radio.init()

    if MODE == "sender":
        print("LoRa SENDER mode — transmitting every 5 seconds")
        counter = 0
        while True:
            counter += 1
            msg = "Hello LoRa #%d from %s" % (counter, config.NODE_ID)
            print("TX:", msg)
            ok = radio.send(msg, timeout_ms=3000)
            if ok:
                print("TX OK")
            else:
                print("TX FAILED")
            time.sleep(5)

    elif MODE == "receiver":
        print("LoRa RECEIVER mode — listening for packets")
        while True:
            payload = radio.receive(timeout_ms=15000)
            if payload is not None:
                print("RX:", payload.decode("utf-8", "replace"))
            else:
                print("RX: no packet (timeout)")


if __name__ == "__main__":
    main()
