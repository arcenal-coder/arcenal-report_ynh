import cgi
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4
from wsgiref.simple_server import make_server

import database
import transcription
import ai_reporting
import report_document
import weather
import integration_http
import hermes_client


ROOT = Path(__file__).parent
DATABASE_PATH = os.environ.get("MAIN_COURANTE_DB", str(ROOT / "data" / "main-courante.sqlite3"))
STATIC_DIRECTORY = ROOT / 'static' if (ROOT / 'static').is_dir() else ROOT.parent / 'web'
UPLOAD_DIRECTORY = Path(os.environ.get("MAIN_COURANTE_UPLOADS", str(ROOT / "data" / "uploads")))
MAX_PHOTO_SIZE = 10 * 1024 * 1024
MAX_AUDIO_SIZE = 25 * 1024 * 1024


def json_response(start_response, status, body):
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    start_response(status, [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(payload))), ('Cache-Control', 'no-store')])
    return [payload]


def read_json(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    if length > 100_000:
        return None
    try:
        return json.loads(environ["wsgi.input"].read(length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def detect_image_type(content):
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def detect_audio_type(content):
    if content.startswith(b"\x1aE\xdf\xa3"):
        return "audio/webm", ".webm"
    if content.startswith(b"OggS"):
        return "audio/ogg", ".ogg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        return "audio/wav", ".wav"
    if len(content) >= 12 and content[4:8] == b"ftyp":
        return "audio/mp4", ".m4a"
    if content.startswith(b"ID3") or content.startswith((b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        return "audio/mpeg", ".mp3"
    return None


def read_media_form(environ, field_name, max_size, detect_type, label):
    try:
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return None, "Requête invalide.", "400 Bad Request"
    if content_length > max_size + 100_000:
        return None, f"Le fichier {label} dépasse la taille autorisée.", "413 Payload Too Large"
    form = cgi.FieldStorage(fp=environ["wsgi.input"], environ=environ, keep_blank_values=True)
    if field_name not in form:
        return None, f"Le fichier {label} est obligatoire.", "400 Bad Request"
    uploaded_file = form[field_name]
    if isinstance(uploaded_file, list) or not uploaded_file.filename:
        return None, f"Formulaire {label} invalide.", "400 Bad Request"
    content = uploaded_file.file.read(max_size + 1)
    if not content or len(content) > max_size:
        return None, f"Le fichier {label} est vide ou trop volumineux.", "400 Bad Request"
    media_type = detect_type(content)
    if not media_type:
        return None, f"Le format du fichier {label} n’est pas accepté.", "400 Bad Request"
    original_name = Path(uploaded_file.filename).name.strip()[:200] or label
    return {"content": content, "original_name": original_name, "mime_type": media_type[0], "extension": media_type[1]}, None, None


def read_photo_form(environ):
    return read_media_form(environ, "photo", MAX_PHOTO_SIZE, detect_image_type, "photo")


def read_audio_form(environ):
    return read_media_form(environ, "audio", MAX_AUDIO_SIZE, detect_audio_type, "audio")


def save_media(mission_uuid, media, entry_type):
    relative_path = Path(mission_uuid) / f"{uuid4()}{media['extension']}"
    absolute_path = UPLOAD_DIRECTORY / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(media["content"])
    try:
        add_entry = database.add_photo_entry if entry_type == "photo" else database.add_audio_entry
        entry = add_entry(DATABASE_PATH, mission_uuid, media["original_name"], str(relative_path), media["mime_type"])
        if entry_type == "audio":
            transcription.queue(DATABASE_PATH, UPLOAD_DIRECTORY, entry["uuid"])
        return entry
    except Exception:
        absolute_path.unlink(missing_ok=True)
        raise


def file_response(start_response, entry):
    file_path = (UPLOAD_DIRECTORY / entry["file_path"]).resolve()
    upload_root = UPLOAD_DIRECTORY.resolve()
    if upload_root not in file_path.parents or not file_path.is_file():
        return json_response(start_response, "404 Not Found", {"error": "Fichier introuvable."})
    content = file_path.read_bytes()
    headers = [
        ("Content-Type", entry["mime_type"]),
        ("Content-Length", str(len(content))),
        ("Content-Disposition", "inline"),
        ("X-Content-Type-Options", "nosniff"),
        ("Cache-Control", "no-store"),
    ]
    start_response("200 OK", headers)
    return [content]


def api(environ, start_response, path):
    segments = path.strip("/").split("/")
    method = environ["REQUEST_METHOD"]
    if segments == ["api", "v1", "missions"] and method == "GET":
        return json_response(start_response, "200 OK", {"missions": database.list_missions(DATABASE_PATH)})
    if len(segments) == 4 and segments[:3] == ["api", "v1", "missions"] and method == "GET":
        mission = database.get_mission(DATABASE_PATH, segments[3])
        return json_response(start_response, "200 OK", mission) if mission else json_response(start_response, "404 Not Found", {"error": "Mission introuvable."})
    if len(segments) == 5 and segments[:3] == ["api", "v1", "missions"] and segments[4] == "entries":
        mission_uuid = segments[3]
        if not database.get_mission(DATABASE_PATH, mission_uuid):
            return json_response(start_response, "404 Not Found", {"error": "Mission introuvable."})
        if method == "GET":
            return json_response(start_response, "200 OK", {"entries": database.list_entries(DATABASE_PATH, mission_uuid)})
        if method == "POST":
            payload = read_json(environ)
            raw_content = payload.get('content') if isinstance(payload, dict) else None
            content = raw_content.strip() if isinstance(raw_content, str) else ''
            if not content or len(content) > 2_000:
                return json_response(start_response, "400 Bad Request", {"error": "La note doit contenir entre 1 et 2000 caractères."})
            return json_response(start_response, "201 Created", database.add_text_entry(DATABASE_PATH, mission_uuid, content))
    if len(segments) == 5 and segments[:3] == ["api", "v1", "missions"] and segments[4] == "photos" and method == "POST":
        mission_uuid = segments[3]
        if not database.get_mission(DATABASE_PATH, mission_uuid):
            return json_response(start_response, "404 Not Found", {"error": "Mission introuvable."})
        photo, error, status = read_photo_form(environ)
        if error:
            return json_response(start_response, status, {"error": error})
        return json_response(start_response, "201 Created", save_media(mission_uuid, photo, "photo"))
    if len(segments) == 5 and segments[:3] == ["api", "v1", "missions"] and segments[4] == "audio" and method == "POST":
        mission_uuid = segments[3]
        if not database.get_mission(DATABASE_PATH, mission_uuid):
            return json_response(start_response, "404 Not Found", {"error": "Mission introuvable."})
        audio, error, status = read_audio_form(environ)
        if error:
            return json_response(start_response, status, {"error": error})
        return json_response(start_response, "201 Created", save_media(mission_uuid, audio, "audio"))
    if len(segments) == 5 and segments[:3] == ["api", "v1", "missions"] and segments[4] == "report":
        mission_uuid = segments[3]
        mission = database.get_mission(DATABASE_PATH, mission_uuid)
        if not mission:
            return json_response(start_response, "404 Not Found", {"error": "Mission introuvable."})
        if method == "GET":
            report = database.get_latest_report(DATABASE_PATH, mission_uuid)
            return json_response(start_response, "200 OK", {"report": report})
        if method == "POST":
            payload = read_json(environ)
            author = (environ.get('HTTP_REMOTE_USER') or environ.get('HTTP_AUTH_USER') or (payload.get('author', '') if isinstance(payload, dict) else ''))
            if not isinstance(author, str) or len(author.strip()) > 120:
                return json_response(start_response, '400 Bad Request', {'error': 'Nom d’équipier invalide.'})
            content = ai_reporting.fallback_report(mission, ai_reporting.collect_facts(mission, database.list_entries(DATABASE_PATH, mission_uuid)), author.strip())
            location = payload.get('location') if isinstance(payload, dict) else None
            if location is not None:
                try:
                    snapshot = weather.fetch_forecast(location)
                    content += '\n\n' + '\n'.join(weather.report_lines(snapshot))
                except (ValueError, OSError, KeyError, IndexError, TypeError):
                    content += '\n\nMÉTÉO LOCALE\nPrévisions indisponibles lors de la génération. Aucune évaluation du vent, de la pluie ou des orages n’a pu être effectuée.'
            else:
                content += '\n\nMÉTÉO LOCALE\nLocalisation refusée ou indisponible. Les conditions météo n’ont pas pu être récupérées.'
            generation_mode = 'Brouillon éditable'
            report = database.save_report(DATABASE_PATH, mission_uuid, content)
            report["generation_mode"] = generation_mode
            return json_response(start_response, "201 Created", report)
        if method == "PUT":
            payload = read_json(environ)
            raw_content = payload.get('content') if isinstance(payload, dict) else None
            content = raw_content.strip() if isinstance(raw_content, str) else ''
            report_uuid = payload.get("uuid") if isinstance(payload, dict) else None
            if report_uuid is not None and not isinstance(report_uuid, str):
                return json_response(start_response, '400 Bad Request', {'error': 'Identifiant de rapport invalide.'})
            if not content or len(content) > 20_000:
                return json_response(start_response, "400 Bad Request", {"error": "Le rapport doit contenir entre 1 et 20 000 caractères."})
            try:
                report = database.save_report(DATABASE_PATH, mission_uuid, content, report_uuid, payload.get('expected_updated_at'))
            except database.ReportConflict as error:
                return json_response(start_response, '409 Conflict', {'error': str(error)})
            return json_response(start_response, "200 OK", report)
    if len(segments) >= 6 and segments[:3] == ['api', 'v1', 'missions'] and segments[4] == 'report':
        mission_uuid = segments[3]
        if not database.get_mission(DATABASE_PATH, mission_uuid):
            return json_response(start_response, '404 Not Found', {'error': 'Mission introuvable.'})
        if segments[5:] == ['assist']:
            actor = environ.get('HTTP_REMOTE_USER', '')
            if method == 'GET':
                return integration_http.respond(start_response, '200 OK', {'available': hermes_client.allowed(mission_uuid, actor)})
            if method == 'POST':
                try:
                    integration_http.check_origin(environ, required=True)
                    payload = integration_http.body_json(environ)
                    if not isinstance(payload, dict) or payload.get('confirmed') is not True:
                        return json_response(start_response, '400 Bad Request', {'error': 'Confirmez l’envoi du brouillon et de la demande à Hermes.'})
                    if not hermes_client.allowed(mission_uuid, actor):
                        return json_response(start_response, '403 Forbidden', {'error': 'Connexion Hermes non configurée ou mission non autorisée.'})
                    instruction = payload.get('instruction')
                    report_uuid = payload.get('uuid')
                    if not isinstance(instruction, str) or not 1 <= len(instruction.strip()) <= 2_000 or not isinstance(report_uuid, str):
                        return json_response(start_response, '400 Bad Request', {'error': 'Brouillon et demande de correction (2000 caractères maximum) obligatoires.'})
                    report = database.get_report(DATABASE_PATH, mission_uuid, report_uuid)
                    if not report or report['status'] != 'draft' or payload.get('expected_updated_at') != report['updated_at']:
                        return json_response(start_response, '409 Conflict', {'error': 'Brouillon absent, modifié ou déjà validé. Rechargez-le.'})
                    proposal = hermes_client.propose(report, instruction.strip(), actor)
                    current = database.get_report(DATABASE_PATH, mission_uuid, report_uuid)
                    if not current or current['status'] != 'draft' or current['updated_at'] != report['updated_at']:
                        return json_response(start_response, '409 Conflict', {'error': 'Le brouillon a changé pendant la correction. Aucune proposition appliquée.'})
                    return integration_http.respond(start_response, '200 OK', proposal | {'uuid': report_uuid, 'expected_updated_at': report['updated_at']})
                except integration_http.service.AccessError as error:
                    return integration_http.respond(start_response, error.status, {'error': str(error)})
                except hermes_client.HermesUnavailable as error:
                    return integration_http.respond(start_response, '503 Service Unavailable', {'error': str(error)})
        if segments[5:] == ['versions'] and method == 'GET':
            return json_response(start_response, '200 OK', {'versions': database.list_report_versions(DATABASE_PATH, mission_uuid)})
        if len(segments) == 7 and segments[5] == 'versions' and method == 'GET':
            version = database.get_report_version(DATABASE_PATH, mission_uuid, segments[6])
            if not version:
                return json_response(start_response, '404 Not Found', {'error': 'Version introuvable.'})
            # Source snapshots stay server-side, not in browser history/URLs.
            return json_response(start_response, '200 OK', {key: value for key, value in version.items() if key not in ('sources_json', 'mission_json')})
        if len(segments) == 8 and segments[5] == 'versions' and segments[7] == 'docx' and method == 'GET':
            version = database.get_report_version(DATABASE_PATH, mission_uuid, segments[6])
            if not version:
                return json_response(start_response, '404 Not Found', {'error': 'Version introuvable.'})
            try:
                content = report_document.build_docx(json.loads(version['mission_json']), version,
                    json.loads(version['sources_json']), UPLOAD_DIRECTORY)
            except ImportError:
                return json_response(start_response, '503 Service Unavailable', {'error': 'Le module python-docx est nécessaire.'})
            start_response('200 OK', [('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
                ('Content-Length', str(len(content))), ('Content-Disposition', f'attachment; filename="rapport-onyx-v{version["version"]}.docx"'), ('Cache-Control', 'no-store')])
            return [content]
        if segments[5:] == ['validate'] and method == 'POST':
            payload = read_json(environ)
            if not isinstance(payload, dict) or payload.get('confirmed') is not True:
                return json_response(start_response, '400 Bad Request', {'error': 'La confirmation explicite de validation est obligatoire.'})
            sso_actor = environ.get('HTTP_REMOTE_USER') or environ.get('HTTP_AUTH_USER')
            actor = sso_actor or payload.get('author')
            content = payload.get('content')
            if not isinstance(actor, str) or not 1 <= len(actor.strip()) <= 120:
                return json_response(start_response, '400 Bad Request', {'error': 'Le nom du validateur est obligatoire.'})
            if not isinstance(content, str) or not 1 <= len(content.strip()) <= 20_000 or not isinstance(payload.get('uuid'), str) or not isinstance(payload.get('expected_updated_at'), str):
                return json_response(start_response, '400 Bad Request', {'error': 'Brouillon et version de relecture obligatoires.'})
            try:
                report = database.validate_report(DATABASE_PATH, mission_uuid, payload['uuid'], content,
                    payload['expected_updated_at'], actor.strip(), 'sso' if sso_actor else 'local_declared')
            except database.ReportConflict as error:
                return json_response(start_response, '409 Conflict', {'error': str(error)})
            return json_response(start_response, '201 Created', report)
        if len(segments) == 8 and segments[5] == 'versions' and segments[7] == 'reopen' and method == 'POST':
            payload = read_json(environ)
            reason = payload.get('reason') if isinstance(payload, dict) else None
            if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500 or payload.get('confirmed') is not True:
                return json_response(start_response, '400 Bad Request', {'error': 'Confirmez la création de copie et indiquez le motif de reprise (500 caractères maximum).'})
            try:
                report = database.reopen_report_version(DATABASE_PATH, mission_uuid, segments[6], reason.strip())
            except database.ReportConflict as error:
                return json_response(start_response, '409 Conflict', {'error': str(error)})
            return json_response(start_response, '201 Created', report)
    if segments[:3] == ['api', 'v1', 'missions'] and method == 'GET' and (
            len(segments) == 6 and segments[4:] == ['report', 'docx']
            or len(segments) == 7 and segments[4] == 'report' and segments[6] == 'docx'):
        mission = database.get_mission(DATABASE_PATH, segments[3])
        report = (database.get_report(DATABASE_PATH, segments[3], segments[5]) if len(segments) == 7
                  else database.get_latest_report(DATABASE_PATH, segments[3])) if mission else None
        if not report:
            return json_response(start_response, '404 Not Found', {'error': 'Générez et enregistrez le rapport avant de le télécharger.'})
        try:
            content = report_document.build_docx(mission, report, database.list_entries(DATABASE_PATH, segments[3]), UPLOAD_DIRECTORY)
        except ImportError:
            return json_response(start_response, '503 Service Unavailable', {'error': 'Le module python-docx doit être installé pour exporter le rapport Word.'})
        start_response('200 OK', [('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'), ('Content-Length', str(len(content))), ('Content-Disposition', 'attachment; filename="rapport-onyx.docx"'), ('Cache-Control', 'no-store')])
        return [content]
    if len(segments) == 5 and segments[:3] == ["api", "v1", "entries"] and segments[4] == "file" and method == "GET":
        entry = database.get_entry(DATABASE_PATH, segments[3])
        if not entry or entry["entry_type"] not in ("photo", "audio"):
            return json_response(start_response, "404 Not Found", {"error": "Fichier introuvable."})
        return file_response(start_response, entry)
    if len(segments) == 5 and segments[:3] == ["api", "v1", "entries"] and segments[4] == "transcribe" and method == "POST":
        entry = database.get_entry(DATABASE_PATH, segments[3])
        if not entry or entry["entry_type"] != "audio":
            return json_response(start_response, "404 Not Found", {"error": "Note vocale introuvable."})
        transcription.queue(DATABASE_PATH, UPLOAD_DIRECTORY, entry["uuid"])
        return json_response(start_response, "202 Accepted", {"status": "queued"})
    return json_response(start_response, "404 Not Found", {"error": "Ressource introuvable."})


def application(environ, start_response):
    path = urlparse(environ.get("PATH_INFO", "/")).path
    if path == '/mcp' or path.startswith('/api/integrations/v1/') or path == '/api/integrations/v1' or path == '/api/v1/integrations' or path.startswith('/api/v1/integrations/'):
        return integration_http.handle(environ, start_response, DATABASE_PATH, path)
    # Machine credentials must never fall through to the browser's writable API.
    if environ.get('HTTP_AUTHORIZATION') and path.startswith('/api/'):
        return integration_http.respond(start_response, '403 Forbidden', {'error': 'Ce jeton est réservé aux routes machine en lecture seule.'})
    if path == '/integrations.html':
        try:
            integration_http.admin_identity(environ)
        except integration_http.service.AccessError as error:
            return integration_http.respond(start_response, error.status, {'error': str(error)})
    if path.startswith("/api/"):
        if os.environ.get('ARCENAL_DEPLOYMENT') == 'yunohost':
            if not environ.get('HTTP_REMOTE_USER'):
                return integration_http.respond(start_response, '401 Unauthorized', {'error': 'Session YunoHost requise.'})
            if environ.get('REQUEST_METHOD') not in ('GET', 'HEAD'):
                try:
                    integration_http.check_origin(environ, required=True)
                except integration_http.service.AccessError as error:
                    return integration_http.respond(start_response, error.status, {'error': str(error)})
        return api(environ, start_response, path)
    if path == "/":
        path = "/index.html"
    file_path = (STATIC_DIRECTORY / path.lstrip("/")).resolve()
    if STATIC_DIRECTORY not in file_path.parents or not file_path.is_file():
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Not found"]
    content = file_path.read_bytes()
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    start_response("200 OK", [("Content-Type", f"{content_type}; charset=utf-8"), ("Content-Length", str(len(content)))])
    return [content]


if __name__ == "__main__":
    database.initialise(DATABASE_PATH)
    port = int(os.environ.get('ARCENAL_PORT', '8080'))
    print(f"ARCenal REPORT disponible sur http://127.0.0.1:{port}", flush=True)
    make_server("127.0.0.1", port, application).serve_forever()
