"""Immutable transport bundles and a local, single-writer durable queue."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time
import uuid
from contextlib import contextmanager
from collections import Counter


def write_json(path: Path, value):
    encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    if len(encoded.encode('utf-8')) > 4_000_000:
        raise ValueError('JSON exceeds 4 MB')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def read_json(path: Path):
    if path.stat().st_size > 4_000_000:
        raise ValueError('JSON exceeds 4 MB')
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path: Path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identifier(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError('Canonical UUID required')
    return value


def device_id(home: Path):
    home.mkdir(parents=True, exist_ok=True)
    path = home / 'device-id'
    try:
        with path.open('x', encoding='ascii') as stream:
            stream.write(str(uuid.uuid4()))
    except FileExistsError:
        pass
    return identifier(path.read_text().strip())


def prepare(audio: Path, outbox: Path, device: str, title: str, dictionary=''):
    identifier(device)
    if audio.suffix.lower() not in ('.mp3', '.wav', '.m4a') or not audio.is_file():
        raise ValueError('Select an existing MP3, WAV, or M4A file')
    if not title.strip() or len(title) > 500:
        raise ValueError('Title must contain 1–500 characters')
    if len(dictionary.encode('utf-8')) > 64_000:
        raise ValueError('Dictionary hint must be at most 64 KB')
    request = str(uuid.uuid4())
    destination = outbox / device
    destination.mkdir(parents=True, exist_ok=True)
    staging = destination / ('.' + request)
    final = destination / request
    staging.mkdir()
    try:
        before = (audio.stat().st_size, audio.stat().st_mtime_ns)
        name = 'audio' + audio.suffix.lower()
        shutil.copyfile(audio, staging / name)
        if before != (audio.stat().st_size, audio.stat().st_mtime_ns) or digest(audio) != digest(staging / name):
            raise ValueError('Audio changed during preparation; retry after collection finishes')
        (staging / 'dictionary.txt').write_text(dictionary, encoding='utf-8')
        write_json(staging / 'request.json', {
            'schema': 1, 'request_id': request, 'device_id': device,
            'title': title.strip(), 'created_at': time.time(),
            'audio': name, 'audio_sha256': digest(staging / name),
            'dictionary_sha256': digest(staging / 'dictionary.txt'),
        })
        staging.rename(final)
        return final
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def validate_bundle(bundle: Path):
    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError('Bundle must be a real directory')
    for name in ('request.json', 'dictionary.txt'):
        if (bundle / name).is_symlink() or not (bundle / name).is_file():
            raise ValueError('Missing or linked bundle member')
    request = read_json(bundle / 'request.json')
    if request.get('schema') != 1:
        raise ValueError('Unsupported schema')
    identifier(request['request_id'])
    identifier(request['device_id'])
    if request['audio'] not in ('audio.mp3', 'audio.wav', 'audio.m4a'):
        raise ValueError('Invalid audio filename')
    if not isinstance(request['title'], str) or not request['title'].strip() or len(request['title']) > 500:
        raise ValueError('Invalid title')
    audio = bundle / request['audio']
    if audio.is_symlink() or not audio.is_file():
        raise ValueError('Missing or linked audio')
    if (bundle / 'dictionary.txt').stat().st_size > 64_000:
        raise ValueError('Dictionary too large')
    (bundle / 'dictionary.txt').read_text(encoding='utf-8')
    for name, expected in ((request['audio'], request['audio_sha256']), ('dictionary.txt', request['dictionary_sha256'])):
        if digest(bundle / name) != expected:
            raise ValueError('Bundle checksum mismatch: ' + name)
    return request


def dictionary_candidates(path: Path):
    if path.suffix.lower() == '.pdf':
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError('PDF extraction requires: pip install -e ".[pdf]"') from exc
        text = '\n'.join(page.extract_text() or '' for page in PdfReader(path).pages)
        if not text.strip():
            raise ValueError('No PDF text. Run OCR externally and import the searchable PDF.')
    else:
        text = path.read_text(encoding='utf-8-sig')
    words = Counter(re.findall(r'[가-힣A-Za-z][가-힣A-Za-z0-9_-]{1,39}', text))
    return '\n'.join(word for word, count in sorted(words.items(), key=lambda item: (-item[1], item[0]))[:200])


@contextmanager
def exclusive(home: Path):
    """All queue mutations, including inference, share one process lock."""
    home.mkdir(parents=True, exist_ok=True)
    with (home / 'hub.lock').open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0)
            stream.write(b'0')
            stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError('Hub is busy') from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError('Hub is busy') from exc
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


class Hub:
    def __init__(self, home: Path):
        self.home = home.resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, device TEXT NOT NULL, title TEXT NOT NULL,
                state TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0,
                error TEXT, model TEXT NOT NULL, created REAL NOT NULL)''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.home / 'queue.sqlite3', timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def jobs(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM jobs ORDER BY created')]

    def ingest(self, bundle: Path, model='mlx-community/whisper-turbo'):
        with exclusive(self.home):
            request = validate_bundle(bundle)
            job = request['request_id']
            target = self.home / 'inputs' / job
            with self.connect() as db:
                existing = db.execute('SELECT id FROM jobs WHERE id=?', (job,)).fetchone()
                if existing:
                    if validate_bundle(target) != request:
                        raise ValueError('Request ID reused with different content')
                    return job
                staging = self.home / 'inputs' / ('.' + job)
                staging.parent.mkdir(parents=True, exist_ok=True)
                if staging.exists():
                    shutil.rmtree(staging)
                staging.mkdir()
                try:
                    for name in ('request.json', 'dictionary.txt', request['audio']):
                        shutil.copyfile(bundle / name, staging / name)
                    if validate_bundle(staging) != request:
                        raise ValueError('Bundle changed during intake')
                    if target.exists():
                        if validate_bundle(target) != request:
                            raise ValueError('Conflicting intake snapshot')
                    else:
                        staging.rename(target)
                    db.execute('INSERT INTO jobs(id,device,title,state,model,created) VALUES(?,?,?,?,?,?)',
                               (job, request['device_id'], request['title'], 'QUEUED', model, time.time()))
                finally:
                    if staging.exists():
                        shutil.rmtree(staging)
            return job

    def change(self, job, action):
        identifier(job)
        with exclusive(self.home), self.connect() as db:
            state = db.execute('SELECT state FROM jobs WHERE id=?', (job,)).fetchone()
            if not state:
                raise ValueError('Unknown job')
            if action == 'retry' and state['state'] in ('FAILED', 'INTERRUPTED'):
                db.execute("UPDATE jobs SET state='QUEUED',error=NULL WHERE id=?", (job,))
            elif action == 'cancel' and state['state'] == 'QUEUED':
                db.execute("UPDATE jobs SET state='CANCELLED' WHERE id=?", (job,))
            else:
                raise ValueError('Action is not allowed in state ' + state['state'])

    def run_one(self, backend=None):
        with exclusive(self.home):
            self._recover()
            with self.connect() as db:
                row = db.execute("SELECT * FROM jobs WHERE state='QUEUED' ORDER BY created LIMIT 1").fetchone()
                if not row:
                    return None
                job = dict(row)
                job['attempt'] += 1
                db.execute("UPDATE jobs SET state='RUNNING',attempt=?,error=NULL WHERE id=?", (job['attempt'], job['id']))
            output = self.home / 'results' / job['id'] / str(job['attempt'])
            try:
                bundle = self.home / 'inputs' / job['id']
                request = validate_bundle(bundle)
                engine = backend or mlx_transcribe
                result = engine(bundle / request['audio'], (bundle / 'dictionary.txt').read_text(encoding='utf-8'), job['model'])
                validate_result(result)
                output.mkdir(parents=True, exist_ok=True)
                write_json(output / 'raw.json', result)
                with (output / 'raw.txt').open('w', encoding='utf-8') as stream:
                    stream.write(result['text'])
                    stream.flush()
                    os.fsync(stream.fileno())
                write_json(output / 'complete.json', {'schema': 1, 'request_id': job['id'],
                    'attempt': job['attempt'], 'model': job['model'],
                    'dictionary_sha256': request['dictionary_sha256'],
                    'raw_json_sha256': digest(output / 'raw.json'), 'raw_txt_sha256': digest(output / 'raw.txt')})
                with self.connect() as db:
                    db.execute("UPDATE jobs SET state='DONE' WHERE id=?", (job['id'],))
            except Exception as exc:
                with self.connect() as db:
                    # No document/audio contents in the queue's diagnostic field.
                    db.execute("UPDATE jobs SET state='FAILED',error=? WHERE id=?", (type(exc).__name__ + ': ' + str(exc)[:500], job['id']))
                raise
            return job['id']

    def _recover(self):
        with self.connect() as db:
            for row in db.execute("SELECT id,attempt FROM jobs WHERE state='RUNNING'").fetchall():
                folder = self.home / 'results' / row['id'] / str(row['attempt'])
                try:
                    marker = read_json(folder / 'complete.json')
                    valid = (marker['request_id'] == row['id'] and marker['attempt'] == row['attempt']
                        and marker['raw_json_sha256'] == digest(folder / 'raw.json')
                        and marker['raw_txt_sha256'] == digest(folder / 'raw.txt'))
                    validate_result(read_json(folder / 'raw.json'))
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
                db.execute('UPDATE jobs SET state=?,error=? WHERE id=?',
                    ('DONE' if valid else 'INTERRUPTED', None if valid else 'Previous process stopped; explicit retry required', row['id']))

    def export(self, exchange: Path):
        """Publish only committed local acknowledgments and verified complete results."""
        with exclusive(self.home):
            self._recover()
            for job in self.jobs():
                destination = exchange / 'receipts' / job['device'] / job['id']
                write_json(destination / 'status.json', {'schema': 1, 'request_id': job['id'],
                    'accepted': True, 'state': job['state'], 'attempt': job['attempt']})
                if job['state'] == 'DONE':
                    source = self.home / 'results' / job['id'] / str(job['attempt'])
                    marker = read_json(source / 'complete.json')
                    for name, key in (('raw.json', 'raw_json_sha256'), ('raw.txt', 'raw_txt_sha256')):
                        if digest(source / name) != marker[key]:
                            raise ValueError('Stored result checksum mismatch')
                    destination = exchange / 'results' / job['device'] / job['id'] / str(job['attempt'])
                    destination.mkdir(parents=True, exist_ok=True)
                    for name in ('raw.json', 'raw.txt'):
                        temp = destination / (name + '.tmp')
                        shutil.copyfile(source / name, temp)
                        os.replace(temp, destination / name)
                    write_json(destination / 'complete.json', marker)


def validate_result(result):
    if not isinstance(result, dict) or not isinstance(result.get('text'), str) or not isinstance(result.get('segments'), list):
        raise ValueError('Invalid transcript structure')
    previous = -1.0
    for segment in result['segments']:
        start, end = segment['start'], segment['end']
        if (not isinstance(start, (int, float)) or not isinstance(end, (int, float))
                or not math.isfinite(start) or not math.isfinite(end)
                or start < 0 or start < previous or end < start or not isinstance(segment['text'], str)):
            raise ValueError('Invalid segment or timestamp')
        previous = start


def mlx_transcribe(audio: Path, dictionary: str, model: str):
    import platform
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise RuntimeError('MLX transcription requires an Apple Silicon Mac')
    if not shutil.which('ffmpeg'):
        raise RuntimeError('FFmpeg is required on the Mac')
    import mlx_whisper
    # Long dictionaries are rejected rather than silently truncated.
    if len(dictionary) > 2000:
        raise ValueError('Reduce dictionary hints to 2000 characters for this preview')
    raw = mlx_whisper.transcribe(str(audio), path_or_hf_repo=model, language='ko',
                               initial_prompt=dictionary or None, verbose=None)
    return {'text': raw['text'], 'language': raw.get('language', 'ko'),
            'segments': [{'start': s['start'], 'end': s['end'], 'text': s['text']} for s in raw['segments']]}
