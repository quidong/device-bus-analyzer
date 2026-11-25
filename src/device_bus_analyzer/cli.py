"""Command line: dba import | rebuild | validate-spec | collect | serve | gaps"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from . import config, logformat
from .importer import import_file
from .spec import validate_spec
from .store import Store


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dba")
    ap.add_argument("--db", default=None, help="SQLite file (default: $DBA_DB or /data/bus.sqlite)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("import", help="import log files")
    p.add_argument("--source", required=True)
    p.add_argument("--protocol", required=True)
    p.add_argument("--date")
    p.add_argument("--tz", default="Europe/Berlin")
    p.add_argument("files", nargs="+")
    sub.add_parser("rebuild", help="re-derive frames from the raw bursts")
    pl = sub.add_parser("purge-legacy", help="delete frames without raw data (old decoded-only recordings); irreversible, make a backup first")
    pl.add_argument("--source", required=True)
    pl.add_argument("--yes", action="store_true", help="really delete")
    p = sub.add_parser("validate-spec")
    p.add_argument("protocol")
    bk = sub.add_parser("build-knowledge", help="write knowledge-manifest.json (version and hashes of specs, catalogue, firmware)")
    bk.add_argument("--sign", metavar="PRIVATE_KEY", help="also sign the manifest (writes knowledge-manifest.json.sig)")
    kg = sub.add_parser("knowledge-keygen", help="create the Ed25519 signing key for knowledge updates (public key goes into the package)")
    kg.add_argument("private_key", help="where to store the PRIVATE key (keep it out of the repository)")
    sub.add_parser("update-knowledge", help="fetch newer device knowledge from the repository now")
    p = sub.add_parser("sanitize", help="print a log with SSID/MAC/IP/hostnames/keys removed")
    p.add_argument("file")
    p = sub.add_parser("gaps", help="check a log file for lost bursts")
    p.add_argument("file")
    p = sub.add_parser("validate-contribution", help="check exported findings (JSON) for shape and private data")
    p.add_argument("files", nargs="+")
    p = sub.add_parser("suggest-spec", help="print spec entries (YAML) for an exported findings file")
    p.add_argument("file")
    sub.add_parser("hash-password", help="print an argon2id hash for ADMIN_PASSWORD_HASH (reads the password from stdin)")
    sub.add_parser("collect", help="run the passive collector for DBA_DEVICES")
    p = sub.add_parser("serve", help="run API + frontend")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--no-collector", action="store_true")
    p.add_argument("--no-tls", action="store_true", help="plain HTTP (same as DBA_TLS=0)")
    sub.add_parser("healthcheck", help="exit 0 if the local server answers (used by the container health check)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = config.load()
    db = a.db or s.db_path

    if a.cmd == "validate-spec":
        problems = validate_spec(a.protocol)
        print("\n".join(problems) or "spec OK")
        return 1 if problems else 0
    if a.cmd == "healthcheck":
        import ssl
        import urllib.request
        port = int(__import__("os").environ.get("DBA_PORT_INTERNAL", "8080"))
        for url, ctx in ((f"https://127.0.0.1:{port}/healthz", ssl._create_unverified_context()), (f"http://127.0.0.1:{port}/healthz", None)):  # noqa: S323
            try:
                urllib.request.urlopen(url, timeout=3, context=ctx)  # noqa: S310
                return 0
            except Exception:
                continue
        return 1
    if a.cmd == "build-knowledge":
        from . import knowledge
        print(knowledge.write_manifest()["version"])
        if a.sign:
            knowledge.sign_manifest(a.sign)
            print("signed")
        return 0
    if a.cmd == "knowledge-keygen":
        from . import knowledge
        print("public key:", knowledge.generate_keypair(a.private_key))
        print("commit src/device_bus_analyzer/knowledge-pubkey.txt, then: dba build-knowledge --sign", a.private_key)
        return 0
    if a.cmd == "update-knowledge":
        from pathlib import Path

        from . import knowledge
        knowledge.configure(Path(db).parent / "knowledge")
        res = knowledge.update(s.knowledge_url or knowledge.DEFAULT_URL)
        print(res["status"], res.get("version") or "", res.get("message") or "")
        return 1 if res["status"] == "error" else 0
    if a.cmd == "sanitize":
        from .sanitize import sanitize_file
        sanitize_file(a.file)
        return 0
    if a.cmd == "gaps":
        entries = [logformat.parse_line(z) for z in open(a.file, encoding="utf-8", errors="replace")]
        g = logformat.find_gaps(entries)
        print("\n".join(g) or "no gaps")
        return 1 if g else 0
    if a.cmd in ("validate-contribution", "suggest-spec"):
        import json

        from .contribution import to_spec_snippet, validate
        bad = 0
        for f in (a.files if a.cmd == "validate-contribution" else [a.file]):
            doc = json.load(open(f, encoding="utf-8"))
            problems = validate(doc)
            if problems:
                bad += 1
                print(f"{f}:\n  " + "\n  ".join(problems))
            elif a.cmd == "suggest-spec":
                print(to_spec_snippet(doc))
            else:
                print(f"{f}: OK")
        return 1 if bad else 0
    if a.cmd == "hash-password":
        from argon2 import PasswordHasher
        print(PasswordHasher().hash(sys.stdin.readline().rstrip("\n")))
        return 0
    store = Store(db)
    if a.cmd == "import":
        for f in a.files:
            print(f, import_file(store, f, a.source, a.protocol, a.date, a.tz))
    elif a.cmd == "purge-legacy":
        if not a.yes:
            print("dry run, nothing deleted; legacy frames:", store.quality(a.source)["legacy"]["frames"], "(add --yes to delete)")
            return 1
        print("frames deleted:", store.purge_legacy(a.source))
    elif a.cmd == "rebuild":
        print("bursts re-decoded:", store.rebuild_frames())
    elif a.cmd == "collect":
        from .collector import run_all
        asyncio.run(run_all(store, s.devices))   # env devices are imported into the DB first
    elif a.cmd == "serve":
        import uvicorn

        from .web import create_app
        s = config.apply_saved(s, store.kv_get("config"))     # settings saved in the UI (HTTPS, time zone, ...)
        s = config.ensure_secrets(s)                       # first start: session secret and API token are created and kept in the data volume
        kw = {}
        if s.tls and not a.no_tls:
            from pathlib import Path

            from . import tls
            files = tls.ensure(Path(db).parent, s.tls_hosts, s.tls_cert, s.tls_key)
            kw = {"ssl_certfile": files.cert, "ssl_keyfile": files.key}
            print(f"HTTPS on port {a.port}; certificate valid until {files.expires:%Y-%m-%d} for: {', '.join(files.hosts)}", flush=True)
        uvicorn.run(create_app(s, store, start_collectors=not a.no_collector), host=a.host, port=a.port, **kw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
