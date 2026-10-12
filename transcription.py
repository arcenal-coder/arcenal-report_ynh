"""Local audio transcription using whisper.cpp."""

import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import database


EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="arcenal-transcription")
WHISPER_BINARY = os.environ.get("WHISPER_CPP_BINARY", "whisper-cli")
WHISPER_MODEL = os.environ.get("WHISPER_CPP_MODEL", "")
FFMPEG_BINARY = os.environ.get("FFMPEG_BINARY", "ffmpeg")
TIMEOUT_SECONDS = 15 * 60


def queue(database_path, upload_directory, entry_uuid):
    database.update_transcription(database_path, entry_uuid, "queued")
    EXECUTOR.submit(_transcribe, database_path, Path(upload_directory), entry_uuid)


def _transcribe(database_path, upload_directory, entry_uuid):
    entry = database.get_entry(database_path, entry_uuid)
    if not entry:
        return
    if not WHISPER_MODEL or not Path(WHISPER_MODEL).is_file():
        database.update_transcription(database_path, entry_uuid, "unavailable", error="Le modèle local Whisper n’est pas encore installé.")
        return
    source = (upload_directory / entry["file_path"]).resolve()
    if upload_directory.resolve() not in source.parents or not source.is_file():
        database.update_transcription(database_path, entry_uuid, "failed", error="Fichier audio introuvable.")
        return
    database.update_transcription(database_path, entry_uuid, "processing")
    try:
        with tempfile.TemporaryDirectory(prefix="arcenal-whisper-") as temporary_directory:
            temporary_path = Path(temporary_directory)
            wav_path = temporary_path / "audio.wav"
            output_base = temporary_path / "transcript"
            subprocess.run([FFMPEG_BINARY, "-y", "-i", str(source), "-ar", "16000", "-ac", "1", str(wav_path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=TIMEOUT_SECONDS)
            subprocess.run([WHISPER_BINARY, "-m", WHISPER_MODEL, "-f", str(wav_path), "-l", "fr", "-otxt", "-of", str(output_base)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=TIMEOUT_SECONDS)
            transcript = output_base.with_suffix(".txt").read_text(encoding="utf-8").strip()
        if not transcript:
            raise RuntimeError("Aucun texte n’a été détecté dans cet enregistrement.")
        database.update_transcription(database_path, entry_uuid, "completed", transcript=transcript)
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        database.update_transcription(database_path, entry_uuid, "failed", error=str(error)[:500])
