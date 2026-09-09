"""CLI and graphical application entry points. No AI imports in preparation mode."""
import argparse
import json
from pathlib import Path
from .core import Hub, prepare, device_id


def main():
    parser = argparse.ArgumentParser(description='SMT2 preparation client / Mac AI hub')
    parser.add_argument('--home', type=Path, default=Path.home() / '.smt2')
    sub = parser.add_subparsers(dest='command', required=True)
    gui = sub.add_parser('gui')
    gui.add_argument('role', choices=['prep', 'hub'])
    prep = sub.add_parser('prepare')
    prep.add_argument('audio', type=Path)
    prep.add_argument('--outbox', type=Path, required=True)
    prep.add_argument('--title', required=True)
    prep.add_argument('--dictionary', type=Path)
    ingest = sub.add_parser('ingest')
    ingest.add_argument('bundle', type=Path)
    ingest.add_argument('--model', default='mlx-community/whisper-turbo')
    sub.add_parser('list')
    run = sub.add_parser('run')
    run.add_argument('--limit', type=int, default=1, choices=range(1, 11))
    export = sub.add_parser('export')
    export.add_argument('exchange', type=Path)
    for action in ('retry', 'cancel'):
        sub.add_parser(action).add_argument('job')
    args = parser.parse_args()
    try:
        if args.command == 'gui':
            from .gui import launch
            launch(args.role, args.home)
        elif args.command == 'prepare':
            print(prepare(args.audio, args.outbox, device_id(args.home), args.title,
                          args.dictionary.read_text(encoding='utf-8') if args.dictionary else ''))
        else:
            hub = Hub(args.home)
            if args.command == 'ingest':
                print(hub.ingest(args.bundle, args.model))
            elif args.command == 'list':
                print(json.dumps(hub.jobs(), ensure_ascii=False, indent=2))
            elif args.command == 'run':
                for _ in range(args.limit):
                    job = hub.run_one()
                    if not job:
                        break
                    print(job)
            elif args.command == 'export':
                hub.export(args.exchange)
            else:
                hub.change(args.job, args.command)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        parser.exit(1, f'{type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    main()
