"""Shared, read-only machine API used by both REST and MCP."""

import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

import database


SCOPES = ('missions:read', 'entries:read', 'reports:read')


class AccessError(Exception):
    def __init__(self, message, status='403 Forbidden'):
        super().__init__(message)
        self.status = status


def initialise(connection):
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS integration_credentials (
            uuid TEXT PRIMARY KEY, label TEXT NOT NULL, digest TEXT NOT NULL,
            missions_json TEXT NOT NULL, scopes_json TEXT NOT NULL,
            created_at REAL NOT NULL, expires_at REAL NOT NULL,
            revoked_at REAL, created_by TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS integration_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at REAL NOT NULL,
            credential_uuid TEXT, operation TEXT NOT NULL, outcome TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS integration_rate (
            credential_uuid TEXT PRIMARY KEY, window INTEGER NOT NULL, count INTEGER NOT NULL
        );
    ''')


def audit(connection, credential_uuid, operation, outcome):
    connection.execute('INSERT INTO integration_audit (occurred_at, credential_uuid, operation, outcome) VALUES (?, ?, ?, ?)',
                       (time.time(), credential_uuid, operation, outcome))
    # Bounded metadata retention. No prompts, notes, secret values or tool args.
    connection.execute('DELETE FROM integration_audit WHERE occurred_at < ?', (time.time() - 90 * 86400,))


def credential_metadata(row):
    value = {key: row[key] for key in ('uuid', 'label', 'created_at', 'expires_at', 'revoked_at')}
    value['missions'] = json.loads(row['missions_json'])
    value['scopes'] = json.loads(row['scopes_json'])
    return value


def list_credentials(db_path):
    with database.connect(db_path) as connection:
        return [credential_metadata(row) for row in connection.execute('SELECT * FROM integration_credentials ORDER BY created_at DESC')]


def create_credential(db_path, payload, actor):
    if not isinstance(payload, dict) or set(payload) - {'label', 'missions', 'scopes', 'expires_days', 'confirmed'}:
        raise AccessError('Paramètres de création invalides.', '400 Bad Request')
    if payload.get('confirmed') is not True:
        raise AccessError('Confirmez explicitement la création de cet accès.', '400 Bad Request')
    label, missions, scopes = payload.get('label'), payload.get('missions'), payload.get('scopes')
    days = payload.get('expires_days', 30)
    if not isinstance(label, str) or not 1 <= len(label.strip()) <= 80 or any(ord(c) < 32 for c in label):
        raise AccessError('Nom d’accès invalide.', '400 Bad Request')
    if not isinstance(missions, list) or not 1 <= len(missions) <= 100 or any(not isinstance(item, str) for item in missions):
        raise AccessError('Sélectionnez entre 1 et 100 missions explicites.', '400 Bad Request')
    if not isinstance(scopes, list) or not scopes or any(not isinstance(item, str) or item not in SCOPES for item in scopes):
        raise AccessError('Portées de lecture invalides.', '400 Bad Request')
    if type(days) is not int or not 1 <= days <= 365:
        raise AccessError('Expiration attendue entre 1 et 365 jours.', '400 Bad Request')
    identifier = uuid4().hex
    token = f'arr_{identifier}.{secrets.token_urlsafe(32)}'
    now = time.time()
    with database.connect(db_path) as connection:
        connection.execute('BEGIN IMMEDIATE')
        for mission in set(missions):
            if not connection.execute('SELECT 1 FROM missions WHERE uuid = ?', (mission,)).fetchone():
                raise AccessError('Une mission sélectionnée est introuvable.', '400 Bad Request')
        count = connection.execute('SELECT COUNT(*) FROM integration_credentials WHERE revoked_at IS NULL AND expires_at > ?', (now,)).fetchone()[0]
        if count >= 50:
            raise AccessError('Limite de 50 accès actifs atteinte.', '409 Conflict')
        connection.execute('INSERT INTO integration_credentials VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)',
            (identifier, label.strip(), hashlib.sha256(token.encode()).hexdigest(), json.dumps(sorted(set(missions))),
             json.dumps(sorted(set(scopes))), now, now + days * 86400, actor))
        audit(connection, identifier, 'credential.create', 'allowed')
        result = credential_metadata(connection.execute('SELECT * FROM integration_credentials WHERE uuid = ?', (identifier,)).fetchone())
    return result | {'token': token}


def revoke_credential(db_path, credential_uuid):
    with database.connect(db_path) as connection:
        cursor = connection.execute('UPDATE integration_credentials SET revoked_at = COALESCE(revoked_at, ?) WHERE uuid = ?', (time.time(), credential_uuid))
        if not cursor.rowcount:
            raise AccessError('Accès introuvable.', '404 Not Found')
        audit(connection, credential_uuid, 'credential.revoke', 'allowed')


def authenticate(db_path, authorization):
    scheme, _, token = (authorization or '').partition(' ')
    if scheme.lower() != 'bearer' or len(token) > 256:
        raise AccessError('Jeton Bearer requis ou invalide.', '401 Unauthorized')
    identifier = token.split('.', 1)[0].removeprefix('arr_')
    with database.connect(db_path) as connection:
        row = connection.execute('SELECT * FROM integration_credentials WHERE uuid = ?', (identifier,)).fetchone()
        valid = row and hmac.compare_digest(row['digest'], hashlib.sha256(token.encode()).hexdigest())
        if not valid or row['revoked_at'] is not None or row['expires_at'] <= time.time():
            raise AccessError('Jeton Bearer requis ou invalide.', '401 Unauthorized')
        return credential_metadata(row)


def consume_rate(db_path, principal):
    window = int(time.time() // 60)
    limited = False
    with database.connect(db_path) as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT * FROM integration_rate WHERE credential_uuid = ?', (principal['uuid'],)).fetchone()
        count = row['count'] + 1 if row and row['window'] == window else 1
        limited = count > 60
        if not limited:
            connection.execute('INSERT OR REPLACE INTO integration_rate VALUES (?, ?, ?)', (principal['uuid'], window, count))
        else:
            audit(connection, principal['uuid'], 'rate.limit', 'denied')
    if limited:
        raise AccessError('Limite de 60 requêtes par minute atteinte.', '429 Too Many Requests')


def uuid_value(value):
    if not isinstance(value, str):
        raise AccessError('Identifiant attendu.', '400 Bad Request')
    try:
        if str(UUID(value)) != value:
            raise ValueError
    except ValueError:
        raise AccessError('Identifiant invalide.', '400 Bad Request') from None
    return value


def pagination(arguments):
    limit, offset = arguments.get('limit', 50), arguments.get('offset', 0)
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise AccessError('Pagination invalide.', '400 Bad Request')
    return limit, offset


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        raise AccessError('Horodatage ISO avec fuseau attendu.', '400 Bad Request')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except ValueError:
        raise AccessError('Horodatage ISO avec fuseau attendu.', '400 Bad Request') from None


OPERATIONS = {
    'list_missions': ('missions:read', {'limit', 'offset'}, set()),
    'get_mission': ('missions:read', {'mission_uuid'}, {'mission_uuid'}),
    'list_entries': ('entries:read', {'mission_uuid', 'limit', 'offset', 'since', 'until'}, {'mission_uuid'}),
    'list_reports': ('reports:read', {'mission_uuid', 'limit', 'offset'}, {'mission_uuid'}),
    'get_report': ('reports:read', {'mission_uuid', 'version_uuid'}, {'mission_uuid', 'version_uuid'}),
}


def read_operation(db_path, principal, operation, arguments):
    try:
        result = _read_operation(db_path, principal, operation, arguments)
    except AccessError:
        with database.connect(db_path) as connection:
            audit(connection, principal['uuid'], operation if operation in OPERATIONS else 'unknown', 'denied')
        raise
    with database.connect(db_path) as connection:
        audit(connection, principal['uuid'], operation, 'allowed')
    return result


def _read_operation(db_path, principal, operation, args):
    if operation not in OPERATIONS:
        raise AccessError('Opération inconnue ou interdite.', '404 Not Found')
    scope, allowed, required = OPERATIONS[operation]
    if not isinstance(args, dict) or set(args) - allowed or not required <= set(args):
        raise AccessError('Arguments invalides.', '400 Bad Request')
    if scope not in principal['scopes']:
        raise AccessError('Portée non autorisée.')
    if 'mission_uuid' in args:
        mission_uuid = uuid_value(args['mission_uuid'])
        if mission_uuid not in principal['missions']:
            raise AccessError('Ressource introuvable.', '404 Not Found')
    limit, offset = pagination(args)
    with database.connect(db_path) as connection:
        if operation == 'list_missions':
            marks = ','.join('?' for _ in principal['missions'])
            rows = connection.execute(f'SELECT * FROM missions WHERE uuid IN ({marks}) ORDER BY uuid LIMIT ? OFFSET ?',
                                      (*principal['missions'], limit + 1, offset)).fetchall()
        elif operation == 'get_mission':
            row = connection.execute('SELECT * FROM missions WHERE uuid = ?', (mission_uuid,)).fetchone()
            if not row:
                raise AccessError('Ressource introuvable.', '404 Not Found')
            return dict(row)
        elif operation == 'list_entries':
            since = timestamp(args['since']) if 'since' in args else None
            until = timestamp(args['until']) if 'until' in args else None
            if since and until and since >= until:
                raise AccessError('La fin doit suivre le début.', '400 Bad Request')
            query = '''SELECT uuid, mission_uuid, entry_type, content, occurred_at,
                       created_at, original_name, transcription_status, transcript
                       FROM entries WHERE mission_uuid = ?'''
            values = [mission_uuid]
            for bound, sign in ((since, '>='), (until, '<')):
                if bound:
                    query += f' AND julianday(occurred_at) {sign} julianday(?)'
                    values.append(bound.isoformat())
            rows = connection.execute(query + ' ORDER BY julianday(occurred_at), uuid LIMIT ? OFFSET ?', (*values, limit + 1, offset)).fetchall()
        elif operation == 'list_reports':
            rows = connection.execute('''SELECT uuid, mission_uuid, version, validated_by, validated_at,
                        identity_source, source_version_uuid, revision_reason FROM report_versions
                        WHERE mission_uuid = ? ORDER BY version LIMIT ? OFFSET ?''', (mission_uuid, limit + 1, offset)).fetchall()
        else:
            version_uuid = uuid_value(args['version_uuid'])
            row = connection.execute('''SELECT uuid, mission_uuid, version, content, validated_by, validated_at,
                        identity_source, source_version_uuid, revision_reason FROM report_versions
                        WHERE uuid = ? AND mission_uuid = ?''', (version_uuid, mission_uuid)).fetchone()
            if not row:
                raise AccessError('Rapport validé introuvable.', '404 Not Found')
            return dict(row)
    items = [dict(row) for row in rows[:limit]]
    if operation == 'list_entries':
        for item in items:
            if item['entry_type'] == 'audio':
                item['transcript_human_validated'] = False
                if item['transcription_status'] != 'completed':
                    item['transcript'] = None
    return {'items': items, 'next_offset': offset + limit if len(rows) > limit else None}
