import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo


def connect(database_path):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialise(database_path):
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS missions (
                uuid TEXT PRIMARY KEY,
                client_name TEXT NOT NULL,
                title TEXT NOT NULL,
                reference TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed')),
                mission_date TEXT NOT NULL
            );

        """)
        ensure_entries_table(connection)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                uuid TEXT PRIMARY KEY,
                mission_uuid TEXT NOT NULL REFERENCES missions(uuid) ON DELETE CASCADE,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        report_columns = {row[1] for row in connection.execute('PRAGMA table_info(reports)')}
        if 'source_version_uuid' not in report_columns:
            connection.execute('ALTER TABLE reports ADD COLUMN source_version_uuid TEXT')
        if 'revision_reason' not in report_columns:
            connection.execute("ALTER TABLE reports ADD COLUMN revision_reason TEXT NOT NULL DEFAULT ''")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS report_versions (
                uuid TEXT PRIMARY KEY,
                mission_uuid TEXT NOT NULL REFERENCES missions(uuid),
                report_uuid TEXT NOT NULL UNIQUE REFERENCES reports(uuid),
                version INTEGER NOT NULL,
                content TEXT NOT NULL,
                validated_by TEXT NOT NULL,
                identity_source TEXT NOT NULL,
                validated_at TEXT NOT NULL,
                source_version_uuid TEXT REFERENCES report_versions(uuid),
                revision_reason TEXT NOT NULL,
                mission_json TEXT NOT NULL,
                sources_json TEXT NOT NULL,
                UNIQUE(mission_uuid, version)
            );
            CREATE TRIGGER IF NOT EXISTS report_versions_no_update
            BEFORE UPDATE ON report_versions BEGIN
                SELECT RAISE(ABORT, 'Validated versions are immutable');
            END;
            CREATE TRIGGER IF NOT EXISTS report_versions_no_delete
            BEFORE DELETE ON report_versions BEGIN
                SELECT RAISE(ABORT, 'Validated versions are immutable');
            END;
            CREATE TRIGGER IF NOT EXISTS validated_reports_no_update
            BEFORE UPDATE ON reports
            WHEN EXISTS (SELECT 1 FROM report_versions WHERE report_uuid = OLD.uuid)
            BEGIN SELECT RAISE(ABORT, 'Validated reports are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS validated_reports_no_delete
            BEFORE DELETE ON reports
            WHEN EXISTS (SELECT 1 FROM report_versions WHERE report_uuid = OLD.uuid)
            BEGIN SELECT RAISE(ABORT, 'Validated reports are immutable'); END;
        """)
        has_missions = connection.execute("SELECT 1 FROM missions LIMIT 1").fetchone()
        if not has_missions:
            seed(connection)
        import integration_service
        integration_service.initialise(connection)


def ensure_entries_table(connection):
    columns = connection.execute("PRAGMA table_info(entries)").fetchall()
    if not columns:
        create_entries_table(connection, "entries")
        return
    column_names = {column[1] for column in columns}
    table_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'entries'"
    ).fetchone()[0]
    if "file_path" not in column_names or "'audio'" not in table_sql:
        create_entries_table(connection, "entries_new")
        if "file_path" in column_names:
            connection.execute("""
                INSERT INTO entries_new (uuid, mission_uuid, entry_type, content, occurred_at, created_at, file_path, original_name, mime_type)
                SELECT uuid, mission_uuid, entry_type, content, occurred_at, created_at, file_path, original_name, mime_type FROM entries
            """)
        else:
            connection.execute("""
                INSERT INTO entries_new (uuid, mission_uuid, entry_type, content, occurred_at, created_at)
                SELECT uuid, mission_uuid, entry_type, content, occurred_at, created_at FROM entries
            """)
        connection.execute("DROP TABLE entries")
        connection.execute("ALTER TABLE entries_new RENAME TO entries")
        column_names = {column[1] for column in connection.execute("PRAGMA table_info(entries)").fetchall()}
    if "transcript" not in column_names:
        connection.execute("ALTER TABLE entries ADD COLUMN transcript TEXT")
    if "transcription_status" not in column_names:
        connection.execute("ALTER TABLE entries ADD COLUMN transcription_status TEXT NOT NULL DEFAULT 'not_requested'")
    if "transcription_error" not in column_names:
        connection.execute("ALTER TABLE entries ADD COLUMN transcription_error TEXT")


