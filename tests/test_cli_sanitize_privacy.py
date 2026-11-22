import io
import re
from pathlib import Path

from conftest import hb1, raw1

from device_bus_analyzer import cli
from device_bus_analyzer.protocols.bshdbus import build_frame
from device_bus_analyzer.sanitize import sanitize_file, sanitize_line

ROOT = Path(__file__).resolve().parent.parent


def test_sanitize_removes_private_details_but_keeps_bus_data():
    f = build_frame(0x25, 0x2008, bytes(8)).hex()
    cases = ["SSID: 'MyHomeNet'", "BSSID: 02:00:5E:00:53:AF", "connect to 192.0.2.23 port 6053", "mac 02:00:5e:00:53:af",
             "Hostname: 'geschirrspuler'", "geschirrspuler.local", "api key: abcdEFGH12345678=="]
    for c in cases:
        out = sanitize_line(c)
        assert out != c and not re.search(r"MyHomeNet|192\.168|02:00:5e|192\.0\.2\.23|geschirrspuler|abcdEFGH", out, re.I), out
    keep = f"RAW1 seq=1 t_us=5 dt_us=5 n=14 hex={f}"
    assert sanitize_line(keep) == keep
    assert sanitize_line("password: !secret wifi_password") == "password: !secret wifi_password"


def test_sanitize_file_preserves_line_endings(tmp_path):
    p = tmp_path / "a.log"
    p.write_bytes(b"x 10.0.0.1\r\ny\r\n")
    buf = io.StringIO(newline="")
    sanitize_file(str(p), buf)
    assert buf.getvalue() == "x <IP>\r\ny\r\n"


def test_cli_import_rebuild_and_validate(tmp_path, capsys):
    f = build_frame(0x17, 0x1010, b"\x1c")
    log = tmp_path / "neff_2026-11-18_x.txt"
    log.write_text(raw1(1, 10, f) + "\n" + raw1(2, 20, f) + "\n" + hb1(2, 30) + "\n")
    db = str(tmp_path / "d.sqlite")
    assert cli.main(["--db", db, "import", "--source", "dw", "--protocol", "bshdbus", str(log)]) == 0
    assert "'RAW1': 2" in capsys.readouterr().out
    assert cli.main(["--db", db, "rebuild"]) == 0
    assert "bursts re-decoded: 2" in capsys.readouterr().out
    assert cli.main(["validate-spec", "bshdbus"]) == 0
    assert cli.main(["gaps", str(log)]) == 0
    gap = tmp_path / "gap.txt"
    gap.write_text(raw1(1, 10, f) + "\n" + raw1(5, 20, f) + "\n")
    assert cli.main(["gaps", str(gap)]) == 1


def test_hash_password_cli(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("secret-pw\n"))
    cli.main(["hash-password"])
    h = capsys.readouterr().out.strip()
    from argon2 import PasswordHasher
    assert h.startswith("$argon2id$") and PasswordHasher().verify(h, "secret-pw")


# --- repository hygiene: the repo is public ----------------------------------------------------
TEXT = {".py", ".md", ".yaml", ".yml", ".json", ".toml", ".html", ".css", ".txt", ".cfg", ".h", ".cpp", ""}
IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
OK_IP = re.compile(r"^(0\.0\.0\.0|127\.0\.0\.1|192\.0\.2\.\d+|198\.51\.100\.\d+|203\.0\.113\.\d+|10\.0\.0\.\d+)$")
MAC = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")
MAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
OK_MAIL = re.compile(r"@(example\.(org|com)|b\.de|board\.lan|(?:10\.0\.0|192\.0\.2)\.\d+|noreply\.github\.com)$", re.I)
PRIVATE_WORDS = re.compile(r"rl29|mannheim|steffen|quidong\.de|192\.168\.", re.I)


def repo_files():
    for p in ROOT.rglob("*"):
        if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts \
                and p.suffix in TEXT and p.name != Path(__file__).name:
            yield p


def test_no_private_data_in_repository():
    problems = []
    for p in repo_files():
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in IP.finditer(text):
            if not OK_IP.match(m.group()) and not _looks_like_version(text, m):
                problems.append(f"{p.relative_to(ROOT)}: IP {m.group()}")
        problems += [f"{p.relative_to(ROOT)}: MAC {m.group()}" for m in MAC.finditer(text)]
        problems += [f"{p.relative_to(ROOT)}: e-mail {m.group()}" for m in MAIL.finditer(text) if not OK_MAIL.search(m.group())]
        problems += [f"{p.relative_to(ROOT)}: private word {m.group()}" for m in PRIVATE_WORDS.finditer(text)]
    assert not problems, "\n".join(problems[:20])


def _looks_like_version(text, m):
    return bool(re.search(r"(version|v|==|>=|<=)\s*$", text[max(0, m.start() - 12):m.start()], re.I))


def test_no_log_or_database_files_in_repository():
    bad = [p.name for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts
           and (p.suffix in {".sqlite", ".db", ".log"} or "dauerlog" in p.name or p.name == "secrets.yaml")]
    assert not bad, bad
