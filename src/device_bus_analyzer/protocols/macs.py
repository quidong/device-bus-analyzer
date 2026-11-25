"""Electrolux/AEG MACS bus (heat-pump tumble dryer), 9600 baud 8E1, inverted logic (idle = 0 V).

Frame layout (confirmed on an AEG heat-pump dryer, 246 of 249 frames with a valid checksum):

    C9 DD SS LL <payload: LL bytes> XX

* ``C9``  message marker (some documents print it as 9C).
* ``DD``  destination, ``SS`` source. Unlike the BSH D-Bus the sender is ON THE WIRE.
* ``LL``  payload length; the frame is LL + 5 bytes long.
* ``XX``  XOR over all preceding bytes of the frame (C9 .. last payload byte).
* The first payload byte is the message *type* (0x5F heartbeat, 0x50 program selection, ...).
* The receiver acknowledges with three bytes ``98 XX XX2``: XX is the checksum byte of the acknowledged
  message, XX2 the XOR of the two preceding ACK bytes. The ACK is only attached when XX matches.

Mapping onto the shared :class:`Frame` record (so storage, API and frontend work unchanged):

* ``ds``   = destination address
* ``cmd``  = ``source << 8 | type``  (key ``DD/SSTT``, e.g. ``2a/225f`` = heartbeat 0x22 -> 0x2A)
* ``data`` = payload WITHOUT the type byte (field byte 0 in the spec is the second payload byte)
* ``ack``  = 0x98 when a valid ACK followed the message, otherwise ``None``

A burst is whatever arrives before the bus was idle (firmware: 20 ms). A single frame must never be split
across two bursts; a frame that is cut off at the end of a burst is counted as rest bytes, never guessed.
"""
from __future__ import annotations

from .bshdbus import BurstStats, Frame

NAME = "macs"
SPEC = "macs.yaml"

MARKER = 0xC9
ACK_MARKER = 0x98


def checksum(data: bytes) -> int:
    c = 0
    for b in data:
        c ^= b
    return c


def build_frame(dest: int, src: int, payload: bytes) -> bytes:
    """Build a valid message (tests and spec checks only; the collector never sends)."""
    body = bytes([MARKER, dest, src, len(payload)]) + bytes(payload)
    return body + bytes([checksum(body)])


def build_ack(message: bytes) -> bytes:
    """ACK for a complete message frame: 98, its checksum byte, XOR of those two."""
    return bytes([ACK_MARKER, message[-1], ACK_MARKER ^ message[-1]])


def parse_burst(data: bytes) -> tuple[list[Frame], BurstStats]:
    """Split a burst into messages. A checksum failure is returned with ``crc_ok=False`` and the parser
    resynchronises on the next byte, like the BSH decoder, so glued or damaged frames show up as noise."""
    frames: list[Frame] = []
    st = BurstStats()
    i, n = 0, len(data)
    while i < n:
        if data[i] != MARKER or i + 5 > n:
            st.rest += 1
            i += 1
            continue
        length = data[i + 3]
        if length == 0:                               # every message has a type byte: LL = 0 is a disturbance whose
            st.rest += 1                              # one-byte XOR happened to fit (seen once: C9 20 20 00 C9)
            i += 1
            continue
        end = i + 5 + length
        if end > n:                                   # cut off at the end of the burst
            st.rest += 1
            i += 1
            continue
        raw = bytes(data[i:end])
        dest, src, payload = raw[1], raw[2], raw[4:-1]
        typ = payload[0] if payload else 0x00
        cmd = (src << 8) | typ
        body = payload[1:]
        if checksum(raw[:-1]) != raw[-1]:
            st.crc += 1
            frames.append(Frame(i, dest, cmd, body, False, None, raw))
            i += 1
            continue
        st.ok += 1
        ack = None
        nxt = i + len(raw)
        if (nxt + 3 <= n and data[nxt] == ACK_MARKER and data[nxt + 1] == raw[-1]
                and data[nxt + 2] == ACK_MARKER ^ raw[-1]):
            ack = ACK_MARKER
            nxt += 3
        else:
            st.noack += 1
        frames.append(Frame(i, dest, cmd, body, True, ack, raw))
        i = nxt
    return frames, st
