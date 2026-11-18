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
    p = sub.add_parser("validate-spec")
    p.add_argument("protocol")
    p = sub.add_parser("sanitize", help="print a log with SSID/MAC/IP/hostnames/keys removed")
    p.add_argument("file")
    p = sub.add_parser("gaps", help="check a log file for lost bursts")
    p.add_argument("file")
    sub.add_parser("hash-password", help="print an argon2id hash for ADMIN_PASSWORD_HASH (reads the password from stdin)")
    sub.add_parser("collect", help="run the read-only collector for DBA_DEVICES")
    p = sub.add_parser("serve", help="run API + frontend")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--no-collector", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = config.load()
    db = a.db or s.db_path

    if a.cmd == "validate-spec":
        problems = validate_spec(a.protocol)
        print("\n".join(problems) or "spec OK")
        return 1 if problems else 0
    if a.cmd == "sanitize":
        from .sanitize import sanitize_file
        sanitize_file(a.file)
        return 0
    if a.cmd == "gaps":
        entries = [logformat.parse_line(z) for z in open(a.file, encoding="utf-8", errors="replace")]
        g = logformat.find_gaps(entries)
        print("\n".join(g) or "no gaps")
        return 1 if g else 0
    if a.cmd == "hash-password":
        from argon2 import PasswordHasher
        print(PasswordHasher().hash(sys.stdin.readline().rstrip("\n")))
        return 0
    store = Store(db)
    if a.cmd == "import":
        for f in a.files:
            print(f, import_file(store, f, a.source, a.protocol, a.date, a.tz))
    elif a.cmd == "rebuild":
        print("bursts re-decoded:", store.rebuild_frames())
    elif a.cmd == "collect":
        from .collector import run_all
        asyncio.run(run_all(store, s.devices))
    elif a.cmd == "serve":
        import uvicorn
        from .web import create_app
        uvicorn.run(create_app(s, store, start_collectors=not a.no_collector), host=a.host, port=a.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
