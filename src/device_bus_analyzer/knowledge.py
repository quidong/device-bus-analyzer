"""Device knowledge (protocol specs, catalogue, recommended firmware) that can be updated from GitHub without a new container image.

The files ship inside the package, together with ``knowledge-manifest.json`` (version + SHA-256 of every file). An update downloads the
manifest from the repository, fetches the listed files, verifies the hashes, validates the result with the normal spec and catalogue
checks and only then makes it active (a directory next to the database; the bundled files stay untouched). Anything that fails leaves
the previous state in place. Only data files are ever fetched: YAML read with ``safe_load``, never code.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import threading
import time
import urllib.request
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Callable

FORMAT = 1                                   # raised when a spec/catalogue change needs a newer app
MANIFEST = "knowledge-manifest.json"
SIGNATURE = MANIFEST + ".sig"                # base64 Ed25519 signature over the manifest bytes
PUBKEY = "knowledge-pubkey.txt"              # base64 raw Ed25519 public key shipped in the package; when present, updates MUST be signed
DEFAULT_URL = "https://raw.githubusercontent.com/quidong/device-bus-analyzer/main/src/device_bus_analyzer/" + MANIFEST
NAME_OK = re.compile(r"^(spec/[a-z0-9_-]+\.yaml|catalog\.yaml|firmware/[A-Za-z0-9][A-Za-z0-9._-]*)$")
MAX_FILE = 1 << 20
MAX_FILES = 64
MAX_ALIASES = 40                             # YAML aliases per file: keeps a hostile file from expanding into gigabytes ("billion laughs")
MIN_INTERVAL = 60                            # seconds between real checks: buttons, the MCP tool and the daily job share this limit

_lock = threading.RLock()
_dir: Path | None = None                     # <data dir>/knowledge ; None = bundled files only


def configure(data_dir: str | Path | None) -> None:
    global _dir
    _dir = Path(data_dir) if data_dir else None
    reload()


def reload() -> None:
    from . import catalog, spec
    spec.load_spec.cache_clear()
    catalog._base.cache_clear()


def _pkg(rel: str) -> str:
    return resources.files("device_bus_analyzer").joinpath(rel).read_text(encoding="utf-8")


def bundled_manifest() -> dict:
    return json.loads(_pkg(MANIFEST))


def _active_dir() -> Path | None:
    return _dir / "active" if _dir and (_dir / "active" / MANIFEST).is_file() else None


def _vkey(version: str) -> tuple[str, int]:
    d, _, n = (version or "").partition(".")
    return d, int(n) if n.isdigit() else 0


def active_manifest() -> dict | None:
    d = _active_dir()
    if not d:
        return None
    try:
        m = json.loads((d / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return m if _vkey(m.get("version", "")) > _vkey(bundled_manifest().get("version", "")) else None   # a newer image wins over an old update


def read(rel: str) -> str:
    """A knowledge file: the active update if there is one and it has the file, else the packaged copy."""
    with _lock:
        if active_manifest() and rel in active_manifest().get("files", {}):
            try:
                return (_active_dir() / rel).read_text(encoding="utf-8")
            except OSError:
                pass
    return _pkg(rel)


def info() -> dict:
    b, a = bundled_manifest(), active_manifest()
    return {"bundled": b["version"], "active": (a or b)["version"], "source": "update" if a else "bundled", "format": FORMAT, "signed": pubkey() is not None}


# --- building the manifest (repository side) ---------------------------------------------------------------------------
def knowledge_files() -> list[str]:
    root = resources.files("device_bus_analyzer")
    names = [f"spec/{p.name}" for p in root.joinpath("spec").iterdir() if p.name.endswith(".yaml")]
    names += [f"firmware/{p.name}" for p in root.joinpath("firmware").iterdir() if p.is_file()]
    return sorted(names + ["catalog.yaml"])


def _digest(files: dict[str, str]) -> str:
    return hashlib.sha256("\n".join(f"{k} {v}" for k, v in sorted(files.items())).encode()).hexdigest()[:16]


def build_manifest(previous: dict | None = None, today: str | None = None) -> dict:
    files = {n: hashlib.sha256(_pkg(n).encode("utf-8")).hexdigest() for n in knowledge_files()}
    rev = _digest(files)
    if previous and previous.get("revision") == rev and previous.get("format") == FORMAT:
        return previous
    today = today or date.today().isoformat()
    d, n = _vkey((previous or {}).get("version", ""))
    return {"format": FORMAT, "version": f"{today}.{n + 1 if d == today else 1}", "revision": rev, "files": files}


def write_manifest() -> dict:
    path = Path(str(resources.files("device_bus_analyzer").joinpath(MANIFEST)))
    prev = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    m = build_manifest(prev)
    path.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return m


# --- signing: the maintainer signs the manifest, installations verify it before trusting any hash in it ------------------
def pubkey() -> str | None:
    try:
        t = resources.files("device_bus_analyzer").joinpath(PUBKEY).read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return None
    return t or None


def _load_public(b64: str):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(b64, validate=True))


def verify_signature(manifest_bytes: bytes, sig_b64: bytes | str, key_b64: str) -> bool:
    from cryptography.exceptions import InvalidSignature
    try:
        sig = base64.b64decode(sig_b64.strip() if isinstance(sig_b64, bytes) else sig_b64.strip(), validate=True)
        _load_public(key_b64).verify(sig, manifest_bytes)
        return True
    except (InvalidSignature, ValueError):
        return False


def generate_keypair(private_path: str | Path, write_public: bool = True) -> str:
    """Create an Ed25519 key. The private key goes to ``private_path`` (mode 600, never into the repository); returns the public key."""
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, ser.NoEncryption())
    path = Path(private_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    pub = base64.b64encode(key.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)).decode()
    if write_public:
        Path(str(resources.files("device_bus_analyzer").joinpath(PUBKEY))).write_text(pub + "\n", encoding="utf-8")
    return pub


def sign_manifest(private_path: str | Path) -> str:
    from cryptography.hazmat.primitives import serialization as ser
    key = ser.load_pem_private_key(Path(private_path).read_bytes(), password=None)
    mp = Path(str(resources.files("device_bus_analyzer").joinpath(MANIFEST)))
    sig = base64.b64encode(key.sign(mp.read_bytes())).decode()
    mp.with_name(SIGNATURE).write_text(sig + "\n", encoding="utf-8")
    return sig


# --- updating (installation side) --------------------------------------------------------------------------------------
Fetch = Callable[[str], bytes]


class _HttpsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise ValueError("redirect to a non-https address refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def http_fetch(url: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("only https is allowed")
    req = urllib.request.Request(url, headers={"User-Agent": "device-bus-analyzer"})
    with urllib.request.build_opener(_HttpsOnly).open(req, timeout=15) as r:           # noqa: S310  (scheme checked above)
        data = r.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError("file too large")
    return data


def _problems() -> list[str]:
    from . import catalog, protocols, spec
    out = []
    for p in protocols.PROTOCOLS:
        try:
            out += [f"{p}: {x}" for x in spec.validate_spec(p)]
        except Exception as exc:                                  # missing file, broken YAML ...
            out.append(f"{p}: {exc}")
    try:
        out += catalog.validate_catalog()
    except Exception as exc:
        out.append(f"catalog: {exc}")
    return out


def update(url: str = DEFAULT_URL, fetch: Fetch = http_fetch) -> dict:
    """Check for newer knowledge and activate it. Returns {'status': updated|current|needs_app_update|error, 'version', 'message'}."""
    from . import protocols
    with _lock:
        if _dir is None:
            return {"status": "error", "version": None, "message": "no data directory"}
        try:
            raw = fetch(url)
            key = pubkey()
            if key:                                               # signed updates: nothing in the manifest is trusted before this passes
                try:
                    sig = fetch(url + ".sig")
                except Exception:
                    sig = b""
                if not verify_signature(raw, sig, key):
                    return {"status": "error", "version": None, "message": "signature missing or invalid: update refused"}
            remote = json.loads(raw.decode("utf-8"))
            files = remote["files"]
            if remote.get("format", 0) > FORMAT:
                return {"status": "needs_app_update", "version": remote.get("version"), "message": "newer format"}
            cur = info()["active"]
            if _vkey(remote["version"]) <= _vkey(cur):
                return {"status": "current", "version": cur, "message": ""}
            if len(files) > MAX_FILES:
                return {"status": "error", "version": remote["version"], "message": "too many files"}
            need = {f"spec/{p}.yaml" for p in protocols.PROTOCOLS} | {"catalog.yaml"}
            if not need <= set(files) or not all(NAME_OK.match(n) and re.fullmatch(r"[0-9a-f]{64}", h) for n, h in files.items()):
                return {"status": "error", "version": remote["version"], "message": "manifest incomplete or invalid"}
            base = url.rsplit("/", 1)[0] + "/"
            stage = _dir / "staging"
            shutil.rmtree(stage, ignore_errors=True)
            for name, want in files.items():
                data = fetch(base + name)
                if hashlib.sha256(data).hexdigest() != want:
                    shutil.rmtree(stage, ignore_errors=True)
                    return {"status": "error", "version": remote["version"], "message": f"checksum mismatch: {name}"}
                if name.endswith(".yaml") and len(re.findall(rb"(?m)(?:^|[\s:\[,{-])\*[A-Za-z0-9_-]+", data)) > MAX_ALIASES:
                    shutil.rmtree(stage, ignore_errors=True)
                    return {"status": "error", "version": remote["version"], "message": f"too many YAML aliases: {name}"}
                (stage / name).parent.mkdir(parents=True, exist_ok=True)
                (stage / name).write_bytes(data)
            (stage / MANIFEST).write_text(json.dumps(remote, indent=2, sort_keys=True), encoding="utf-8")
            active, previous = _dir / "active", _dir / "previous"
            shutil.rmtree(previous, ignore_errors=True)
            if active.exists():
                active.rename(previous)
            stage.rename(active)
            reload()
            bad = _problems()
            if bad:                                               # roll back: the previous state stays in place
                shutil.rmtree(active, ignore_errors=True)
                if previous.exists():
                    previous.rename(active)
                reload()
                return {"status": "error", "version": remote["version"], "message": "validation failed: " + "; ".join(bad[:3])}
            shutil.rmtree(previous, ignore_errors=True)
            return {"status": "updated", "version": remote["version"], "message": ""}
        except Exception as exc:
            shutil.rmtree(_dir / "staging", ignore_errors=True)
            return {"status": "error", "version": None, "message": str(exc)[:200]}


def reset() -> None:
    """Back to the packaged knowledge (removes the downloaded update)."""
    with _lock:
        if _dir:
            shutil.rmtree(_dir / "active", ignore_errors=True)
        reload()


def now() -> float:
    return time.time()
