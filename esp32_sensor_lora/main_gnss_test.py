"""Basic GNSS location fix test for the Heltec WiFi LoRa 32 V4.

Flash this as main.py to test the L76 GNSS module. Take the board outdoors
or near a window with clear sky view for a fix.
"""

import time
import config
from gnss_driver import GNSS

def main():
    print("GNSS test starting...")
    gps = GNSS()
    gps.power_on()

    print("Waiting for fix (timeout 90s)...")
    loc = gps.get_location(timeout_ms=90000)

    if loc:
        print("FIX ACQUIRED!")
        print("  Latitude:  ", loc["latitude"])
        print("  Longitude: ", loc["longitude"])
        print("  Altitude:  ", loc["altitude"])
        print("  Satellites:", loc["satellites"])
        print("  HDOP:      ", loc["hdop"])
        print("  Speed (kn):", loc["speed_knots"])
        print("  Course:    ", loc["course_deg"])
        if loc["datetime"]:
            print("  DateTime:  ", loc["datetime"])
    else:
        print("No fix acquired.")
        print("  Satellites in view:", gps.satellites)

    gps.power_off()

if __name__ == "__main__":
    main()
