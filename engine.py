"""Motor local de transcrição; somente modelos são baixados da internet."""
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import urllib.request

_REVISION = '5359861c739e955e79d9a303bcbc70fb988958b1'
MODELS = {
    'turbo': {'label': 'Rápido — large-v3-turbo', 'filename': 'ggml-large-v3-turbo-q5_0.bin', 'size': 574041195, 'sha256': '394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2'},
    'quality': {'label': 'Máxima qualidade — large-v3', 'filename': 'ggml-large-v3-q5_0.bin', 'size': 1081140203, 'sha256': 'd75795ecff3f83b5faa89d1900604ad8c780abd5739fae406de19f23ecd98ad1'},
}
for _model in MODELS.values():
    _model['url'] = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/{_REVISION}/{_model['filename']}"


class Cancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel.is_set():
        raise Cancelled('Operação cancelada.')


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    segments: list[Segment]
    language: str

    @property
    def text(self):
        return '\n'.join(segment.text for segment in self.segments)


class ModelManager:
    def __init__(self, root: Path):
        self.root = Path(root)
        self._verified = {}

    def is_ready(self, key):
        model = MODELS[key]
        path = self.root / model['filename']
        if not path.is_file() or path.stat().st_size != model['size']:
            return False
        stamp = (path.stat().st_size, path.stat().st_mtime_ns)
        if self._verified.get(key) == stamp:
            return True
        with path.open('rb') as stream:
            valid = hashlib.file_digest(stream, 'sha256').hexdigest() == model['sha256']
        if valid:
            self._verified[key] = stamp
        return valid

    def ensure(self, key, callback, cancel):
        check_cancel(cancel)
        model = MODELS[key]
        callback('model', None, 'Verificando modelo local…')
        if self.is_ready(key):
            return self.root / model['filename']
        self.root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(self.root).free < model['size'] + 100 * 1024 * 1024:
            raise OSError('Espaço insuficiente para baixar o modelo. Libere espaço no disco.')
        path = self.root / model['filename']
        partial = path.with_suffix('.bin.part')
        digest = hashlib.sha256()
        received = 0
        try:
            request = urllib.request.Request(model['url'], headers={'User-Agent': 'TranscreveLocal/1.0'})
            with urllib.request.urlopen(request, timeout=15) as response, partial.open('wb') as stream:
                while True:
                    check_cancel(cancel)
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > model['size']:
                        raise ValueError('Download maior que o modelo esperado.')
                    digest.update(chunk)
                    stream.write(chunk)
                    callback('download', received / model['size'], f'Baixando modelo: {received / 1048576:.0f} de {model["size"] / 1048576:.0f} MB')
            check_cancel(cancel)
            if received != model['size'] or digest.hexdigest() != model['sha256']:
                raise ValueError('Modelo incompleto ou corrompido. Tente baixar novamente.')
            os.replace(partial, path)
            stat = path.stat()
            self._verified[key] = (stat.st_size, stat.st_mtime_ns)
            return path
        finally:
            partial.unlink(missing_ok=True)


def run_process(command, cancel, on_line):
    check_cancel(cancel)
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, encoding='utf-8', errors='replace', **options)
    lines = queue.Queue()

    def read():
        try:
            for line in process.stdout:
                lines.put(line.rstrip())
        finally:
            lines.put(None)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    tail = []
    try:
        finished = False
        while not finished:
            check_cancel(cancel)
            try:
                line = lines.get(timeout=.1)
            except queue.Empty:
                continue
            if line is None:
                finished = True
            else:
                tail.append(line)
                tail = tail[-30:]
                on_line(line)
        code = process.wait()
        check_cancel(cancel)
        if code:
            raise RuntimeError(f'O processamento falhou (código {code}).\n' + '\n'.join(tail)[-4000:])
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        reader.join(timeout=2)
        process.stdout.close()


def parse_transcript(data):
    try:
        segments = []
        for row in data['transcription']:
            start = row['offsets']['from'] / 1000
            end = row['offsets']['to'] / 1000
            if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start:
                raise ValueError('Tempos inválidos no resultado da transcrição.')
            segments.append(Segment(start, end, row['text'].strip()))
        return Transcript(segments, data.get('result', {}).get('language', 'auto'))
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('O motor retornou uma transcrição inválida.') from error


class Transcriber:
    def __init__(self, runtime: Path, models: ModelManager):
        self.runtime = Path(runtime)
        self.models = models

    def transcribe(self, source: Path, model_key: str, language: str, callback, cancel):
        source = Path(source).resolve()
        if not source.is_file():
            raise ValueError('Selecione um arquivo de vídeo ou áudio existente.')
        if language not in ('pt', 'auto', 'en', 'es'):
            raise ValueError('Idioma não suportado.')
        ffmpeg = self.runtime / 'ffmpeg.exe'
        whisper = self.runtime / 'whisper-cli.exe'
        if not ffmpeg.is_file() or not whisper.is_file():
            raise FileNotFoundError('Motor local incompleto. Extraia novamente a pasta inteira do aplicativo.')
        model = self.models.ensure(model_key, callback, cancel)
        with tempfile.TemporaryDirectory(prefix='transcreve-') as folder:
            wav = Path(folder) / 'audio.wav'
            output = Path(folder) / 'resultado'
            callback('convert', None, 'Preparando áudio local…')
            run_process([str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source), '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(wav)], cancel, lambda line: None)
            callback('transcribe', None, 'Carregando modelo e transcrevendo no PC…')

            def progress(line):
                match = re.search(r'progress\s*=\s*(\d+)%', line)
                if match:
                    callback('transcribe', min(int(match.group(1)), 100) / 100, 'Transcrevendo localmente…')

            run_process([str(whisper), '-m', str(model), '-f', str(wav), '-l', language, '-ng', '-t', str(max(1, min(8, (os.cpu_count() or 2) - 1))), '--output-json', '--output-txt', '--output-srt', '--output-vtt', '--print-progress', '-of', str(output)], cancel, progress)
            check_cancel(cancel)
            result = parse_transcript(json.loads(output.with_suffix('.json').read_text(encoding='utf-8-sig')))
            callback('done', 1.0, 'Transcrição concluída.' if result.segments else 'Nenhuma fala detectada.')
            return result


def _timestamp(seconds, separator):
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02}{separator}{milliseconds:03}'


def export_transcript(transcript, path: Path, format: str, edited_text=None):
    if format == 'txt':
        content = transcript.text if edited_text is None else edited_text
    elif format in ('srt', 'vtt'):
        separator = ',' if format == 'srt' else '.'
        blocks = []
        for index, segment in enumerate(transcript.segments, 1):
            prefix = f'{index}\n' if format == 'srt' else ''
            blocks.append(f'{prefix}{_timestamp(segment.start, separator)} --> {_timestamp(segment.end, separator)}\n{segment.text}\n\n')
        content = ('WEBVTT\n\n' if format == 'vtt' else '') + ''.join(blocks)
    else:
        raise ValueError('Formato de exportação inválido.')
    path = Path(path)
    handle, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.part', dir=path.parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
