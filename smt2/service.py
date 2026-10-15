"""One safe intake, transcription, and export pass for the Mac hub."""
import sys
import time
from pathlib import Path

from .core import Hub


def cycle(hub: Hub, exchange: Path, model='mlx-community/whisper-turbo', backend=None):
    errors = []
    if exchange.is_dir():
        try:
            requests = sorted((exchange / 'outbox').glob('*/*/request.json'))
        except OSError as exc:
            errors.append(f'교환 폴더 검색: {exc}')
            requests = []
        for request in requests:
            if not request.parent.name.startswith('.'):
                try:
                    hub.ingest(request.parent, model)
                except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
                    errors.append(f'{request.parent}: {exc}')
        try:
            hub.export(exchange)  # Acknowledge local ownership before a long transcription.
        except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            errors.append(f'결과 발행: {exc}')
    else:
        errors.append(f'교환 폴더에 접근할 수 없음: {exchange}')

    job = None
    try:
        job = hub.run_one(backend)
    except Exception as exc:
        errors.append(f'전사: {type(exc).__name__}: {exc}')

    if exchange.is_dir():
        try:
            hub.export(exchange)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            errors.append(f'결과 발행: {exc}')
    return job, errors


def serve(home: Path, exchange: Path, model='mlx-community/whisper-turbo', interval=5):
    if interval <= 0:
        raise ValueError('Polling interval must be positive')
    hub = Hub(home)
    previous_errors = set()
    while True:
        job, errors = cycle(hub, exchange, model)
        if job:
            print(f'전사 완료: {job}', flush=True)
        current_errors = set(errors)
        for error in sorted(current_errors - previous_errors):
            print(error, file=sys.stderr, flush=True)
        previous_errors = current_errors
        time.sleep(interval)
