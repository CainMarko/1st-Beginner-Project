"""MicroPython L76 GNSS driver for the Heltec WiFi LoRa 32 V4.

Reads NMEA sentences from the L76 module over UART (GPIO39 RX / GPIO38 TX)
and parses GGA, RMC, and GSV sentences to extract position, fix quality,
satellite count, and time. The L76 supports GPS, GLONASS, QZSS, and SBAS.

NMEA sentence format: $TALKER,TYPE,field1,field2,...*CHECKSUM
Common talker IDs: GP (GPS), GL (GLONASS), GN (combined)
"""

import time
import machine

import config


class GNSS:
    """L76 GNSS module driver over UART.

    Usage:
        gps = GNSS()
        gps.power_on()
        loc = gps.get_location(timeout_ms=90000)
        if loc:
            print("Lat:", loc["latitude"], "Lon:", loc["longitude"])
    """

    def __init__(self):
        self.power = machine.Pin(config.GNSS_POWER_PIN, machine.Pin.OUT, value=0)
        self.rst = machine.Pin(config.GNSS_RST_PIN, machine.Pin.OUT, value=1)
        self.wakeup = machine.Pin(config.GNSS_WAKEUP_PIN, machine.Pin.OUT, value=1)

        # UART1 for GNSS — ESP RX on GPIO39, ESP TX on GPIO38
        self.uart = machine.UART(
            1,
            baudrate=config.GNSS_UART_BAUD,
            rx=machine.Pin(config.GNSS_RX_PIN),
            tx=machine.Pin(config.GNSS_TX_PIN),
            timeout=500,
            rxbuf=1024,
        )
        self._fix = False
        self._satellites = 0
        self._latitude = None
        self._longitude = None
        self._altitude = None
        self._speed = None
        self._course = None
        self._datetime = None
        self._hdop = None

    def power_on(self):
        """Enable power to the GNSS module via VGNSS_Ctrl."""
        self.power.value(1)
        self.rst.value(1)
        self.wakeup.value(1)
        time.sleep_ms(100)
        print("GNSS: Power on (VGNSS_Ctrl=HIGH)")

    def power_off(self):
        """Disable GNSS power to save battery."""
        self.power.value(0)
        self.wakeup.value(0)
        print("GNSS: Power off")

    def _read_nmea(self):
        """Read available NMEA sentences from UART. Returns list of strings."""
        sentences = []
        while True:
            line = self.uart.readline()
            if line is None:
                break
            line = line.decode("ascii", "replace").strip()
            if line.startswith("$") and "*" in line:
                sentences.append(line)
        return sentences

    def _parse(self, sentence):
        """Parse a single NMEA sentence and update internal state."""
        # Strip $ prefix and *checksum suffix
        body = sentence[1:]  # remove $
        if "*" not in body:
            return
        fields = body.split("*")[0].split(",")

        talker_type = fields[0]  # e.g. GPGGA, GNRMC, GPGSV

        if talker_type.endswith("GGA"):
            self._parse_gga(fields)
        elif talker_type.endswith("RMC"):
            self._parse_rmc(fields)
        elif talker_type.endswith("GSV"):
            self._parse_gsv(fields)

    def _parse_gga(self, fields):
        """$xxGGA: fix quality, satellites, HDOP, altitude."""
        # GGA: time, lat, N/S, lon, E/W, fix, sats, hdop, alt, M, geoid, M, ...
        if len(fields) < 10:
            return
        try:
            fix_quality = int(fields[6]) if fields[6] else 0
        except ValueError:
            fix_quality = 0
        self._fix = fix_quality > 0

        if fix_quality > 0:
            self._latitude = self._parse_coord(fields[2], fields[3])
            self._longitude = self._parse_coord(fields[4], fields[5])
            try:
                self._satellites = int(fields[7]) if fields[7] else 0
            except ValueError:
                pass
            self._hdop = float(fields[8]) if fields[8] else None
            self._altitude = float(fields[9]) if fields[9] else None

    def _parse_rmc(self, fields):
        """$xxRMC: time, status, lat, lon, speed, course, date."""
        # RMC: time, status, lat, N/S, lon, E/W, speed, course, date, magvar
        if len(fields) < 10:
            return
        status = fields[2]  # A = active, V = void
        if status == "A":
            self._fix = True
            self._latitude = self._parse_coord(fields[3], fields[4])
            self._longitude = self._parse_coord(fields[5], fields[6])
            self._speed = float(fields[7]) if fields[7] else None  # knots
            self._course = float(fields[8]) if fields[8] else None  # degrees
            self._datetime = self._parse_datetime(fields[1], fields[9])
        else:
            self._fix = False

    def _parse_gsv(self, fields):
        """$xxGSV: satellites in view. Update satellite count from last msg."""
        # GSV: total msgs, msg num, sats in view, [sat details...]
        if len(fields) < 4:
            return
        try:
            total_msgs = int(fields[1])
            msg_num = int(fields[2])
            sats_in_view = int(fields[3])
            if msg_num == total_msgs:
                self._satellites = sats_in_view
        except ValueError:
            pass

    @staticmethod
    def _parse_coord(value, direction):
        """Parse NMEA coordinate (ddmm.mmmm or dddmm.mmmm) to decimal degrees."""
        if not value or not direction:
            return None
        try:
            # Degrees = integer part before the last 2 digits of the minutes
            dot_pos = value.index(".")
            deg_len = dot_pos - 2  # 2 for latitude, 3 for longitude
            degrees = float(value[:deg_len])
            minutes = float(value[deg_len:])
            decimal = degrees + minutes / 60.0
            if direction in ("S", "W"):
                decimal = -decimal
            return round(decimal, 6)
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _parse_datetime(time_str, date_str):
        """Parse NMEA time (hhmmss.ss) and date (ddmmyy) to a tuple."""
        if not time_str or not date_str:
            return None
        try:
            hh = int(time_str[0:2])
            mm = int(time_str[2:4])
            ss = int(time_str[4:6])
            dd = int(date_str[0:2])
            mo = int(date_str[2:4])
            yy = int(date_str[4:6])
            year = 2000 + yy if yy < 80 else 1900 + yy
            return (year, mo, dd, hh, mm, ss)
        except (ValueError, IndexError):
            return None

    def update(self):
        """Read and parse all available NMEA sentences from the UART."""
        sentences = self._read_nmea()
        for s in sentences:
            self._parse(s)
        return len(sentences)

    def get_location(self, timeout_ms=None):
        """Block until a fix is obtained or timeout. Returns dict or None."""
        timeout_ms = timeout_ms or config.GNSS_FIX_TIMEOUT_MS
        start = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            self.update()
            if self._fix and self._latitude is not None and self._longitude is not None:
                return {
                    "latitude": self._latitude,
                    "longitude": self._longitude,
                    "altitude": self._altitude,
                    "satellites": self._satellites,
                    "hdop": self._hdop,
                    "speed_knots": self._speed,
                    "course_deg": self._course,
                    "datetime": self._datetime,
                    "fix": True,
                }
            time.sleep_ms(500)

        print("GNSS: No fix within %dms" % timeout_ms)
        return None

    @property
    def has_fix(self):
        return self._fix

    @property
    def satellites(self):
        return self._satellites
