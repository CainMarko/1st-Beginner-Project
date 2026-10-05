"""MicroPython SX1262 LoRa driver for the Heltec WiFi LoRa 32 V4.

Minimal SX1262 SPI interface: init, send, receive. Pin assignments come
from config.py and match the S3R2 variant of the Heltec V4 board.

Opcodes from Semtech SX126x datasheet v3.1 (Table 13-36).
"""

import time
import machine
import struct

import config

# ── SX1262 SPI Command Opcodes ──────────────────────────────────────
CMD_SET_STANDBY         = 0x80
CMD_SET_PACKET_TYPE     = 0x8A
CMD_SET_RF_FREQ          = 0x86
CMD_SET_TX_PARAMS        = 0x8E
CMD_SET_MOD_PARAMS       = 0x8C
CMD_SET_PKT_PARAMS       = 0x8B
CMD_SET_DIO_IRQ          = 0x97
CMD_GET_IRQ_STATUS       = 0x98
CMD_CLEAR_IRQ_STATUS     = 0x99
CMD_SET_RX               = 0x82
CMD_SET_TX               = 0x83
CMD_SET_BUFFER_BASE_ADDR = 0x8F
CMD_GET_RX_BUFFER_STATUS = 0x93
CMD_WRITE_BUFFER         = 0x0E
CMD_READ_BUFFER          = 0x02
CMD_WRITE_REGISTER       = 0x0D
CMD_READ_REGISTER        = 0x1D

# IRQ bits
IRQ_TX_DONE    = 1 << 0
IRQ_RX_DONE    = 1 << 1
IRQ_CRC_ERR    = 1 << 5
IRQ_CAD_DONE   = 1 << 6
IRQ_TIMEOUT    = 1 << 8
IRQ_ALL        = 0x03FF

# Packet types
PKT_TYPE_LORA  = 0x01

# Standby configs
STDBY_RC       = 0x00

# Register addresses
REG_SYNC_WORD  = 0x0740

# Bandwidth encoding table
_BW_CODES = {
    7800: 0x00, 10400: 0x01, 15600: 0x02, 20800: 0x03,
    31200: 0x04, 41600: 0x05, 62500: 0x06,
    125000: 0x07, 250000: 0x08, 500000: 0x09,
}


