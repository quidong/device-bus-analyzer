"""Logformat 1 parser (see docs/LOGFORMAT.md) plus tolerant parsing of legacy firmware lines."""
from __future__ import annotations

import re

ANSI = re.compile(r"\x1b\[[0-9;]*m")
HOST_TS = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\.(\d{3})\]")
RE_RAW1 = re.compile(r"\bRAW1 seq=(\d+) t_us=(\d+) dt_us=(\d+) n=(\d+) hex=([0-9a-fA-F]*)")
RE_HB1 = re.compile(r"\bHB1 seq=(\d+) t_us=(\d+) epoch=(\d+) bytes=(\d+) bursts=(\d+) ok=(\d+) crc=(\d+) noack=(\d+) rest=(\d+)")
RE_FRAME = re.compile(r"\bFRAME ([0-9A-Fa-f]{6,})\s+(OK|CRC!)(?: ACK ([0-9A-Fa-f]{2}))?")
RE_RECEIVED = re.compile(r"Received frame dest 0x([0-9a-fA-F]{2}) cmd 0x([0-9a-fA-F]{4}): 0x([0-9a-fA-F]*)")
HB_FIELDS = ("seq", "t_us", "epoch", "bytes", "bursts", "ok", "crc", "noack", "rest")


def host_seconds(line: str) -> float | None:
    m = HOST_TS.match(ANSI.sub("", line))
    if not m:
        return None
    h, mi, s, ms = map(int, m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000


def parse_line(line: str) -> dict | None:
    """Return a dict with key 'typ' in RAW1 | HB1 | FRAME | RECEIVED, or None for unrelated lines.

    A RAW1 line whose length field disagrees with its hex gets ``{'typ': 'RAW1', 'fehler': ...}``.
    """
    z = ANSI.sub("", line.rstrip("\r\n"))
    host = host_seconds(z)
    m = RE_RAW1.search(z)
    if m:
        seq, t_us, dt_us, n, hexs = m.groups()
        if len(hexs) % 2:
            return {"typ": "RAW1", "fehler": "odd hex length", "host": host}
        data = bytes.fromhex(hexs)
        if len(data) != int(n):
            return {"typ": "RAW1", "fehler": f"n={n} but {len(data)} bytes", "host": host}
        return {"typ": "RAW1", "seq": int(seq), "t_us": int(t_us), "dt_us": int(dt_us), "data": data, "host": host}
    m = RE_HB1.search(z)
    if m:
        d = dict(zip(HB_FIELDS, map(int, m.groups())))
        d.update(typ="HB1", host=host)
        return d
    m = RE_FRAME.search(z)
    if m:
        hexs, status, ack = m.groups()
        if len(hexs) % 2:
            return None
        raw = bytes.fromhex(hexs)            # DS CC CC data (no LL, no CRC) as printed by the firmware
        return {"typ": "FRAME", "ds": raw[0], "cmd": (raw[1] << 8) | raw[2], "data": raw[3:], "crc_ok": status == "OK",
                "ack": int(ack, 16) if ack else None, "host": host}
    m = RE_RECEIVED.search(z)
    if m:
        ds, cmd, data = m.groups()
        if len(data) % 2:
            return None
        return {"typ": "RECEIVED", "ds": int(ds, 16), "cmd": int(cmd, 16), "data": bytes.fromhex(data), "crc_ok": True,
                "ack": None, "host": host}
    return None


def find_gaps(entries) -> list[str]:
    """Check RAW1 sequence numbers and heartbeats. A restart (t_us falls back) starts a new section."""
    out, last_seq, last_t = [], None, None
    for e in entries:
        if e is None:
            continue
        if "fehler" in e:
            out.append(f"broken line: {e['fehler']}")
            continue
        if e["typ"] not in ("RAW1", "HB1"):
            continue
        if last_t is not None and e["t_us"] < last_t:
            last_seq = None
        last_t = e["t_us"]
        if e["typ"] == "RAW1":
            if last_seq is not None and e["seq"] != last_seq + 1:
                out.append(f"gap: seq {last_seq} -> {e['seq']} ({e['seq'] - last_seq - 1} bursts missing)")
            last_seq = e["seq"]
        elif last_seq is not None and e["seq"] != last_seq:
            out.append(f"heartbeat seq={e['seq']}, last seen seq={last_seq}: bursts lost")
            last_seq = e["seq"]
    return out
