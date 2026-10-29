import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import engine


class EngineTests(unittest.TestCase):
    def test_export_edits_only_text_and_preserves_millisecond_subtitles(self):
        result = engine.Transcript([engine.Segment(1.234, 62.789, 'Olá mundo')], 'pt')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'ação.txt'
            engine.export_transcript(result, path, 'txt', 'Revisado')
            self.assertEqual(path.read_text(encoding='utf-8'), 'Revisado')
            engine.export_transcript(result, path, 'srt', 'Revisado')
            self.assertEqual(path.read_text(encoding='utf-8'), '1\n00:00:01,234 --> 00:01:02,789\nOlá mundo\n\n')
            engine.export_transcript(result, path, 'vtt')
            self.assertIn('00:00:01.234 --> 00:01:02.789\nOlá mundo', path.read_text(encoding='utf-8'))
            with self.assertRaises(ValueError):
                engine.export_transcript(result, path, 'exe')
            self.assertFalse(list(Path(folder).glob('*.part')))

    def test_verified_download_and_tampering(self):
        data = b'model fixture'
        metadata = {'filename': 'model.bin', 'url': 'https://example.org/model', 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'label': 'Fixture'}
        with tempfile.TemporaryDirectory() as folder, patch.dict(engine.MODELS, {'fixture': metadata}):
            manager = engine.ModelManager(Path(folder))
            with patch('engine.urllib.request.urlopen', return_value=io.BytesIO(data)):
                path = manager.ensure('fixture', lambda *a: None, threading.Event())
            self.assertTrue(manager.is_ready('fixture'))
            path.write_bytes(b'broken')
            self.assertFalse(manager.is_ready('fixture'))
            with patch('engine.urllib.request.urlopen', return_value=io.BytesIO(b'wrong')):
                with self.assertRaises(ValueError):
                    manager.ensure('fixture', lambda *a: None, threading.Event())
            self.assertFalse(list(Path(folder).glob('*.part')))

    def test_cancelled_download_has_no_partial_model(self):
        with tempfile.TemporaryDirectory() as folder:
            cancel = threading.Event()
            cancel.set()
            manager = engine.ModelManager(Path(folder))
            with self.assertRaises(engine.Cancelled):
                manager.ensure(next(iter(engine.MODELS)), lambda *a: None, cancel)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_real_cli_json_offsets_and_language(self):
        result = engine.parse_transcript({'result': {'language': 'pt'}, 'transcription': [{'offsets': {'from': 1234, 'to': 5678}, 'text': ' Olá! '}]})
        self.assertEqual(result.text, 'Olá!')
        self.assertEqual(result.segments[0], engine.Segment(1.234, 5.678, 'Olá!'))
        self.assertEqual(result.language, 'pt')
        with self.assertRaises(ValueError):
            engine.parse_transcript({'transcription': [{'offsets': {'from': 500, 'to': 100}, 'text': 'x'}]})

    def test_running_process_can_be_cancelled_without_output(self):
        import sys
        import time
        cancel = threading.Event()
        timer = threading.Timer(.3, cancel.set)
        timer.start()
        start = time.monotonic()
        try:
            with self.assertRaises(engine.Cancelled):
                engine.run_process([sys.executable, '-c', 'import time; time.sleep(30)'], cancel, lambda line: None)
        finally:
            timer.cancel()
        self.assertLess(time.monotonic() - start, 5)


if __name__ == '__main__':
    unittest.main()

class PipelineTests(unittest.TestCase):
    def test_pipeline_uses_real_cli_schema_and_cleans_temporary_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'ffmpeg.exe').touch()
            (root / 'whisper-cli.exe').touch()
            source = root / 'vídeo ação.mp4'
            source.touch()
            calls = []
            events = []
            manager = engine.ModelManager(root)

            def execute(command, cancel, on_line):
                calls.append(command)
                if command[0].endswith('ffmpeg.exe'):
                    Path(command[-1]).write_bytes(b'RIFF')
                else:
                    on_line('whisper_print_progress_callback: progress =  65%')
                    output = Path(command[command.index('-of') + 1]).with_suffix('.json')
                    output.write_text(json.dumps({'result': {'language': 'pt'}, 'transcription': [{'offsets': {'from': 0, 'to': 1000}, 'text': ' Olá mundo.'}]}), encoding='utf-8')

            with patch.object(manager, 'ensure', return_value=root / 'model.bin'), patch('engine.run_process', side_effect=execute):
                result = engine.Transcriber(root, manager).transcribe(source, 'turbo', 'pt', lambda *args: events.append(args), threading.Event())
            self.assertEqual(result.text, 'Olá mundo.')
            self.assertIn(str(source.resolve()), calls[0])
            self.assertIn('-ng', calls[1])
            self.assertIn(('transcribe', .65, 'Transcrevendo localmente…'), events)
            self.assertFalse(Path(calls[0][-1]).exists())

    def test_failed_process_reports_diagnostic(self):
        import sys
        with self.assertRaisesRegex(RuntimeError, 'diagnóstico'):
            engine.run_process([sys.executable, '-c', "import sys; sys.stdout.reconfigure(encoding='utf-8'); print('diagnóstico'); sys.exit(3)"], threading.Event(), lambda line: None)

    def test_atomic_export_preserves_existing_file_on_replace_failure(self):
        result = engine.Transcript([], 'pt')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'original.txt'
            path.write_text('original', encoding='utf-8')
            with patch('engine.os.replace', side_effect=PermissionError('locked')):
                with self.assertRaises(PermissionError):
                    engine.export_transcript(result, path, 'txt', 'alterado')
            self.assertEqual(path.read_text(encoding='utf-8'), 'original')
            self.assertEqual(list(Path(folder).iterdir()), [path])


if __name__ == '__main__':
    unittest.main()
