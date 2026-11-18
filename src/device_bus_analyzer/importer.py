"""Import saved ESPHome log files into the store (offline counterpart of the collector)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import logformat
from .store import Store


def guess_date(path: Path) -> str | None:
    m = re.search(r"(\d{4})[-_](\d{2})[-_](\d{2})", path.name)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def import_file(store: Store, path: str | Path, source: str, protocol: str, date: str | None = None,
                tz: str = "Europe/Berlin") -> dict:
    """Import one log. Host timestamps (HH:MM:SS.mmm) get ``date`` + timezone; a falling time means a new day."""
    path = Path(path)
    date = date or guess_date(path)
    if date is None:
        raise ValueError(f"{path.name}: no date in the file name, pass date=YYYY-MM-DD")
    zone = ZoneInfo(tz)
    day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=zone)
    sid = store.source(source, protocol)
    counts: dict[str, int] = {}
    last_host = None
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        for line in fh:
            h = logformat.host_seconds(line)
            if h is not None:
                if last_host is not None and h < last_host - 60:
                    day += timedelta(days=1)
                last_host = h
                recv = (day + timedelta(seconds=h)).timestamp()
            else:
                recv = None if last_host is None else (day + timedelta(seconds=last_host)).timestamp()
            typ = store.ingest_line(sid, line, recv if recv is not None else day.timestamp())
            if typ:
                counts[typ] = counts.get(typ, 0) + 1
    return counts