def create_entries_table(connection, table_name):
    connection.execute(f"""
        CREATE TABLE {table_name} (
            uuid TEXT PRIMARY KEY,
            mission_uuid TEXT NOT NULL REFERENCES missions(uuid) ON DELETE CASCADE,
            entry_type TEXT NOT NULL CHECK (entry_type IN ('text', 'photo', 'audio')),
            content TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            file_path TEXT,
            original_name TEXT,
            mime_type TEXT,
            transcript TEXT,
            transcription_status TEXT NOT NULL DEFAULT 'not_requested',
            transcription_error TEXT
        )
    """)


def seed(connection):
    first_mission = "815bd8aa-1b3a-4a00-8d32-000000000145"
    second_mission = "815bd8aa-1b3a-4a00-8d32-000000000158"
    connection.executemany(
        "INSERT INTO missions VALUES (?, ?, ?, ?, ?, ?)",
        [
            (first_mission, "TOTALENERGIES", "Coordination tirs radio", "ONYX-2026-0145", "in_progress", "2026-09-25"),
            (second_mission, "AQUERIS", "Audit terrain", "ONYX-2026-0158", "in_progress", "2026-09-25"),
        ],
    )
    now = "2026-09-25T10:14:00+02:00"
    connection.executemany(
        """INSERT INTO entries
           (uuid, mission_uuid, entry_type, content, occurred_at, created_at)
           VALUES (?, ?, 'text', ?, ?, ?)""",
        [
            (str(uuid4()), first_mission, "Arrivée sur site.", "2026-09-25T08:12:00+02:00", now),
            (str(uuid4()), first_mission, "Permis non disponible.", "2026-09-25T09:05:00+02:00", now),
        ],
    )


def list_missions(database_path):
    with connect(database_path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM missions ORDER BY client_name")]


def get_mission(database_path, mission_uuid):
    with connect(database_path) as connection:
        row = connection.execute("SELECT * FROM missions WHERE uuid = ?", (mission_uuid,)).fetchone()
        return dict(row) if row else None


class MissionConflict(ValueError):
    pass


def create_mission(database_path, payload):
    if not isinstance(payload, dict):
        raise ValueError('Formulaire de mission invalide.')
    fields = {}
    for key, label, limit in [('client_name', 'Le client', 160), ('title', 'L’intitulé', 240), ('reference', 'La référence', 100)]:
        value = payload.get(key, '')
        if not isinstance(value, str):
            raise ValueError(f'{label} doit être du texte.')
        value = value.strip()
        if (not value and key != 'reference') or len(value) > limit or any(ord(char) < 32 for char in value):
            raise ValueError(f'{label} est obligatoire (sauf référence) et limité à {limit} caractères, sans retour à la ligne.')
        fields[key] = value
    raw_date = payload.get('mission_date')
    try:
        if not isinstance(raw_date, str) or date.fromisoformat(raw_date).isoformat() != raw_date:
            raise ValueError()
    except ValueError:
        raise ValueError('La date doit être une date valide au format AAAA-MM-JJ.') from None
    mission_uuid = str(uuid4())
    fields.update(uuid=mission_uuid, mission_date=raw_date, status='in_progress')
    fields['reference'] = fields['reference'] or f'REPORT-{raw_date[:4]}-{mission_uuid.upper()}'
    try:
        with connect(database_path) as connection:
            connection.execute('INSERT INTO missions (uuid, client_name, title, reference, status, mission_date) VALUES (:uuid, :client_name, :title, :reference, :status, :mission_date)', fields)
    except sqlite3.IntegrityError:
        raise MissionConflict('Cette référence existe déjà. Choisissez une autre référence.') from None
    return fields


def list_entries(database_path, mission_uuid):
    with connect(database_path) as connection:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM entries WHERE mission_uuid = ? ORDER BY occurred_at", (mission_uuid,)
        )]


