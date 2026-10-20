import hashlib
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from wsgiref.util import setup_testing_defaults

import app
import database
import integration_service as service


class IntegrationsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / 'test.sqlite3')
        self.patch_db = patch.object(app, 'DATABASE_PATH', self.path)
        self.patch_db.start()
        self.patch_env = patch.dict(os.environ, {'ARCENAL_PUBLIC_URL': 'https://report.example.org/arcenal-report', 'ARCENAL_DEPLOYMENT': 'yunohost'})
        self.patch_env.start()
        database.initialise(self.path)
        self.mission, self.other = database.list_missions(self.path)
        self.credential = service.create_credential(self.path, {
            'label': 'Hermes test', 'missions': [self.mission['uuid']],
            'scopes': list(service.SCOPES), 'expires_days': 30, 'confirmed': True,
        }, 'admin')
        self.token = self.credential['token']

    def tearDown(self):
        self.patch_db.stop()
        self.patch_env.stop()
        self.directory.cleanup()

    def request(self, method, path, payload=None, token=None, admin=False, origin=None, extra=None, query=''):
        environ = {}
        setup_testing_defaults(environ)
        encoded = json.dumps(payload).encode() if payload is not None else b''
        environ.update(REQUEST_METHOD=method, PATH_INFO=path, CONTENT_LENGTH=str(len(encoded)), CONTENT_TYPE='application/json', QUERY_STRING=query,
                       HTTP_ACCEPT='application/json, text/event-stream', **{'wsgi.input': BytesIO(encoded)})
        if token is not None:
            environ['HTTP_AUTHORIZATION'] = 'Bearer ' + token
        if admin:
            environ.update(HTTP_REMOTE_USER='admin', HTTP_X_REPORT_ADMIN='1')
        if origin:
            environ['HTTP_ORIGIN'] = origin
        if extra:
            environ.update(extra)
        result = {}
        body = b''.join(app.application(environ, lambda status, headers: result.update(status=status, headers=dict(headers))))
        return result['status'], json.loads(body) if body and 'application/json' in result['headers']['Content-Type'] else body, result['headers']

    def rpc(self, method, params=None, identifier=1, **kwargs):
        body = {'jsonrpc': '2.0', 'id': identifier, 'method': method, 'params': params or {}}
        return self.request('POST', '/mcp', body, token=self.token, **kwargs)

    def test_mcp_initialize_notification_tools_and_read(self):
        status, result, _ = self.rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '1'}})
        self.assertEqual(status, '200 OK')
        self.assertEqual(result['result']['protocolVersion'], '2025-06-18')
        self.assertEqual(result['result']['capabilities'], {'tools': {'listChanged': False}})
        status, body, _ = self.request('POST', '/mcp', {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, token=self.token)
        self.assertEqual((status, body), ('202 Accepted', b''))
        status, result, _ = self.rpc('tools/list')
        self.assertEqual(len(result['result']['tools']), 5)
        self.assertTrue(all(tool['annotations']['readOnlyHint'] for tool in result['result']['tools']))
        status, result, _ = self.rpc('tools/call', {'name': 'report_list_missions'}, extra={'HTTP_MCP_PROTOCOL_VERSION': '2025-06-18'})
        self.assertEqual(result['result']['structuredContent']['items'][0]['uuid'], self.mission['uuid'])
        self.assertEqual(len(result['result']['structuredContent']['items']), 1)
        self.assertEqual(self.rpc('ping')[1]['result'], {})

    def test_bearer_required_even_with_sso_and_revocation_immediate(self):
        for token in (None, '', 'wrong'):
            status, _, headers = self.request('POST', '/mcp', {}, token=token, admin=True)
            self.assertEqual(status, '401 Unauthorized')
            self.assertIn('WWW-Authenticate', headers)
        service.revoke_credential(self.path, self.credential['uuid'])
        self.assertEqual(self.rpc('tools/list')[0], '401 Unauthorized')

    def test_expiry_is_enforced(self):
        with patch.object(service.time, 'time', return_value=self.credential['expires_at'] + 1):
            self.assertEqual(self.rpc('tools/list')[0], '401 Unauthorized')

    def test_origin_query_protocol_content_size_and_methods_refused(self):
        self.assertEqual(self.rpc('ping', origin='https://evil.example')[0], '403 Forbidden')
        self.assertEqual(self.rpc('ping', query='token=not-a-real-secret')[0], '400 Bad Request')
        self.assertEqual(self.rpc('ping', extra={'HTTP_MCP_PROTOCOL_VERSION': 'invalid'})[0], '400 Bad Request')
        self.assertEqual(self.rpc('ping', extra={'HTTP_ACCEPT': 'text/html'})[0], '406 Not Acceptable')
        self.assertEqual(self.rpc('ping', extra={'CONTENT_TYPE': 'text/plain'})[0], '415 Unsupported Media Type')
        self.assertEqual(self.rpc('ping', extra={'CONTENT_LENGTH': '100001'})[0], '413 Payload Too Large')
        for method in ('GET', 'DELETE', 'PUT'):
            self.assertEqual(self.request(method, '/mcp', token=self.token)[0], '405 Method Not Allowed')

    def test_jsonrpc_invalid_requests_and_unsupported_operations(self):
        for payload in ([], {'jsonrpc': '2.0', 'method': 7}, {'jsonrpc': '2.0', 'id': True, 'method': 'ping'}):
            self.assertEqual(self.request('POST', '/mcp', payload, token=self.token)[0], '400 Bad Request')
        self.assertEqual(self.rpc('reports/write')[1]['error']['code'], -32601)
        self.assertEqual(self.rpc('tools/call', {'name': 'report_save_report', 'arguments': {}})[1]['error']['code'], -32602)
        self.assertEqual(self.rpc('tools/call', {'name': 'report_list_missions', 'arguments': {'sql': 'DROP TABLE missions'}})[1]['error']['code'], -32602)
        self.assertEqual(self.rpc('tools/call', {'name': 'report_list_missions', 'arguments': {'limit': True}})[1]['error']['code'], -32602)

    def test_rest_and_mcp_share_scope_and_mission_controls(self):
        rest_base = '/api/integrations/v1/missions/'
        status, rest, _ = self.request('GET', rest_base + self.mission['uuid'] + '/entries', token=self.token)
        self.assertEqual(status, '200 OK')
        rpc = self.rpc('tools/call', {'name': 'report_list_entries', 'arguments': {'mission_uuid': self.mission['uuid']}})[1]
        self.assertEqual(rest, json.loads(rpc['result']['content'][0]['text']))
        self.assertEqual(self.request('GET', rest_base + self.other['uuid'], token=self.token)[0], '404 Not Found')
        denied = self.rpc('tools/call', {'name': 'report_get_mission', 'arguments': {'mission_uuid': self.other['uuid']}})[1]
        self.assertTrue(denied['result']['isError'])
        self.assertEqual(self.request('POST', rest_base, {}, token=self.token)[0], '405 Method Not Allowed')

    def test_scope_limited_tool_catalog_and_rest_refusal(self):
        credential = service.create_credential(self.path, {'label': 'Limité', 'missions': [self.mission['uuid']], 'scopes': ['reports:read'], 'confirmed': True}, 'admin')
        self.token = credential['token']
        tools = self.rpc('tools/list')[1]['result']['tools']
        self.assertEqual({item['name'] for item in tools}, {'report_list_reports', 'report_get_report'})
        self.assertEqual(self.request('GET', '/api/integrations/v1/missions', token=self.token)[0], '403 Forbidden')

    def test_read_api_pagination_filters_and_private_fields(self):
        for index, hour in enumerate(('08:12', '09:05')):
            entry = database.add_text_entry(self.path, self.mission['uuid'], f'Observation {index}')
            with database.connect(self.path) as connection:
                connection.execute('UPDATE entries SET occurred_at = ? WHERE uuid = ?', (f'2026-09-25T{hour}:00+02:00', entry['uuid']))
        entry = database.add_audio_entry(self.path, self.mission['uuid'], 'note.wav', 'private/path.wav', 'audio/wav')
        database.update_transcription(self.path, entry['uuid'], 'completed', 'Texte à vérifier', 'Diagnostic privé')
        base = f"/api/integrations/v1/missions/{self.mission['uuid']}/entries"
        status, result, _ = self.request('GET', base, token=self.token, query='limit=1')
        self.assertEqual(status, '200 OK')
        self.assertEqual(len(result['items']), 1)
        self.assertEqual(result['next_offset'], 1)
        status, result, _ = self.request('GET', base, token=self.token, query='offset=2')
        audio = next(item for item in result['items'] if item['entry_type'] == 'audio')
        self.assertFalse(audio['transcript_human_validated'])
        self.assertNotIn('file_path', audio)
        self.assertNotIn('transcription_error', audio)
        status, result, _ = self.request('GET', base, token=self.token, query='since=2026-09-25T06:00:00Z&until=2026-09-25T07:00:00Z')
        self.assertEqual(len(result['items']), 1)
        for query in ('limit=101', 'since=2026-09-25', 'offset=-1', 'limit=1&limit=2', 'token=x'):
            self.assertEqual(self.request('GET', base, token=self.token, query=query)[0], '400 Bad Request')

    def test_only_validated_reports_are_visible_and_sources_stay_private(self):
        draft = database.save_report(self.path, self.mission['uuid'], 'Brouillon privé')
        base = f"/api/integrations/v1/missions/{self.mission['uuid']}/reports"
        self.assertEqual(self.request('GET', base, token=self.token)[1]['items'], [])
        saved = database.validate_report(self.path, self.mission['uuid'], draft['uuid'], draft['content'], draft['updated_at'], 'Équipier', 'local_declared')
        version_uuid = saved['validation']['uuid']
        result = self.request('GET', base + '/' + version_uuid, token=self.token)[1]
        self.assertEqual(result['content'], draft['content'])
        self.assertNotIn('sources_json', result)
        self.assertNotIn('mission_json', result)

    def test_machine_token_cannot_use_normal_browser_api_or_uploads(self):
        for method, path in [('GET', '/api/v1/missions'), ('PUT', f"/api/v1/missions/{self.mission['uuid']}/report"), ('GET', '/api/v1/entries/anything/file')]:
            self.assertEqual(self.request(method, path, {'content': 'Interdit'}, token=self.token, admin=True)[0], '403 Forbidden')

    def test_admin_management_requires_role_identity_origin_confirmation(self):
        base = '/api/v1/integrations'
        self.assertEqual(self.request('GET', base, admin=False)[0], '403 Forbidden')
        self.assertEqual(self.request('GET', base, extra={'HTTP_REMOTE_USER': 'equipier'})[0], '403 Forbidden')
        self.assertEqual(self.request('GET', base, extra={'HTTP_X_REPORT_ADMIN': '1'})[0], '403 Forbidden')
        payload = {'label': 'Autre accès', 'missions': [self.other['uuid']], 'scopes': ['missions:read'], 'confirmed': True}
        self.assertEqual(self.request('POST', base + '/credentials', payload, admin=True)[0], '403 Forbidden')
        self.assertEqual(self.request('POST', base + '/credentials', payload | {'confirmed': False}, admin=True, origin='https://report.example.org')[0], '400 Bad Request')
        status, created, _ = self.request('POST', base + '/credentials', payload, admin=True, origin='https://report.example.org')
        self.assertEqual(status, '201 Created')
        status, listing, headers = self.request('GET', base, admin=True)
        self.assertEqual(status, '200 OK')
        self.assertEqual(listing['mcp_url'], 'https://report.example.org/arcenal-report/mcp')
        self.assertNotIn(created['token'], json.dumps(listing))
        self.assertNotIn('digest', json.dumps(listing))
        self.assertEqual(headers['Cache-Control'], 'no-store')
        url = base + '/credentials/' + created['uuid'] + '/revoke'
        self.assertEqual(self.request('POST', url, {'confirmed': True}, admin=True, origin='https://report.example.org')[0], '200 OK')
        self.assertEqual(self.request('GET', '/api/integrations/v1/missions', token=created['token'])[0], '401 Unauthorized')

    def test_credentials_validation_and_no_plaintext_in_database(self):
        payload = {'label': 'Test', 'missions': [self.mission['uuid']], 'scopes': ['missions:read'], 'confirmed': True}
        for change in ({'missions': ['*']}, {'missions': []}, {'scopes': ['write']}, {'expires_days': True}, {'expires_days': 366}, {'unknown': 'x'}):
            with self.assertRaises(service.AccessError):
                service.create_credential(self.path, payload | change, 'admin')
        with database.connect(self.path) as connection:
            stored = connection.execute('SELECT digest FROM integration_credentials').fetchone()[0]
            audit = str([dict(row) for row in connection.execute('SELECT * FROM integration_audit')])
        self.assertEqual(stored, hashlib.sha256(self.token.encode()).hexdigest())
        self.assertNotIn(self.token, audit)
        self.assertNotIn(self.token.encode(), Path(self.path).read_bytes())

    def test_rate_limit_is_shared_by_connections_and_concurrent_calls(self):
        principal = service.authenticate(self.path, 'Bearer ' + self.token)
        def consume(_):
            service.consume_rate(self.path, principal)
        with patch.object(service.time, 'time', return_value=1_800_000_000), ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(consume, range(60)))
            with self.assertRaises(service.AccessError) as error:
                service.consume_rate(self.path, principal)
            self.assertEqual(error.exception.status, '429 Too Many Requests')

    def test_yunohost_browser_api_requires_session_and_same_origin_for_writes(self):
        self.assertEqual(self.request('GET', '/api/v1/missions')[0], '401 Unauthorized')
        base = f"/api/v1/missions/{self.mission['uuid']}/entries"
        self.assertEqual(self.request('POST', base, {'content': 'Note'}, admin=True)[0], '403 Forbidden')
        self.assertEqual(self.request('POST', base, {'content': 'Note'}, admin=True, origin='https://report.example.org')[0], '201 Created')

    def test_create_mission_requires_sso_origin_and_no_machine_token(self):
        payload = {'client_name': 'Recette', 'title': 'Poste manuel', 'mission_date': '2026-10-20'}
        origin = 'https://report.example.org'
        self.assertEqual(self.request('POST', '/api/v1/missions', payload, origin=origin)[0], '401 Unauthorized')
        self.assertEqual(self.request('POST', '/api/v1/missions', payload, admin=True)[0], '403 Forbidden')
        self.assertEqual(self.request('POST', '/api/v1/missions', payload, admin=True, origin='https://evil.example')[0], '403 Forbidden')
        self.assertEqual(self.request('POST', '/api/v1/missions', payload, token=self.token, admin=True, origin=origin)[0], '403 Forbidden')
        self.assertEqual(len(database.list_missions(self.path)), 2)
        status, mission, _ = self.request('POST', '/api/v1/missions', payload, admin=True, origin=origin,
                                        extra={'HTTP_AUTHORIZATION': 'Basic cmVjZXR0ZTpmYWtl'})
        self.assertEqual(status, '201 Created')
        self.assertEqual(database.get_mission(self.path, mission['uuid'])['title'], 'Poste manuel')
        # Creation never expands an existing MCP token's mission scope.
        result = self.rpc('tools/call', {'name': 'report_list_missions'}, extra={'HTTP_MCP_PROTOCOL_VERSION': '2025-06-18'})[1]
        self.assertEqual(len(result['result']['structuredContent']['items']), 1)

    def test_yunohost_basic_header_does_not_hide_missions_for_an_authenticated_user(self):
        # Synthetic Basic value only: YunoHost's SSO may forward this header
        # alongside the trusted Remote-User identity. It is NOT a MCP Bearer.
        extra = {'HTTP_AUTHORIZATION': 'Basic cmVjZXR0ZTpmYWtlLXBhc3N3b3Jk'}
        status, body, _ = self.request('GET', '/api/v1/missions', admin=True, extra=extra)
        self.assertEqual(status, '200 OK')
        self.assertEqual(len(body['missions']), 2)
        status, body, _ = self.request('GET', f"/api/v1/missions/{self.mission['uuid']}/entries", admin=True, extra=extra)
        self.assertEqual(status, '200 OK')
        self.assertIn('entries', body)

    def test_basic_header_alone_never_authenticates_a_yunohost_user(self):
        extra = {'HTTP_AUTHORIZATION': 'Basic cmVjZXR0ZTpmYWtlLXBhc3N3b3Jk'}
        self.assertEqual(self.request('GET', '/api/v1/missions', extra=extra)[0], '401 Unauthorized')
        self.assertEqual(self.request('POST', '/mcp', {}, extra=extra)[0], '401 Unauthorized')

    def test_package_copies_modules_and_protects_separate_routes(self):
        import tomllib
        root = Path(app.ROOT)
        manifest = tomllib.loads((root / 'manifest.toml').read_text())
        permissions = manifest['resources']['permissions']
        self.assertEqual(permissions['machine']['allowed'], 'visitors')
        self.assertFalse(permissions['machine']['auth_header'])
        self.assertEqual(permissions['integrations']['allowed'], 'admins')
        self.assertNotIn('/api/', permissions['machine']['additional_urls'])
        for script in ('install', 'upgrade'):
            content = (root / 'scripts' / script).read_text()
            for module in ('integration_service.py', 'integration_http.py', 'hermes_client.py'):
                self.assertIn(module, content)
        nginx = (root / 'conf/nginx.conf').read_text()
        self.assertIn('location = __PATH__/mcp', nginx)
        self.assertIn('proxy_set_header X-Report-Admin "";', nginx)
        self.assertIn('proxy_set_header X-Report-Admin "1";', nginx)
        self.assertIn('UMask=0077', (root / 'conf/systemd.service').read_text())

    def test_admin_page_uses_packaged_web_directory(self):
        # Nginx proxies this page for the server-side admin check; static files
        # are in install_dir/web, not backend/static, on a YunoHost installation.
        import shutil
        import subprocess
        import sys
        root = Path(self.directory.name) / 'packaged'
        backend = root / 'backend'
        web = root / 'web'
        backend.mkdir(parents=True)
        web.mkdir()
        for name in ('app.py', 'database.py', 'integration_service.py', 'integration_http.py', 'hermes_client.py', 'transcription.py', 'ai_reporting.py', 'report_document.py', 'weather.py'):
            shutil.copy(Path(app.ROOT) / name, backend / name)
        result = subprocess.run([sys.executable, '-c', 'import app; print(app.STATIC_DIRECTORY)'], cwd=backend, capture_output=True, text=True, check=True)
        self.assertEqual(Path(result.stdout.strip()).resolve(), web.resolve())


if __name__ == '__main__':
    unittest.main()
