"""BSH D-Bus (Bosch/Siemens/Neff appliances), 9600 baud 8N1.

Frame layout (verified on a Neff S413K60S0E):

    LL DS CC CC <data...> CRC CRC

* ``LL``  = number of bytes after ``DS`` up to (excluding) the CRC, i.e. 2 command bytes + data length.
  Total frame length = LL + 4.
* ``DS``  = destination node. High nibble selects the node class (0x1x power module, 0x2x feedback).
* ``CC CC`` = command, big endian.
* CRC16/XMODEM (poly 0x1021, init 0, MSB first, no reflection) over ``LL .. last data byte``.
* A receiver acknowledges with one byte whose low nibble is 0xA (for example 0x1A, 0x2A).

A *burst* is everything received until the bus was idle for ~15 ms; it may contain several
frames and ACK bytes. The parser re-synchronises byte by byte after a CRC failure, exactly like the
firmware does, so "CRC!" noise is reproduced instead of hidden.
"""
from __future__ import annotations

from dataclasses import dataclass

NAME = "bshdbus"
SPEC = "bshdbus.yaml"


def crc16_xmodem(data: bytes, crc: int = 0) -> int:
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


@dataclass(frozen=True)
class Frame:
    offset: int          # byte offset inside the burst
    ds: int              # destination
    cmd: int             # command
    data: bytes          # payload without command bytes
    crc_ok: bool
    ack: int | None      # ACK byte directly after the frame, if any
    raw: bytes           # LL..CRC as received

    @property
    def key(self) -> str:
        return f"{self.ds:02x}/{self.cmd:04x}"


@dataclass
class BurstStats:
    ok: int = 0
    crc: int = 0
    noack: int = 0
    rest: int = 0        # bytes that could not be assigned to a frame


def build_frame(ds: int, cmd: int, data: bytes = b"") -> bytes:
    """Build a valid frame (used by tests and by the decoder spec checks; the collector never sends)."""
    body = bytes([len(data) + 2, ds, cmd >> 8, cmd & 0xFF]) + bytes(data)
    return body + crc16_xmodem(body).to_bytes(2, "big")


def parse_burst(data: bytes) -> tuple[list[Frame], BurstStats]:
    """Split a burst into frames. CRC-failing candidates are returned with ``crc_ok=False``."""
    frames: list[Frame] = []
    st = BurstStats()
    i, n = 0, len(data)
    while i < n:
        length = data[i] + 4
        if data[i] == 0 or length < 6 or i + length > n:
            st.rest += 1
            i += 1
            continue
        chunk = data[i:i + length]
        soll = crc16_xmodem(chunk[:-2])
        ist = (chunk[-2] << 8) | chunk[-1]
        ds, cmd, payload = chunk[1], (chunk[2] << 8) | chunk[3], bytes(chunk[4:-2])
        if soll != ist:
            st.crc += 1
            frames.append(Frame(i, ds, cmd, payload, False, None, bytes(chunk)))
            i += 1                      # resynchronise on the next byte
            continue
        st.ok += 1
        start = i
        ack = None
        if i + length < n and (data[i + length] & 0x0F) == 0x0A:
            ack = data[i + length]
            i += length + 1
        else:
            st.noack += 1
            i += length
        frames.append(Frame(start, ds, cmd, payload, True, ack, bytes(chunk)))
    return frames, st
