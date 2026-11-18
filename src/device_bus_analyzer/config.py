"""Configuration from environment variables (Portainer stack variables)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Device:
    name: str
    host: str
    port: int
    protocol: str
    key: str | None = None          # ESPHome API encryption key (noise PSK), from DBA_KEY_<NAME>


@dataclass
class Settings:
    db_path: str = "/data/bus.sqlite"
    devices: list[Device] = field(default_factory=list)
    admin_email: str = ""
    admin_password: str = ""
    admin_password_hash: str = ""
    session_secret: str = ""
    api_token: str = ""
    cookie_secure: bool = False
    session_hours: int = 12


_DEV = re.compile(r"^(?P<name>[A-Za-z0-9_-]+)@(?P<host>[^:/\s]+)(?::(?P<port>\d+))?/(?P<proto>[a-z0-9]+)$")


def parse_devices(spec: str, env: dict[str, str] | None = None) -> list[Device]:
    """DBA_DEVICES="geschirrspuler@host-or-ip:6053/bshdbus,trockner@host/macs"; keys via DBA_KEY_<NAME>."""
    env = os.environ if env is None else env
    out = []
    for part in filter(None, (p.strip() for p in spec.split(","))):
        m = _DEV.match(part)
        if not m:
            raise ValueError(f"bad device spec {part!r}, expected name@host[:port]/protocol")
        key = env.get("DBA_KEY_" + re.sub(r"[^A-Za-z0-9]", "_", m["name"]).upper()) or None
        out.append(Device(m["name"], m["host"], int(m["port"] or 6053), m["proto"], key))
    return out


def load(env: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ) if env is None else env
    return Settings(
        db_path=env.get("DBA_DB", "/data/bus.sqlite"),
        devices=parse_devices(env.get("DBA_DEVICES", ""), env),
        admin_email=env.get("ADMIN_EMAIL", "").strip().lower(),
        admin_password=env.get("ADMIN_PASSWORD", ""),
        admin_password_hash=env.get("ADMIN_PASSWORD_HASH", ""),
        session_secret=env.get("SESSION_SECRET", ""),
        api_token=env.get("API_TOKEN", ""),
        cookie_secure=env.get("COOKIE_SECURE", "0") == "1",
        session_hours=int(env.get("SESSION_HOURS", "12")),
    )
