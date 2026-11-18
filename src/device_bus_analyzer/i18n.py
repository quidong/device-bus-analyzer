"""Tiny DE/EN string table for the frontend."""
STR = {
    "en": {
        "title": "Device Bus Analyzer", "login": "Sign in", "email": "E-mail", "password": "Password", "logout": "Sign out",
        "bad_login": "Wrong e-mail or password.", "locked": "Too many attempts, try again in a few minutes.",
        "sources": "Sources", "frames": "Frames", "timeline": "Timeline", "commands": "Commands", "bursts": "Raw bursts",
        "findings": "Findings", "quality": "Quality", "name": "Name", "protocol": "Protocol", "first": "First", "last": "Last",
        "time": "Time", "dest": "Dest", "cmd": "Cmd", "data": "Data", "ack": "ACK", "crc": "CRC", "decoded": "Decoded",
        "status": "Status", "filter": "Filter", "since": "From", "until": "To", "limit": "Limit", "only_bad": "CRC errors only",
        "count": "Count", "distinct": "Distinct values", "evidence": "Evidence", "no_data": "No data yet.",
        "gaps": "Gaps / losses", "sessions": "Boots", "ok": "valid", "bad": "CRC error", "values": "Values",
        "confirmed": "confirmed", "assumed": "assumed", "unknown": "unknown", "read_only": "read-only", "next": "Next", "prev": "Previous",
        "burst_hex": "Raw hex", "runs": "Runs", "run": "Run", "start": "Start", "end": "End", "duration": "Duration", "program": "Program", "remaining": "Remaining", "running": "running",
        "runs_note": "A run is derived: it starts at the start command and ends at the last telegram before a silent gap. Both are marked as assumed.", "sender": "Sender", "receiver": "Receiver", "nodes": "Nodes",
        "sender_note": "The frame carries only the destination; the sender is derived from it and is never better than assumed.", "timezone_note": "Times in", "all": "all",
    },
    "de": {
        "title": "Geräte-Bus-Analyse", "login": "Anmelden", "email": "E-Mail", "password": "Passwort", "logout": "Abmelden",
        "bad_login": "E-Mail oder Passwort falsch.", "locked": "Zu viele Versuche, bitte in einigen Minuten erneut versuchen.",
        "sources": "Quellen", "frames": "Telegramme", "timeline": "Zeitverlauf", "commands": "Kommandos", "bursts": "Rohdaten-Bursts",
        "findings": "Erkenntnisse", "quality": "Qualität", "name": "Name", "protocol": "Protokoll", "first": "Erstes", "last": "Letztes",
        "time": "Zeit", "dest": "Ziel", "cmd": "Kommando", "data": "Daten", "ack": "ACK", "crc": "CRC", "decoded": "Dekodiert",
        "status": "Status", "filter": "Filtern", "since": "Von", "until": "Bis", "limit": "Anzahl", "only_bad": "Nur CRC-Fehler",
        "count": "Anzahl", "distinct": "Verschiedene Werte", "evidence": "Beleg", "no_data": "Noch keine Daten.",
        "gaps": "Lücken / Verluste", "sessions": "Neustarts", "ok": "gültig", "bad": "CRC-Fehler", "values": "Werte",
        "confirmed": "bestätigt", "assumed": "angenommen", "unknown": "unbekannt", "read_only": "nur lesend", "next": "Weiter", "prev": "Zurück",
        "burst_hex": "Rohdaten (hex)", "runs": "Läufe", "run": "Lauf", "start": "Start", "end": "Ende", "duration": "Dauer", "program": "Programm", "remaining": "Restzeit", "running": "läuft",
        "runs_note": "Ein Lauf ist abgeleitet: Er beginnt beim Startbefehl und endet beim letzten Telegramm vor einer längeren Pause. Beides ist als angenommen markiert.", "sender": "Absender", "receiver": "Empfänger", "nodes": "Knoten",
        "sender_note": "Das Telegramm enthält nur die Zieladresse; der Absender wird daraus abgeleitet und ist höchstens angenommen.", "timezone_note": "Zeiten in", "all": "alle",
    },
}


def pick(accept_language: str | None, cookie: str | None, query: str | None) -> str:
    for cand in (query, cookie):
        if cand in STR:
            return cand
    return "de" if (accept_language or "").lower().startswith("de") else "en"