def get_entry(database_path, entry_uuid):
    with connect(database_path) as connection:
        row = connection.execute("SELECT * FROM entries WHERE uuid = ?", (entry_uuid,)).fetchone()
        return dict(row) if row else None


def update_transcription(database_path, entry_uuid, status, transcript=None, error=None):
    with connect(database_path) as connection:
        connection.execute(
            "UPDATE entries SET transcription_status = ?, transcript = ?, transcription_error = ? WHERE uuid = ?",
            (status, transcript, error, entry_uuid),
        )


def get_latest_report(database_path, mission_uuid):
    with connect(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM reports WHERE mission_uuid = ? ORDER BY updated_at DESC LIMIT 1", (mission_uuid,)
        ).fetchone()
        return report_state(connection, row) if row else None


def get_report(database_path, mission_uuid, report_uuid):
    with connect(database_path) as connection:
        row = connection.execute('SELECT * FROM reports WHERE mission_uuid = ? AND uuid = ?', (mission_uuid, report_uuid)).fetchone()
        return report_state(connection, row) if row else None


class ReportConflict(ValueError):
    pass


def report_state(connection, row):
    report = dict(row)
    version = connection.execute(
        'SELECT uuid, version, validated_by, validated_at, identity_source FROM report_versions WHERE report_uuid = ?',
        (report['uuid'],),
    ).fetchone()
    report['status'] = 'validated' if version else 'draft'
    report['validation'] = dict(version) if version else None
    return report


def save_report(database_path, mission_uuid, content, report_uuid=None, expected_updated_at=None):
    timestamp = datetime.now(ZoneInfo("Europe/Paris")).isoformat()
    with connect(database_path) as connection:
        connection.execute('BEGIN IMMEDIATE')
        if report_uuid:
            row = connection.execute('SELECT * FROM reports WHERE uuid = ? AND mission_uuid = ?', (report_uuid, mission_uuid)).fetchone()
            if not row:
                raise ReportConflict('Rapport introuvable dans cette mission.')
            if report_state(connection, row)['status'] == 'validated':
                raise ReportConflict('Rapport validé : ouvrez une copie pour le modifier.')
            if expected_updated_at is not None and row['updated_at'] != expected_updated_at:
                raise ReportConflict('Le brouillon a changé. Rechargez-le avant de poursuivre.')
            connection.execute(
                "UPDATE reports SET content = ?, updated_at = ? WHERE uuid = ? AND mission_uuid = ?",
                (content, timestamp, report_uuid, mission_uuid),
            )
            row = connection.execute("SELECT * FROM reports WHERE uuid = ? AND mission_uuid = ?", (report_uuid, mission_uuid)).fetchone()
            return report_state(connection, row)
        report_uuid = str(uuid4())
        connection.execute(
            "INSERT INTO reports (uuid, mission_uuid, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (report_uuid, mission_uuid, content, timestamp, timestamp),
        )
        return report_state(connection, connection.execute("SELECT * FROM reports WHERE uuid = ?", (report_uuid,)).fetchone())


def list_report_versions(database_path, mission_uuid):
    with connect(database_path) as connection:
        return [dict(row) for row in connection.execute(
            '''SELECT uuid, report_uuid, version, validated_by, identity_source,
                      validated_at, revision_reason, source_version_uuid
               FROM report_versions WHERE mission_uuid = ? ORDER BY version DESC''', (mission_uuid,)
        )]


def get_report_version(database_path, mission_uuid, version_uuid):
    with connect(database_path) as connection:
        row = connection.execute('SELECT * FROM report_versions WHERE uuid = ? AND mission_uuid = ?', (version_uuid, mission_uuid)).fetchone()
        return dict(row) if row else None


