"""HTTPS for the LAN: a small local certificate authority and a server certificate, created on first start in the data volume.

The CA certificate (``/tls/ca.crt``) is installed once on phones and computers; renewing the server certificate later needs no new
trust step. A certificate of your own (``DBA_TLS_CERT`` + ``DBA_TLS_KEY``) is used as it is. The server certificate lists the host
names and addresses from ``DBA_TLS_HOSTS`` (plus localhost and the container name) and is recreated when that list changes or when
it is about to expire. Keys never leave the data volume.
"""
from __future__ import annotations

import datetime as dt
import ipaddress
import os
import socket
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

CA_DAYS, LEAF_DAYS, RENEW_BEFORE_DAYS = 3650, 800, 30


@dataclass
class TlsFiles:
    cert: str
    key: str
    ca: str | None          # the certificate people install; None when the operator brought their own certificate
    own: bool
    hosts: list[str]
    expires: dt.datetime | None


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _write_key(path: Path, key) -> None:
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    os.chmod(path, 0o600)


def _names(hosts: list[str]) -> list[str]:
    out = ["localhost", "127.0.0.1", "::1"]
    try:
        out.append(socket.gethostname())
    except OSError:
        pass
    for h in hosts:
        h = h.strip()
        if h and h not in out:
            out.append(h)
    return out


def _san(names: list[str]) -> x509.SubjectAlternativeName:
    items: list[x509.GeneralName] = []
    for n in names:
        try:
            items.append(x509.IPAddress(ipaddress.ip_address(n)))
        except ValueError:
            items.append(x509.DNSName(n))
    return x509.SubjectAlternativeName(items)


def _make_ca(d: Path) -> tuple[x509.Certificate, object]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Device Bus Analyzer local CA"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Device Bus Analyzer")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(_now() - dt.timedelta(minutes=5)).not_valid_after(_now() + dt.timedelta(days=CA_DAYS))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, encipher_only=False, decipher_only=False), critical=True)
            .sign(key, hashes.SHA256()))
    _write_key(d / "ca.key", key)
    (d / "ca.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert, key


def _make_leaf(d: Path, ca_cert, ca_key, names: list[str]) -> x509.Certificate:
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Device Bus Analyzer")]))
            .issuer_name(ca_cert.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(_now() - dt.timedelta(minutes=5)).not_valid_after(_now() + dt.timedelta(days=LEAF_DAYS))
            .add_extension(_san(names), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=False, content_commitment=False, data_encipherment=False, key_agreement=True,
                                         key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    _write_key(d / "server.key", key)
    (d / "server.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert


def _load(path: Path) -> x509.Certificate:
    return x509.load_pem_x509_certificate(path.read_bytes())


def san_names(cert: x509.Certificate) -> list[str]:
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return []
    return [str(v) for v in san.get_values_for_type(x509.DNSName)] + [str(v) for v in san.get_values_for_type(x509.IPAddress)]


def ensure(data_dir: str | Path, hosts: list[str] | None = None, own_cert: str = "", own_key: str = "") -> TlsFiles:
    """Files for uvicorn. Creates the CA and the server certificate when missing, when the host list changed or shortly before expiry."""
    if own_cert and own_key:
        c = _load(Path(own_cert))
        return TlsFiles(own_cert, own_key, None, True, san_names(c), c.not_valid_after_utc)
    d = Path(data_dir) / "tls"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    names = _names(hosts or [])
    if (d / "ca.crt").is_file() and (d / "ca.key").is_file():
        ca_cert = _load(d / "ca.crt")
        ca_key = serialization.load_pem_private_key((d / "ca.key").read_bytes(), None)
    else:
        ca_cert, ca_key = _make_ca(d)
        for f in ("server.crt", "server.key"):
            (d / f).unlink(missing_ok=True)
    leaf = _load(d / "server.crt") if (d / "server.crt").is_file() and (d / "server.key").is_file() else None
    if leaf is None or set(san_names(leaf)) != set(names) or leaf.not_valid_after_utc - _now() < dt.timedelta(days=RENEW_BEFORE_DAYS):
        leaf = _make_leaf(d, ca_cert, ca_key, names)
    return TlsFiles(str(d / "server.crt"), str(d / "server.key"), str(d / "ca.crt"), False, san_names(leaf), leaf.not_valid_after_utc)


def fingerprint(path: str) -> str:
    return ":".join(f"{b:02X}" for b in _load(Path(path)).fingerprint(hashes.SHA256()))
