import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from wsgiref.util import setup_testing_defaults
from zipfile import ZipFile

import app
import database


class ReportVersionsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / 'reports.sqlite3')
        self.db_patch = patch.object(app, 'DATABASE_PATH', self.path)
        self.db_patch.start()
        database.initialise(self.path)
        self.mission, self.other = database.list_missions(self.path)
        self.base = f"/api/v1/missions/{self.mission['uuid']}/report"
        self.draft = database.save_report(self.path, self.mission['uuid'], 'Rapport relu. Faits conservés.')

    def tearDown(self):
        self.db_patch.stop()
        self.directory.cleanup()

    def request(self, method, path, body=None, actor=None):
        encoded = json.dumps(body).encode() if body is not None else b''
        environ = {}
        setup_testing_defaults(environ)
        environ.update(REQUEST_METHOD=method, PATH_INFO=path, CONTENT_LENGTH=str(len(encoded)),
                       CONTENT_TYPE='application/json', **{'wsgi.input': BytesIO(encoded)})
        if actor:
            environ['HTTP_REMOTE_USER'] = actor
        result = {}
        content = b''.join(app.application(environ, lambda status, headers: result.update(status=status, headers=dict(headers))))
        if 'application/json' in result['headers']['Content-Type']:
            content = json.loads(content)
        return result['status'], content

    def validation_body(self, report=None):
        report = report or self.draft
        return {'uuid': report['uuid'], 'content': report['content'],
                'expected_updated_at': report['updated_at'], 'author': 'Équipier local', 'confirmed': True}

    def validate(self, report=None):
        status, saved = self.request('POST', self.base + '/validate', self.validation_body(report))
        self.assertEqual(status, '201 Created')
        return saved

    def test_validation_records_identity_and_freezes_report(self):
        status, saved = self.request('POST', self.base + '/validate', self.validation_body(), actor='sso-equipier')
        self.assertEqual(status, '201 Created')
        self.assertEqual(saved['status'], 'validated')
        self.assertEqual(saved['validation']['validated_by'], 'sso-equipier')
        self.assertEqual(saved['validation']['identity_source'], 'sso')
        status, error = self.request('PUT', self.base, {'uuid': self.draft['uuid'], 'content': 'Écrasement'})
        self.assertEqual(status, '409 Conflict')
        self.assertIn('validé', error['error'])
        self.assertEqual(database.get_latest_report(self.path, self.mission['uuid'])['content'], self.draft['content'])

    def test_requires_confirmation_actor_and_exact_reviewed_text(self):
        for changes, expected in [({'confirmed': False}, '400 Bad Request'),
                                  ({'confirmed': 'true'}, '400 Bad Request'),
                                  ({'author': ''}, '400 Bad Request'),
                                  ({'content': 'Non enregistré'}, '409 Conflict'),
                                  ({'expected_updated_at': 'stale'}, '409 Conflict'),
                                  ({'content': 4}, '400 Bad Request')]:
            body = self.validation_body() | changes
            status, _ = self.request('POST', self.base + '/validate', body)
            self.assertEqual(status, expected)
        self.assertEqual(database.list_report_versions(self.path, self.mission['uuid']), [])

    def test_cannot_validate_or_edit_another_missions_report(self):
        other_base = f"/api/v1/missions/{self.other['uuid']}/report"
        status, _ = self.request('POST', other_base + '/validate', self.validation_body())
        self.assertEqual(status, '409 Conflict')
        status, _ = self.request('PUT', other_base, {'uuid': self.draft['uuid'], 'content': 'Interdit'})
        self.assertEqual(status, '409 Conflict')
        saved = self.validate()
        status, _ = self.request('GET', other_base + '/versions/' + saved['validation']['uuid'])
        self.assertEqual(status, '404 Not Found')
        status, _ = self.request('POST', other_base + '/versions/' + saved['validation']['uuid'] + '/reopen', {'reason': 'Interdit', 'confirmed': True})
        self.assertEqual(status, '409 Conflict')

    def test_reopen_keeps_original_and_creates_new_validated_version(self):
        first = self.validate()
        version_uuid = first['validation']['uuid']
        status, reopened = self.request('POST', self.base + '/versions/' + version_uuid + '/reopen', {'reason': 'Précision technique', 'confirmed': True})
        self.assertEqual(status, '201 Created')
        self.assertNotEqual(reopened['uuid'], first['uuid'])
        self.assertEqual(reopened['status'], 'draft')
        self.assertEqual(reopened['source_version_uuid'], version_uuid)
        status, edited = self.request('PUT', self.base, {'uuid': reopened['uuid'], 'content': 'Nouvelle version corrigée.', 'expected_updated_at': reopened['updated_at']})
        self.assertEqual(status, '200 OK')
        second = self.validate(edited)
        self.assertEqual(second['validation']['version'], 2)
        original = database.get_report_version(self.path, self.mission['uuid'], version_uuid)
        self.assertEqual(original['content'], first['content'])
        self.assertEqual(len(database.list_report_versions(self.path, self.mission['uuid'])), 2)

    def test_reopen_requires_nonempty_reason_and_confirmation(self):
        saved = self.validate()
        url = self.base + '/versions/' + saved['validation']['uuid'] + '/reopen'
        for payload in ({'reason': ''}, {'reason': 'Motif'}, {'reason': 'x' * 501, 'confirmed': True}):
            status, _ = self.request('POST', url, payload)
            self.assertEqual(status, '400 Bad Request')

    def test_concurrent_validation_accepts_only_one(self):
        def attempt(_):
            try:
                database.validate_report(self.path, self.mission['uuid'], self.draft['uuid'], self.draft['content'], self.draft['updated_at'], 'Équipier', 'local_declared')
                return 'validated'
            except database.ReportConflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(list(executor.map(attempt, range(2))), ['validated', 'conflict'])

    def test_stale_edit_refused(self):
        database.save_report(self.path, self.mission['uuid'], 'Modification concurrente', self.draft['uuid'])
        status, _ = self.request('PUT', self.base, {'uuid': self.draft['uuid'], 'content': 'Écrasement périmé', 'expected_updated_at': self.draft['updated_at']})
        self.assertEqual(status, '409 Conflict')

    def test_database_triggers_prevent_overwrite_or_deletion(self):
        saved = self.validate()
        for statement, value in [
            ('UPDATE report_versions SET content = \'altéré\' WHERE uuid = ?', saved['validation']['uuid']),
            ('DELETE FROM report_versions WHERE uuid = ?', saved['validation']['uuid']),
            ('UPDATE reports SET content = \'altéré\' WHERE uuid = ?', saved['uuid']),
            ('DELETE FROM reports WHERE uuid = ?', saved['uuid']),
        ]:
            with self.assertRaises(sqlite3.IntegrityError), database.connect(self.path) as connection:
                connection.execute(statement, (value,))

    def test_source_snapshot_and_export_do_not_include_later_notes(self):
        saved = self.validate()
        version_uuid = saved['validation']['uuid']
        snapshot = database.get_report_version(self.path, self.mission['uuid'], version_uuid)
        database.add_text_entry(self.path, self.mission['uuid'], 'Fait ajouté après validation')
        self.assertNotIn('Fait ajouté après validation', snapshot['sources_json'])
        database.save_report(self.path, self.mission['uuid'], 'Un autre brouillon')
        status, docx = self.request('GET', self.base + '/versions/' + version_uuid + '/docx')
        self.assertEqual(status, '200 OK')
        with ZipFile(BytesIO(docx)) as archive:
            text = archive.read('word/document.xml').decode()
        self.assertIn('Faits conservés.', text)
        self.assertNotIn('Un autre brouillon', text)
        status, visible = self.request('GET', self.base + '/versions/' + version_uuid)
        self.assertEqual(status, '200 OK')
        self.assertNotIn('sources_json', visible)

    def test_migration_preserves_existing_report_and_is_idempotent(self):
        path = str(Path(self.directory.name) / 'legacy.sqlite3')
        with sqlite3.connect(path) as connection:
            connection.execute('CREATE TABLE reports (uuid TEXT PRIMARY KEY, mission_uuid TEXT, content TEXT, created_at TEXT, updated_at TEXT)')
            connection.execute("INSERT INTO reports VALUES ('ancien', 'mission', 'Texte historique', 'date', 'date')")
        database.initialise(path)
        database.initialise(path)
        with database.connect(path) as connection:
            self.assertEqual(connection.execute("SELECT content FROM reports WHERE uuid = 'ancien'").fetchone()[0], 'Texte historique')
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM report_versions').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
