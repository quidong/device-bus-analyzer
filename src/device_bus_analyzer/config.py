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
    knowledge_url: str = ""          # override of the manifest URL for knowledge updates (default: the project repository)
    cookie_secure: bool = False
    tls: bool = True                 # serve HTTPS (DBA_TLS=0 only behind your own TLS proxy)
    tls_hosts: list[str] = field(default_factory=list)   # extra names/addresses in the server certificate
    tls_cert: str = ""
    tls_key: str = ""
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
        knowledge_url=env.get("KNOWLEDGE_URL", ""),
        cookie_secure=env.get("COOKIE_SECURE", "1" if env.get("DBA_TLS", "1") != "0" else "0") == "1",
        tls=env.get("DBA_TLS", "1") != "0",
        tls_hosts=[h for h in re.split(r"[,\s]+", env.get("DBA_TLS_HOSTS", "")) if h],
        tls_cert=env.get("DBA_TLS_CERT", ""), tls_key=env.get("DBA_TLS_KEY", ""),
        session_hours=int(env.get("SESSION_HOURS", "12")),
    )


_NAME = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_HOST = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]{0,251}[A-Za-z0-9])?$")


def validate_device_input(name: str, host: str, port: str | int, protocol: str, key: str | None, known_protocols) -> tuple[int, str | None]:
    """Validate the fields of the device dialog. Returns (port, normalised key). Raises ValueError with a short code."""
    import base64
    import binascii
    if not _NAME.match(name or ""):
        raise ValueError("bad_name")
    if protocol not in known_protocols:
        raise ValueError("bad_protocol")
    if host and not _HOST.match(host):
        raise ValueError("bad_host")
    try:
        p = int(port or 6053)
    except ValueError:
        raise ValueError("bad_port") from None
    if not 1 <= p <= 65535:
        raise ValueError("bad_port")
    k = (key or "").strip() or None
    if k:
        try:
            if len(base64.b64decode(k, validate=True)) != 32:
                raise ValueError("bad_key")
        except (binascii.Error, ValueError):
            raise ValueError("bad_key") from None
    return p, k
