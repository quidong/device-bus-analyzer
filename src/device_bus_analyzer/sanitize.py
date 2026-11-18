"""Remove private details from ESPHome logs before they are shared: SSID/BSSID, MAC and IP addresses, hostnames,
keys and passwords. Bus data (RAW1 / FRAME / HB1) is left untouched."""
from __future__ import annotations

import re
import sys

RULES = [
    (re.compile(r"(SSID: ')[^']*(')"), r"\1<SSID>\2"),
    (re.compile(r"(BSSID: )[0-9A-Fa-f:]{17}"), r"\1<BSSID>"),
    (re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b"), "<MAC>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<IP>"),
    (re.compile(r"(Hostname: '?)[^'\s]+('?)"), r"\1<HOST>\2"),
    (re.compile(r"[A-Za-z0-9_-]+\.local\b"), "<HOST>.local"),
    (re.compile(r"(?i)((?:api[_ -]?key|password|passwort|psk|token|secret)\W{1,3})[A-Za-z0-9+/=_-]{8,}"), r"\1<SECRET>"),
]


def sanitize_line(line: str) -> str:
    for pattern, repl in RULES:
        if "!secret" in line and repl.endswith("<SECRET>"):     # references to secrets.yaml are not secrets
            continue
        line = pattern.sub(repl, line)
    return line


def sanitize_file(path: str, out=sys.stdout) -> None:
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:     # keep line endings unchanged
        for line in fh:
            out.write(sanitize_line(line))
