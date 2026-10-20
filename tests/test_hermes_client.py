import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from wsgiref.util import setup_testing_defaults

import app
import database
import hermes_client


class HermesClientTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.path = str(self.root / 'db.sqlite3')
        database.initialise(self.path)
        self.mission = database.list_missions(self.path)[0]
        self.draft = database.save_report(self.path, self.mission['uuid'], 'Constat source à 08:12, pression 4 bar.')
        self.token_file = self.root / 'hermes-token'
        self.token_file.write_text('test-only-ABCDEFGHIJKLMNOPQRSTUVWXYZ-0123456789-not-a-real-key')
        self.token_file.chmod(0o600)
        self.grants_file = self.root / 'grants.json'
        self.grants_file.write_text(json.dumps({'equipier': [self.mission['uuid']]}))
        self.grants_file.chmod(0o600)
        self.environment = patch.dict(os.environ, {
            'ARCENAL_HERMES_URL': 'https://agent.example.org/arcenal/api/v1/agents/report/query',
            'ARCENAL_HERMES_AGENT': 'report',
            'ARCENAL_HERMES_TOKEN_FILE': str(self.token_file),
            'ARCENAL_HERMES_GRANTS_FILE': str(self.grants_file),
            'ARCENAL_PUBLIC_URL': 'https://report.example.org/arcenal-report',
        })
        self.environment.start()
        self.db_patch = patch.object(app, 'DATABASE_PATH', self.path)
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.environment.stop()
        self.directory.cleanup()

    def output(self, **changes):
        value = {'response': 'Constat corrigé à 08:12, pression 4 bar.', 'agent_id': 'report', 'status': 'completed', 'actions': [], 'request_id': 'test-request'} | changes
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(value).encode()
        return response

    def request(self, payload, actor='equipier', origin='https://report.example.org', method='POST'):
        body = json.dumps(payload).encode()
        environ = {}
        setup_testing_defaults(environ)
        environ.update(REQUEST_METHOD=method, PATH_INFO=f"/api/v1/missions/{self.mission['uuid']}/report/assist",
                       CONTENT_TYPE='application/json', CONTENT_LENGTH=str(len(body)), HTTP_REMOTE_USER=actor,
                       HTTP_ORIGIN=origin, **{'wsgi.input': BytesIO(body)})
        result = {}
        content = b''.join(app.application(environ, lambda status, headers: result.update(status=status)))
        return result['status'], json.loads(content)

    def payload(self, **changes):
        return {'uuid': self.draft['uuid'], 'expected_updated_at': self.draft['updated_at'], 'instruction': 'Corriger la syntaxe', 'confirmed': True} | changes

    def test_client_uses_existing_contract_and_dedicated_application_identity(self):
        opener = Mock()
        opener.open.return_value = self.output()
        with patch.object(hermes_client, 'build_opener', return_value=opener):
            proposal = hermes_client.propose(self.draft, 'Corriger', 'equipier')
        self.assertEqual(proposal['request_id'], 'test-request')
        request = opener.open.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.get_header('X-arcenal-application'), 'arcenal-report')
        self.assertEqual(request.get_header('X-arcenal-user'), 'equipier')
        self.assertEqual(set(payload), {'message', 'context'})
        self.assertIn('4 bar', payload['message'])
        self.assertNotIn(self.token_file.read_text(), str(payload))
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 90)

    def test_configuration_requires_explicit_grants_and_private_files(self):
        self.assertTrue(hermes_client.allowed(self.mission['uuid'], 'equipier'))
        self.assertFalse(hermes_client.allowed(self.mission['uuid'], 'autre'))
        self.assertFalse(hermes_client.allowed('other-mission', 'equipier'))
        self.token_file.chmod(0o644)
        self.assertFalse(hermes_client.allowed(self.mission['uuid'], 'equipier'))

    def test_unsafe_urls_and_symlinks_refused(self):
        for url in ('http://agent.example/query', 'https://user:secret@agent.example/api/v1/agents/report/query',
                    'https://agent.example/api/v1/agents/report/query?token=x', 'https://agent.example/not-the-contract'):
            with patch.dict(os.environ, {'ARCENAL_HERMES_URL': url}), self.assertRaises(hermes_client.HermesUnavailable):
                hermes_client.configuration()
        symlink = self.root / 'link'
        symlink.symlink_to(self.token_file)
        with patch.dict(os.environ, {'ARCENAL_HERMES_TOKEN_FILE': str(symlink)}), self.assertRaises(hermes_client.HermesUnavailable):
            hermes_client.configuration()

    def test_redirect_never_forwards_credential(self):
        self.assertIsNone(hermes_client.NoRedirect().redirect_request(None, None, 302, 'Moved', {}, 'https://evil.example'))

    def test_invalid_provider_response_or_tool_action_is_refused(self):
        for changes in ({'response': ''}, {'agent_id': 'arc'}, {'status': 'failed'}, {'actions': [{'tool': 'write'}]}, {'response': 'x' * 20_001}):
            opener = Mock()
            opener.open.return_value = self.output(**changes)
            with patch.object(hermes_client, 'build_opener', return_value=opener), self.assertRaises(hermes_client.HermesUnavailable):
                hermes_client.propose(self.draft, 'Corriger', 'equipier')

    def test_failures_do_not_expose_remote_diagnostic_or_token(self):
        for error in (HTTPError('https://agent.example', 403, 'private remote diagnostic', {}, None), URLError('private remote diagnostic')):
            opener = Mock()
            opener.open.side_effect = error
            with patch.object(hermes_client, 'build_opener', return_value=opener), self.assertRaises(hermes_client.HermesUnavailable) as raised:
                hermes_client.propose(self.draft, 'Corriger', 'equipier')
            self.assertNotIn('private remote diagnostic', str(raised.exception))
            self.assertNotIn(self.token_file.read_text(), str(raised.exception))

    def test_proposal_requires_confirmation_and_does_not_save_or_validate(self):
        opener = Mock()
        opener.open.return_value = self.output()
        with patch.object(hermes_client, 'build_opener', return_value=opener):
            self.assertEqual(self.request(self.payload(confirmed=False))[0], '400 Bad Request')
            opener.open.assert_not_called()
            self.assertEqual(self.request(self.payload(), actor='autre')[0], '403 Forbidden')
            self.assertEqual(self.request(self.payload(), origin='https://evil.example')[0], '403 Forbidden')
            self.assertEqual(self.request(self.payload(expected_updated_at='stale'))[0], '409 Conflict')
            opener.open.assert_not_called()
            status, proposal = self.request(self.payload())
        self.assertEqual(status, '200 OK')
        self.assertIn('corrigé', proposal['content'])
        current = database.get_report(self.path, self.mission['uuid'], self.draft['uuid'])
        self.assertEqual(current['content'], self.draft['content'])
        self.assertEqual(current['status'], 'draft')
        self.assertEqual(database.list_report_versions(self.path, self.mission['uuid']), [])

    def test_validated_report_cannot_be_sent_for_in_place_correction(self):
        database.validate_report(self.path, self.mission['uuid'], self.draft['uuid'], self.draft['content'], self.draft['updated_at'], 'equipier', 'local_declared')
        with patch.object(hermes_client, 'build_opener') as opener:
            self.assertEqual(self.request(self.payload())[0], '409 Conflict')
            opener.assert_not_called()

    def test_concurrent_change_during_request_discards_proposal(self):
        opener = Mock()
        def changed(*_args, **_kwargs):
            database.save_report(self.path, self.mission['uuid'], 'Autre correction', self.draft['uuid'])
            return self.output()
        opener.open.side_effect = changed
        with patch.object(hermes_client, 'build_opener', return_value=opener):
            self.assertEqual(self.request(self.payload())[0], '409 Conflict')


if __name__ == '__main__':
    unittest.main()