class SX1262:
    """Minimal MicroPython SX1262 LoRa transceiver for Heltec V4."""

    def __init__(self, freq=None, sf=None, bw=None, cr=None,
                 tx_power=None, sync_word=None):
        # Pins from config
        self.nss = machine.Pin(config.LORA_NSS, machine.Pin.OUT, value=1)
        self.rst = machine.Pin(config.LORA_RST, machine.Pin.OUT, value=1)
        self.busy = machine.Pin(config.LORA_BUSY, machine.Pin.IN)
        self.dio1 = machine.Pin(config.LORA_DIO1, machine.Pin.IN)

        # SPI bus 2 (FSPI on ESP32-S3)
        self.spi = machine.SPI(
            2,
            baudrate=8_000_000,
            sck=machine.Pin(config.LORA_SCK),
            mosi=machine.Pin(config.LORA_MOSI),
            miso=machine.Pin(config.LORA_MISO),
        )

        # FEM control
        self._fem_en = machine.Pin(config.LORA_FEM_EN, machine.Pin.OUT, value=1)
        self._pa_ctx = machine.Pin(config.LORA_PA_CTX, machine.Pin.OUT, value=1)
        self._vfem = machine.Pin(config.LORA_VFEM_CTRL, machine.Pin.OUT, value=1)

        # Radio params
        self.freq = freq or config.LORA_FREQUENCY
        self.sf = sf or config.LORA_SPREADING_FACTOR
        self.bw = bw or config.LORA_BANDWIDTH
        self.cr = cr or config.LORA_CODING_RATE
        self.tx_power = tx_power if tx_power is not None else config.LORA_TX_POWER
        self.sync_word = sync_word or config.LORA_SYNC_WORD
        self._initialised = False

    # ── Low-level SPI ────────────────────────────────────────────────

    def _wait_busy(self):
        """Block until BUSY pin goes LOW (radio ready for SPI)."""
        deadline = time.ticks_add(time.ticks_ms(), 1000)
        while self.busy.value():
            if time.ticks_diff(time.ticks_ms(), deadline) > 0:
                raise RuntimeError("SX1262 BUSY timeout")

    def _write_cmd(self, opcode, data=b""):
        """Send opcode + payload, no response expected."""
        self._wait_busy()
        self.nss.value(0)
        try:
            self.spi.write(bytes([opcode]) + bytes(data))
        finally:
            self.nss.value(1)

    def _read_cmd(self, opcode, read_len):
        """Send opcode, then read read_len bytes. SX1262 requires a NOP gap."""
        self._wait_busy()
        self.nss.value(0)
        try:
            self.spi.write(bytes([opcode]))
            # NOP dummy bytes to clock out the response
            buf = bytearray(read_len)
            self.spi.write_readinto(b"\x00" * read_len, buf)
            return bytes(buf)
        finally:
            self.nss.value(1)

    def _write_reg(self, addr, data):
        """Write to a register (3-byte big-endian address)."""
        addr_bytes = struct.pack(">I", addr)[1:]  # low 3 bytes
        self._write_cmd(CMD_WRITE_REGISTER, addr_bytes + bytes(data))

    def _read_reg(self, addr, read_len=1):
        """Read from a register (3-byte big-endian address)."""
        addr_bytes = struct.pack(">I", addr)[1:]
        self._wait_busy()
        self.nss.value(0)
        try:
            self.spi.write(bytes([CMD_READ_REGISTER]) + addr_bytes)
            buf = bytearray(read_len)
            self.spi.write_readinto(b"\x00" * read_len, buf)
            return bytes(buf)
        finally:
            self.nss.value(1)

    # ── Public API ──────────────────────────────────────────────────

    def init(self):
        """Hard-reset and configure the radio for LoRa TX/RX."""
        # Hardware reset
        self.rst.value(0)
        time.sleep_ms(10)
        self.rst.value(1)
        time.sleep_ms(10)

        # Enable FEM
        self._fem_en.value(1)
        self._pa_ctx.value(1)
        self._vfem.value(1)
        time.sleep_ms(5)

        # Standby on RC oscillator (no TCXO on V4)
        self._write_cmd(CMD_SET_STANDBY, bytes([STDBY_RC]))
        time.sleep_ms(5)

        # Packet type: LoRa
        self._write_cmd(CMD_SET_PACKET_TYPE, bytes([PKT_TYPE_LORA]))

        # RF frequency: reg = freq * 2^25 / 32 MHz
        rf_reg = int(self.freq * (1 << 25) / 32_000_000)
        self._write_cmd(CMD_SET_RF_FREQ, struct.pack(">I", rf_reg))

        # Modulation params: SF, BW code, coding rate
        bw_code = _BW_CODES.get(self.bw, 0x07)
        self._write_cmd(CMD_SET_MOD_PARAMS, bytes([self.sf, bw_code, self.cr]))

        # Packet params: preamble(2B), explicit header, payload len(0=variable),
        # CRC on, standard IQ
        pkt = struct.pack(">H", config.LORA_PREAMBLE_LEN)
        pkt += bytes([0x00, 0x00, 0x01, 0x00])
        self._write_cmd(CMD_SET_PKT_PARAMS, pkt)

        # Sync word (private network)
        self._write_reg(REG_SYNC_WORD, struct.pack(">H", self.sync_word))

        # TX power + ramp time (200us = 0x04)
        self._write_cmd(CMD_SET_TX_PARAMS, bytes([self.tx_power, 0x04]))

        # Buffer base addresses: TX=0x00, RX=0x00
        self._write_cmd(CMD_SET_BUFFER_BASE_ADDR, bytes([0x00, 0x00]))

        # Clear IRQs
        self._write_cmd(CMD_CLEAR_IRQ_STATUS, struct.pack(">H", IRQ_ALL))

        # DIO1 IRQ mapping
        irq_mask = IRQ_TX_DONE | IRQ_RX_DONE | IRQ_TIMEOUT | IRQ_CRC_ERR
        self._write_cmd(CMD_SET_DIO_IRQ, struct.pack(">HH", irq_mask, irq_mask))

        self._initialised = True
        print("LoRa: SX1262 init OK — %dMHz SF%d BW%d CR4/%d %ddBm"
              % (self.freq // 1_000_000, self.sf, self.bw // 1000,
                 self.cr, self.tx_power))

    def send(self, data, timeout_ms=5000):
        """Transmit payload bytes. Returns True on success."""
        if not self._initialised:
            raise RuntimeError("SX1262 not initialised")
        if isinstance(data, str):
            data = data.encode("utf-8")
        if len(data) > 255:
            raise ValueError("Payload too large (max 255 bytes)")

        # Update payload length in packet params
        pkt = struct.pack(">H", config.LORA_PREAMBLE_LEN)
        pkt += bytes([0x00, len(data), 0x01, 0x00])
        self._write_cmd(CMD_SET_PKT_PARAMS, pkt)

        # Write payload to buffer at offset 0
        self._wait_busy()
        self.nss.value(0)
        try:
            self.spi.write(bytes([CMD_WRITE_BUFFER, 0x00]) + data)
        finally:
            self.nss.value(1)

        # Clear IRQs, enter TX with timeout
        self._write_cmd(CMD_CLEAR_IRQ_STATUS, struct.pack(">H", IRQ_ALL))
        tx_timeout = timeout_ms * 64  # ~15.625us units
        self._write_cmd(CMD_SET_TX, struct.pack(">I", tx_timeout)[1:])

        # Wait for DIO1 or overall timeout
        start = time.ticks_ms()
        while not self.dio1.value():
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                self._write_cmd(CMD_CLEAR_IRQ_STATUS, struct.pack(">H", IRQ_ALL))
                return False
            time.sleep_ms(1)

        status = self._get_irq_status()
        self._clear_irqs()
        return bool(status & IRQ_TX_DONE)

    def receive(self, timeout_ms=10000):
        """Listen for a packet. Returns payload bytes or None on timeout."""
        if not self._initialised:
            raise RuntimeError("SX1262 not initialised")

        self._write_cmd(CMD_CLEAR_IRQ_STATUS, struct.pack(">H", IRQ_ALL))
        rx_timeout = timeout_ms * 64
        self._write_cmd(CMD_SET_RX, struct.pack(">I", rx_timeout)[1:])

        start = time.ticks_ms()
        while not self.dio1.value():
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                return None
            time.sleep_ms(1)

        status = self._get_irq_status()
        self._clear_irqs()

        if status & IRQ_CRC_ERR:
            print("LoRa: CRC error")
            return None
        if not (status & IRQ_RX_DONE):
            return None

        # Get payload length and start offset
        raw = self._read_cmd(CMD_GET_RX_BUFFER_STATUS, 2)
        payload_len, offset = raw[0], raw[1]
        if payload_len == 0:
            return b""

        # Read payload from buffer
        self._wait_busy()
        self.nss.value(0)
        try:
            self.spi.write(bytes([CMD_READ_BUFFER, offset]))
            buf = bytearray(payload_len)
            self.spi.write_readinto(b"\x00" * payload_len, buf)
            return bytes(buf)
        finally:
            self.nss.value(1)

    # ── Helpers ─────────────────────────────────────────────────────

    def _get_irq_status(self):
        raw = self._read_cmd(CMD_GET_IRQ_STATUS, 2)
        return struct.unpack(">H", raw)[0] if len(raw) >= 2 else 0

    def _clear_irqs(self, mask=IRQ_ALL):
        self._write_cmd(CMD_CLEAR_IRQ_STATUS, struct.pack(">H", mask))
