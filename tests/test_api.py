import base64
import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from wsgiref.util import setup_testing_defaults

import app
import database


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.temporary_file = tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False)
        self.temporary_file.close()
        self.previous_path = app.DATABASE_PATH
        self.previous_upload_directory = app.UPLOAD_DIRECTORY
        app.DATABASE_PATH = self.temporary_file.name
        self.upload_directory = tempfile.TemporaryDirectory()
        app.UPLOAD_DIRECTORY = Path(self.upload_directory.name)
        database.initialise(app.DATABASE_PATH)

    def tearDown(self):
        app.DATABASE_PATH = self.previous_path
        app.UPLOAD_DIRECTORY = self.previous_upload_directory
        self.upload_directory.cleanup()
        os.unlink(self.temporary_file.name)

    def request_raw(self, method, path, body=b'', content_type='application/json'):
        environ = {}
        setup_testing_defaults(environ)
        environ['REQUEST_METHOD'] = method
        environ['PATH_INFO'] = path
        environ['CONTENT_LENGTH'] = str(len(body))
        environ['CONTENT_TYPE'] = content_type
        environ['wsgi.input'] = BytesIO(body)
        result = {}
        response = b''.join(app.application(environ, lambda status, headers: result.update(status=status, headers=headers)))
        return result['status'], dict(result['headers']), response

    def request(self, method, path, body=b'', content_type='application/json'):
        status, _, response = self.request_raw(method, path, body, content_type)
        return status, json.loads(response)

    def test_lists_seeded_missions_and_adds_a_text_entry(self):
        status, payload = self.request('GET', '/api/v1/missions')
        self.assertEqual(status, '200 OK'); self.assertEqual(len(payload['missions']), 2)
        mission_uuid = payload['missions'][0]['uuid']
        status, created = self.request('POST', f'/api/v1/missions/{mission_uuid}/entries', json.dumps({'content': 'Contrôle terminé.'}).encode())
        self.assertEqual(status, '201 Created'); self.assertEqual(created['content'], 'Contrôle terminé.')
        status, entries = self.request('GET', f'/api/v1/missions/{mission_uuid}/entries')
        self.assertEqual(status, '200 OK'); self.assertTrue(any(entry['content'] == 'Contrôle terminé.' for entry in entries['entries']))

    def test_rejects_an_empty_entry(self):
        mission_uuid = database.list_missions(app.DATABASE_PATH)[0]['uuid']
        status, payload = self.request('POST', f'/api/v1/missions/{mission_uuid}/entries', b'{}')
        self.assertEqual(status, '400 Bad Request')
        self.assertIn('note', payload['error'])

    def test_uploads_and_serves_a_mission_photo(self):
        mission_uuid = database.list_missions(app.DATABASE_PATH)[0]['uuid']
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
        boundary = 'photo-test-boundary'
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="../../terrain.png"\r\n'
            'Content-Type: image/png\r\n\r\n'
        ).encode() + png + f'\r\n--{boundary}--\r\n'.encode()
        status, created = self.request(
            'POST', f'/api/v1/missions/{mission_uuid}/photos', body,
            f'multipart/form-data; boundary={boundary}'
        )
        self.assertEqual(status, '201 Created')
        self.assertEqual(created['original_name'], 'terrain.png')
        status, headers, content = self.request_raw('GET', f"/api/v1/entries/{created['uuid']}/file")
        self.assertEqual(status, '200 OK')
        self.assertEqual(headers['Content-Type'], 'image/png')
        self.assertEqual(content, png)

    def test_rejects_a_non_image_upload(self):
        mission_uuid = database.list_missions(app.DATABASE_PATH)[0]['uuid']
        boundary = 'invalid-photo-boundary'
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="danger.html"\r\n'
            'Content-Type: text/html\r\n\r\n<script>alert(1)</script>\r\n'
            f'--{boundary}--\r\n'
        ).encode()
        status, payload = self.request(
            'POST', f'/api/v1/missions/{mission_uuid}/photos', body,
            f'multipart/form-data; boundary={boundary}'
        )
        self.assertEqual(status, '400 Bad Request')
        self.assertIn('pas accepté', payload['error'])

    def test_uploads_and_serves_an_audio_recording(self):
        mission_uuid = database.list_missions(app.DATABASE_PATH)[0]['uuid']
        wav = b'RIFF\x24\x00\x00\x00WAVEfmt ' + b'\x00' * 32
        boundary = 'audio-test-boundary'
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; filename="note.wav"\r\n'
            'Content-Type: audio/wav\r\n\r\n'
        ).encode() + wav + f'\r\n--{boundary}--\r\n'.encode()
        status, created = self.request(
            'POST', f'/api/v1/missions/{mission_uuid}/audio', body,
            f'multipart/form-data; boundary={boundary}'
        )
        self.assertEqual(status, '201 Created')
        self.assertEqual(created['entry_type'], 'audio')
        status, headers, content = self.request_raw('GET', f"/api/v1/entries/{created['uuid']}/file")
        self.assertEqual(status, '200 OK')
        self.assertEqual(headers['Content-Type'], 'audio/wav')
        self.assertEqual(content, wav)

    def test_yunohost_package_uses_relative_frontend_assets(self):
        index = (Path(app.ROOT) / 'static' / 'index.html').read_text(encoding='utf-8')
        frontend = (Path(app.ROOT) / 'static' / 'app.js').read_text(encoding='utf-8')
        manifest = (Path(app.ROOT) / 'manifest.toml').read_text(encoding='utf-8')
        self.assertIn('href="styles.css"', index)
        self.assertIn('src="app.js"', index)
        self.assertIn("new URL('api/v1/', document.baseURI)", frontend)
        self.assertIn('id = "arcenal_report"', manifest)
