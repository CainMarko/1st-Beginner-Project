# Pico W heartbeat setup

Arduino IDE is not used. The board runs MicroPython. You can load the files with Thonny, or by copying them to the board after the firmware is installed.

## Firmware

1. Unplug the Pico.
2. Hold BOOTSEL while plugging it into USB. A drive named `RPI-RP2` appears.
3. Copy the Pico W MicroPython `.uf2` file onto that drive. Use the **Pico W** build, not the plain Pico build. The official file is `RPI_PICO_W-20260824-v1.29.0.uf2` from the MicroPython Pico W download page.
4. The drive disappears and the board reboots with a USB serial port.

## Files

- `pico-hub/main.py` runs at power-up.
- `pico-hub/report.py` builds the log line.
- `secrets.py` is your Wi-Fi name and password. Copy `pico-hub/secrets.example.py` to `pico-hub/secrets.py` and replace the placeholders. Keep the real password out of the example file.

## Thonny

1. Install Thonny from https://thonny.org/.
2. Plug in the Pico after MicroPython is installed.
3. Open Thonny. Choose **Run > Configure interpreter > MicroPython (Raspberry Pi Pico)**.
4. Open `main.py` and `report.py`. Use **File > Save as** and pick **Raspberry Pi Pico**, saving each file under the same name.
5. Create `secrets.py` the same way if you want the board to join your Wi-Fi.
6. Unplug and replug the Pico, or press the stop/restart button in Thonny. The Shell pane shows the log.

## Log line

One line at boot, then one line about every 30 minutes:

```text
ticks_ms,pico-hub,WIFI_UP or WIFI_DOWN,rssi,tx_msgs,rx_msgs,tx_bytes,rx_bytes,tx_msgs_total,rx_msgs_total,tx_bytes_total,rx_bytes_total
```

- `rssi` is the signal strength of your own network. It is empty when that network was not measured.
- `tx_msgs`, `rx_msgs`, `tx_bytes`, and `rx_bytes` are the current 30-minute window.
- The four `*_total` fields are counts since boot.
- Those counts are the status lines this board sends. Incoming counts stay at 0 until a second Pico sends a heartbeat.

The onboard LED is on when the Pico is connected to your Wi-Fi.

Until `secrets.py` is on the board, the log prints a short note and then `WIFI_DOWN`.

The Pico W radio needs a two-letter country code before it will connect. The script uses `US` unless `secrets.py` sets `WIFI_COUNTRY` to another code.
