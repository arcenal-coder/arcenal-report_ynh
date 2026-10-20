from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import database
import transcription


class TranscriptionTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.db = self.root / 'test.sqlite3'
        database.initialise(self.db)
        mission = database.list_missions(self.db)[0]['uuid']
        (self.root / 'recording.webm').write_bytes(b'test audio')
        self.model = self.root / 'model.bin'
        self.model.write_bytes(b'test model')
        self.entry = database.add_audio_entry(self.db, mission, 'note.webm', 'recording.webm', 'audio/webm')
        self.model_patch = patch.object(transcription, 'WHISPER_MODEL', str(self.model))
        self.model_patch.start()

    def tearDown(self):
        self.model_patch.stop()
        self.directory.cleanup()

    def result(self):
        return database.get_entry(self.db, self.entry['uuid'])

    def test_non_executable_whisper_is_reported_before_conversion(self):
        executable = self.root / 'whisper-cli'
        executable.write_text('not executable', encoding='utf-8')
        executable.chmod(0o640)
        with patch.object(transcription, 'WHISPER_BINARY', str(executable)), patch('transcription.subprocess.run') as run:
            transcription._transcribe(self.db, self.root, self.entry['uuid'])
        run.assert_not_called()
        self.assertEqual(self.result()['transcription_status'], 'unavailable')
        self.assertIn('Whisper est absent ou non exécutable', self.result()['transcription_error'])

    def test_success_persists_text_from_whisper_output(self):
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            if '-of' in command:
                Path(command[command.index('-of') + 1]).with_suffix('.txt').write_text('Contrôle terminé.', encoding='utf-8')
        with patch('transcription.shutil.which', return_value='/test/executable'), patch('transcription.subprocess.run', side_effect=run):
            transcription._transcribe(self.db, self.root, self.entry['uuid'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.result()['transcript'], 'Contrôle terminé.')
        self.assertEqual(self.result()['transcription_status'], 'completed')
        self.assertIn('16000', calls[0])
        self.assertIn('fr', calls[1])

    def test_conversion_failure_records_tool_diagnostic(self):
        failure = subprocess.CalledProcessError(1, ['ffmpeg'], stderr=b'Invalid data found when processing input')
        with patch('transcription.shutil.which', return_value='/test/executable'), patch('transcription.subprocess.run', side_effect=failure):
            transcription._transcribe(self.db, self.root, self.entry['uuid'])
        self.assertEqual(self.result()['transcription_status'], 'failed')
        self.assertIn('FFmpeg', self.result()['transcription_error'])
        self.assertIn('Invalid data', self.result()['transcription_error'])

    def test_missing_model_is_actionable(self):
        self.model.unlink()
        transcription._transcribe(self.db, self.root, self.entry['uuid'])
        self.assertEqual(self.result()['transcription_status'], 'unavailable')
        self.assertIn('modèle', self.result()['transcription_error'])


class RuntimePermissionsTest(unittest.TestCase):
    def test_package_assigns_binary_to_service_account(self):
        """Exercise the real permission helper with chown recorded, no root needed."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = root / 'install'
            data = root / 'data'
            for path in (install / 'web', install / 'backend', install / 'bin', data / 'uploads', data / 'models'):
                path.mkdir(parents=True, exist_ok=True)
            binary = install / 'bin/whisper-cli'
            binary.write_bytes(b'whisper')
            helper = Path(__file__).resolve().parents[1] / 'scripts/_common.sh'
            command = 'source "$1"; chown() { printf "%s\\n" "$*"; }; install_dir="$2"; data_dir="$3"; set_runtime_permissions'
            result = subprocess.run(['bash', '-eu', '-c', command, 'test', str(helper), str(install), str(data)], capture_output=True, text=True, check=True)
            self.assertIn(f'-R arcenal_report:arcenal_report {install}/bin', result.stdout)
            self.assertEqual(binary.stat().st_mode & 0o777, 0o750)
            self.assertEqual((install / 'bin').stat().st_mode & 0o777, 0o750)
