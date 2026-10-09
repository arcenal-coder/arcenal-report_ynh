import sqlite3
from datetime import datetime
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
        has_missions = connection.execute("SELECT 1 FROM missions LIMIT 1").fetchone()
        if not has_missions:
            seed(connection)


def ensure_entries_table(connection):
    columns = connection.execute("PRAGMA table_info(entries)").fetchall()
    if not columns:
        create_entries_table(connection, "entries")
        return
    column_names = {column[1] for column in columns}
    table_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'entries'"
    ).fetchone()[0]
    if "file_path" in column_names and "photo_category" not in column_names and "'audio'" in table_sql:
        return
    create_entries_table(connection, "entries_new")
    if "file_path" in column_names:
        connection.execute("""
            INSERT INTO entries_new
            (uuid, mission_uuid, entry_type, content, occurred_at, created_at,
             file_path, original_name, mime_type)
            SELECT uuid, mission_uuid, entry_type, content, occurred_at, created_at,
                   file_path, original_name, mime_type
            FROM entries
        """)
    else:
        connection.execute("""
            INSERT INTO entries_new (uuid, mission_uuid, entry_type, content, occurred_at, created_at)
            SELECT uuid, mission_uuid, entry_type, content, occurred_at, created_at FROM entries
        """)
    connection.execute("DROP TABLE entries")
    connection.execute("ALTER TABLE entries_new RENAME TO entries")


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
            mime_type TEXT
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


def list_entries(database_path, mission_uuid):
    with connect(database_path) as connection:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM entries WHERE mission_uuid = ? ORDER BY occurred_at", (mission_uuid,)
        )]


def get_entry(database_path, entry_uuid):
    with connect(database_path) as connection:
        row = connection.execute("SELECT * FROM entries WHERE uuid = ?", (entry_uuid,)).fetchone()
        return dict(row) if row else None


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
