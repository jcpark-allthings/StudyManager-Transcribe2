from pathlib import Path
import shutil
import tempfile
import unittest
import uuid

from smt2.core import Hub, prepare
from smt2.service import cycle


def fake(*_):
    return {'text': '강의 시험', 'language': 'ko',
            'segments': [{'start': 0.0, 'end': 1.0, 'text': '강의 시험'}]}


class ServiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.exchange = self.root / 'exchange'
        self.exchange.mkdir()
        self.hub = Hub(self.root / 'hub')
        self.audio = self.root / '강의.mp3'
        self.audio.write_bytes(b'fake audio for transport only')
        self.device = str(uuid.uuid4())

    def submit(self):
        return prepare(self.audio, self.exchange / 'outbox', self.device, '강의', '')

    def test_invalid_bundle_does_not_block_valid_transcription(self):
        bad = self.submit()
        (bad / 'audio.mp3').write_bytes(b'corrupted')
        good = self.submit()
        job, errors = cycle(self.hub, self.exchange, backend=fake)
        self.assertEqual(job, good.name)
        self.assertTrue(any('checksum' in error for error in errors))
        self.assertTrue((self.exchange / 'results' / self.device / job / '1' / 'complete.json').exists())

    def test_local_job_finishes_during_exchange_outage_and_exports_later(self):
        bundle = self.submit()
        self.hub.ingest(bundle)
        shutil.rmtree(self.exchange)
        job, errors = cycle(self.hub, self.exchange, backend=fake)
        self.assertEqual(job, bundle.name)
        self.assertTrue(any('교환 폴더' in error for error in errors))
        self.exchange.mkdir()
        self.assertIsNone(cycle(self.hub, self.exchange, backend=fake)[0])
        self.assertTrue((self.exchange / 'results' / self.device / job / '1' / 'complete.json').exists())

    def test_unchanged_export_does_not_rewrite_shared_files(self):
        bundle = self.submit()
        job, errors = cycle(self.hub, self.exchange, backend=fake)
        self.assertEqual(job, bundle.name)
        self.assertFalse(errors)
        receipt = self.exchange / 'receipts' / self.device / job / 'status.json'
        result = self.exchange / 'results' / self.device / job / '1' / 'complete.json'
        before = (receipt.stat().st_mtime_ns, result.stat().st_mtime_ns)
        cycle(self.hub, self.exchange, backend=fake)
        self.assertEqual(before, (receipt.stat().st_mtime_ns, result.stat().st_mtime_ns))


if __name__ == '__main__':
    unittest.main()
