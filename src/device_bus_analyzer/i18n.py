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
        "sender_note": "The frame carries only the destination; the sender is derived from it and is never better than assumed.", "devices": "Devices", "address": "Address", "device": "Device",
        "devices_note": "Source and destination addresses are read from the frame and are always true; what a device is comes from its traffic and carries a status.", "timezone_note": "Times in", "all": "all",
        "devices_title": "Devices", "new_device": "New device", "edit": "Edit", "save": "Save", "cancel": "Cancel", "device_type": "Type",
        "manufacturer": "Manufacturer", "model": "Model", "host": "Host / IP", "port": "Port", "api_key": "API encryption key",
        "key_set": "set", "key_missing": "not set", "key_keep": "Leave empty to keep the stored key.", "key_clear": "Remove stored key",
        "enabled": "Collect", "disabled": "paused", "enabled_on": "collecting", "unclassified": "not classified",
        "import_only": "import only", "connection": "Connection", "dev_note": "Devices are stored in the database volume. Nothing is ever deleted here: pausing a device keeps all its data. Name and protocol cannot be changed afterwards.",
        "pick_hint": "Pick from the suggestions or type your own value.", "protocol_fixed": "Protocol is fixed once the device exists.",
        "bad_name": "Name: letters, digits, - and _ only (max. 40).", "bad_protocol": "Unknown protocol.", "bad_host": "Host is missing or invalid.",
        "bad_port": "Port must be 1-65535.", "bad_key": "The key must be the base64 key of the ESPHome API (32 bytes).",
        "exists": "A device with this name already exists.", "bad_input": "Invalid input, or the name is already used with another protocol.",
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
        "sender_note": "Das Telegramm enthält nur die Zieladresse; der Absender wird daraus abgeleitet und ist höchstens angenommen.", "devices": "Geräte", "address": "Adresse", "device": "Gerät",
        "devices_note": "Quell- und Zieladresse stehen im Telegramm und sind immer sicher; was ein Gerät ist, ergibt sich aus seinem Verkehr und hat einen Status.", "timezone_note": "Zeiten in", "all": "alle",
        "devices_title": "Geräte", "new_device": "Neues Gerät", "edit": "Bearbeiten", "save": "Speichern", "cancel": "Abbrechen", "device_type": "Typ",
        "manufacturer": "Hersteller", "model": "Modell", "host": "Host / IP", "port": "Port", "api_key": "API-Verschlüsselungsschlüssel",
        "key_set": "gesetzt", "key_missing": "nicht gesetzt", "key_keep": "Leer lassen, um den gespeicherten Schlüssel zu behalten.", "key_clear": "Gespeicherten Schlüssel entfernen",
        "enabled": "Aufzeichnen", "disabled": "pausiert", "enabled_on": "zeichnet auf", "unclassified": "nicht eingeordnet",
        "import_only": "nur Import", "connection": "Verbindung", "dev_note": "Geräte liegen in der Datenbank im Volume. Hier wird nie etwas gelöscht: Pausieren behält alle Daten. Name und Protokoll lassen sich nachträglich nicht ändern.",
        "pick_hint": "Aus den Vorschlägen wählen oder einen eigenen Wert eintippen.", "protocol_fixed": "Das Protokoll ist nach dem Anlegen fest.",
        "bad_name": "Name: nur Buchstaben, Ziffern, - und _ (max. 40).", "bad_protocol": "Unbekanntes Protokoll.", "bad_host": "Host fehlt oder ist ungültig.",
        "bad_port": "Port muss 1-65535 sein.", "bad_key": "Der Schlüssel muss der Base64-Schlüssel der ESPHome-API sein (32 Byte).",
        "exists": "Ein Gerät mit diesem Namen gibt es schon.", "bad_input": "Ungültige Eingabe, oder der Name wird schon mit einem anderen Protokoll verwendet.",
    },
}


def pick(accept_language: str | None, cookie: str | None, query: str | None) -> str:
    for cand in (query, cookie):
        if cand in STR:
            return cand
    return "de" if (accept_language or "").lower().startswith("de") else "en"
