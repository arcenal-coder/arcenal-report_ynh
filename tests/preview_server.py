"""Disposable UI fixture. Never packaged or used as a production entry point.

Emulates a YunoHost admin session and Hermes response on loopback only. Nothing
is sent to a provider. This is UI evidence, not SSO or real Hermes acceptance.
"""
import os
import tempfile
from pathlib import Path
from wsgiref.simple_server import make_server

import app
import database
import hermes_client


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as directory:
        app.DATABASE_PATH = str(Path(directory) / 'preview.sqlite3')
        database.initialise(app.DATABASE_PATH)
        mission_uuid = database.list_missions(app.DATABASE_PATH)[0]['uuid']
        database.add_text_entry(app.DATABASE_PATH, mission_uuid, 'Contrôle à 08:12 : pression mesurée à 4 bar. Zone sécurisée.')
        database.save_report(app.DATABASE_PATH, mission_uuid, 'ONYX — RAPPORT DE FIN DE JOURNÉE\nÉquipier : Équipier de recette\n\nDÉROULÉ\n08:12 — Controle effectué : pression 4 bar. Zone sécurisé.')
        os.environ['ARCENAL_DEPLOYMENT'] = 'yunohost'
        os.environ['ARCENAL_PUBLIC_URL'] = 'https://recette.example.org/arcenal-report'
        hermes_client.allowed = lambda mission, actor: mission == mission_uuid and actor == 'recette'
        hermes_client.propose = lambda report, instruction, actor: {
            'content': report['content'].replace('Controle', 'Contrôle').replace('Zone sécurisé.', 'Zone sécurisée.'),
            'request_id': 'synthetic-ui-check',
        }

        def fixture(environ, start_response):
            environ['HTTP_REMOTE_USER'] = 'recette'
            if not environ['PATH_INFO'].startswith('/mcp'):
                environ.setdefault('HTTP_AUTHORIZATION', 'Basic cmVjZXR0ZTpmYWtl')
            if environ['PATH_INFO'] == '/integrations.html' or environ['PATH_INFO'].startswith('/api/v1/integrations'):
                environ['HTTP_X_REPORT_ADMIN'] = '1'
            else:
                environ.pop('HTTP_X_REPORT_ADMIN', None)
            if environ.get('HTTP_ORIGIN') == 'http://127.0.0.1:8083':
                environ['HTTP_ORIGIN'] = 'https://recette.example.org'
            return app.application(environ, start_response)

        print('Disposable UI fixture: http://127.0.0.1:8083 — synthetic SSO and Hermes, no real user data.', flush=True)
        make_server('127.0.0.1', 8083, fixture).serve_forever()