def validate_report(database_path, mission_uuid, report_uuid, content, expected_updated_at, actor, identity_source):
    timestamp = datetime.now(ZoneInfo('Europe/Paris')).isoformat()
    with connect(database_path) as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT * FROM reports WHERE uuid = ? AND mission_uuid = ?', (report_uuid, mission_uuid)).fetchone()
        if not row or report_state(connection, row)['status'] == 'validated':
            raise ReportConflict('Brouillon absent ou déjà validé.')
        if row['updated_at'] != expected_updated_at or row['content'] != content:
            raise ReportConflict('Le texte a changé. Enregistrez et relisez le brouillon avant de valider.')
        version_number = connection.execute('SELECT COALESCE(MAX(version), 0) + 1 FROM report_versions WHERE mission_uuid = ?', (mission_uuid,)).fetchone()[0]
        # Record a source snapshot, not a claim that media files are immutable.
        sources = [dict(entry) for entry in connection.execute('SELECT * FROM entries WHERE mission_uuid = ? ORDER BY occurred_at', (mission_uuid,))]
        connection.execute('''INSERT INTO report_versions
            (uuid, mission_uuid, report_uuid, version, content, validated_by,
             identity_source, validated_at, source_version_uuid, revision_reason, mission_json, sources_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (str(uuid4()), mission_uuid, report_uuid, version_number, content, actor,
             identity_source, timestamp, row['source_version_uuid'], row['revision_reason'],
             json.dumps(dict(connection.execute('SELECT * FROM missions WHERE uuid = ?', (mission_uuid,)).fetchone()), ensure_ascii=False),
             json.dumps(sources, ensure_ascii=False)))
        return report_state(connection, row)


def reopen_report_version(database_path, mission_uuid, version_uuid, reason):
    timestamp = datetime.now(ZoneInfo('Europe/Paris')).isoformat()
    with connect(database_path) as connection:
        connection.execute('BEGIN IMMEDIATE')
        version = connection.execute('SELECT * FROM report_versions WHERE uuid = ? AND mission_uuid = ?', (version_uuid, mission_uuid)).fetchone()
        if not version:
            raise ReportConflict('Version introuvable dans cette mission.')
        report_uuid = str(uuid4())
        connection.execute('''INSERT INTO reports
            (uuid, mission_uuid, content, created_at, updated_at, source_version_uuid, revision_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (report_uuid, mission_uuid, version['content'], timestamp, timestamp, version_uuid, reason))
        return report_state(connection, connection.execute('SELECT * FROM reports WHERE uuid = ?', (report_uuid,)).fetchone())


def add_text_entry(database_path, mission_uuid, content):
    timestamp = datetime.now(ZoneInfo("Europe/Paris")).isoformat()
    entry = {
        "uuid": str(uuid4()),
        "mission_uuid": mission_uuid,
        "entry_type": "text",
        "content": content,
        "occurred_at": timestamp,
        "created_at": timestamp,
    }
    with connect(database_path) as connection:
        connection.execute(
            """INSERT INTO entries
               (uuid, mission_uuid, entry_type, content, occurred_at, created_at)
               VALUES (:uuid, :mission_uuid, :entry_type, :content, :occurred_at, :created_at)""", entry
        )
    return entry


def add_photo_entry(database_path, mission_uuid, original_name, file_path, mime_type):
    return add_file_entry(database_path, mission_uuid, "photo", original_name, file_path, mime_type)


def add_audio_entry(database_path, mission_uuid, original_name, file_path, mime_type):
    return add_file_entry(database_path, mission_uuid, "audio", original_name, file_path, mime_type)


def add_file_entry(database_path, mission_uuid, entry_type, original_name, file_path, mime_type):
    timestamp = datetime.now(ZoneInfo("Europe/Paris")).isoformat()
    entry = {
        "uuid": str(uuid4()),
        "mission_uuid": mission_uuid,
        "entry_type": entry_type,
        "content": original_name,
        "occurred_at": timestamp,
        "created_at": timestamp,
        "file_path": file_path,
        "original_name": original_name,
        "mime_type": mime_type,
    }
    with connect(database_path) as connection:
        connection.execute("""
            INSERT INTO entries
            (uuid, mission_uuid, entry_type, content, occurred_at, created_at,
             file_path, original_name, mime_type)
            VALUES (:uuid, :mission_uuid, :entry_type, :content, :occurred_at, :created_at,
                    :file_path, :original_name, :mime_type)
        """, entry)
    return entry
