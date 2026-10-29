"""Verifica os codecs do FFmpeg realmente distribuído, sem rede ou modelos."""
from pathlib import Path
import tempfile
import threading
import unittest
import wave

from engine import run_process

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = ROOT / 'vendor/runtime/ffmpeg.exe'


@unittest.skipUnless(FFMPEG.is_file(), 'Execute prepare.ps1 para testar o runtime real')
class RuntimeTests(unittest.TestCase):
    def test_compressed_audio_and_video_to_mono_pcm(self):
        with tempfile.TemporaryDirectory() as folder:
            for extension in ('mp3', 'm4a', 'mp4'):
                with self.subTest(format=extension):
                    output = Path(folder) / f'{extension}.wav'
                    source = ROOT / 'tests/fixtures' / f'tone.{extension}'
                    run_process([str(FFMPEG), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                                 '-i', str(source), '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le',
                                 str(output)], threading.Event(), lambda line: None)
                    with wave.open(str(output), 'rb') as audio:
                        self.assertEqual((audio.getnchannels(), audio.getframerate(), audio.getsampwidth()), (1, 16000, 2))
                        self.assertGreater(audio.getnframes(), 14000)
                        self.assertTrue(any(audio.readframes(8000)))
