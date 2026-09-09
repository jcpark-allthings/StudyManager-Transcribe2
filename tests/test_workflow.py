import json
from pathlib import Path
import tempfile
import unittest
import uuid
from smt2.core import Hub, prepare, validate_bundle, validate_result, exclusive, dictionary_candidates


def fake(audio, dictionary, model):
    return {'text': '강의 시험', 'language': 'ko', 'segments': [{'start': 0.0, 'end': 1.2, 'text': '강의 시험'}]}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.audio = self.root / 'lecture.mp3'
        # Deliberately not real audio: fake backend tests transport/state only.
        self.audio.write_bytes(b'test-audio-bytes')
        self.device = str(uuid.uuid4())
        self.exchange = self.root / 'exchange'
        self.bundle = prepare(self.audio, self.exchange / 'outbox', self.device, '테스트 강의', '사용자 사전')
        self.hub = Hub(self.root / 'hub')

    def test_roundtrip_survives_source_removal(self):
        job = self.hub.ingest(self.bundle)
        self.hub.export(self.exchange)
        receipt = self.exchange / 'receipts' / self.device / job / 'status.json'
        self.assertTrue(json.loads(receipt.read_text())['accepted'])
        import shutil
        shutil.rmtree(self.bundle)
        self.audio.unlink()
        self.assertEqual(self.hub.run_one(fake), job)
        self.hub.export(self.exchange)
        result = self.exchange / 'results' / self.device / job / '1'
        self.assertEqual((result / 'raw.txt').read_text(), '강의 시험')
        self.assertTrue((result / 'complete.json').exists())
        self.assertEqual(self.hub.jobs()[0]['state'], 'DONE')

    def test_repeated_intake_is_idempotent(self):
        job = self.hub.ingest(self.bundle)
        self.assertEqual(self.hub.ingest(self.bundle), job)
        self.assertEqual(len(self.hub.jobs()), 1)
        self.hub.run_one(fake)
        self.hub.ingest(self.bundle)
        self.assertIsNone(self.hub.run_one(fake))

    def test_tamper_rejected_without_ack(self):
        (self.bundle / 'audio.mp3').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.hub.ingest(self.bundle)
        self.assertEqual(self.hub.jobs(), [])

    def test_path_escape_rejected(self):
        path = self.bundle / 'request.json'
        request = json.loads(path.read_text())
        request['audio'] = '../../outside.mp3'
        path.write_text(json.dumps(request))
        with self.assertRaisesRegex(ValueError, 'filename'):
            validate_bundle(self.bundle)

    def test_failure_requires_explicit_retry(self):
        job = self.hub.ingest(self.bundle)
        def fail(*args):
            raise RuntimeError('test failure')
        with self.assertRaises(RuntimeError):
            self.hub.run_one(fail)
        self.assertIsNone(self.hub.run_one(fake))
        self.hub.change(job, 'retry')
        self.hub.run_one(fake)
        self.assertEqual(self.hub.jobs()[0]['attempt'], 2)

    def test_interrupted_job_not_automatically_repeated(self):
        job = self.hub.ingest(self.bundle)
        with self.hub.connect() as db:
            db.execute("UPDATE jobs SET state='RUNNING',attempt=1")
        self.assertIsNone(Hub(self.hub.home).run_one(fake))
        self.assertEqual(self.hub.jobs()[0]['state'], 'INTERRUPTED')
        self.hub.change(job, 'retry')
        self.hub.run_one(fake)

    def test_completed_checkpoint_recovers_without_inference(self):
        self.hub.ingest(self.bundle)
        self.hub.run_one(fake)
        with self.hub.connect() as db:
            db.execute("UPDATE jobs SET state='RUNNING'")
        self.assertIsNone(self.hub.run_one(lambda *a: self.fail('must not rerun')))
        self.assertEqual(self.hub.jobs()[0]['state'], 'DONE')

    def test_corrupt_checkpoint_not_recovered(self):
        job = self.hub.ingest(self.bundle)
        self.hub.run_one(fake)
        (self.hub.home / 'results' / job / '1' / 'raw.txt').write_text('changed')
        with self.hub.connect() as db:
            db.execute("UPDATE jobs SET state='RUNNING'")
        self.hub.run_one(fake)
        self.assertEqual(self.hub.jobs()[0]['state'], 'INTERRUPTED')

    def test_queue_cancel_and_done_retry_rejected(self):
        job = self.hub.ingest(self.bundle)
        self.hub.change(job, 'cancel')
        self.assertIsNone(self.hub.run_one(fake))
        with self.assertRaises(ValueError):
            self.hub.change(job, 'retry')

    def test_local_inputs_rechecked(self):
        job = self.hub.ingest(self.bundle)
        (self.hub.home / 'inputs' / job / 'dictionary.txt').write_text('tampered')
        with self.assertRaises(ValueError):
            self.hub.run_one(fake)
        self.assertEqual(self.hub.jobs()[0]['state'], 'FAILED')

    def test_multiple_devices(self):
        self.hub.ingest(self.bundle)
        second = prepare(self.audio, self.exchange / 'outbox', str(uuid.uuid4()), '다른 PC')
        self.hub.ingest(second)
        self.assertEqual(len(self.hub.jobs()), 2)
        self.hub.run_one(fake)
        self.hub.run_one(fake)
        self.hub.export(self.exchange)
        self.assertEqual(len(list((self.exchange / 'receipts').glob('*/*/status.json'))), 2)

    def test_invalid_timestamp(self):
        for start, end in [(float('nan'), 2), (-1, 2), (2, 1), (1, float('inf'))]:
            with self.assertRaises(ValueError):
                validate_result({'text': 'x', 'segments': [{'start': start, 'end': end, 'text': 'x'}]})

    def test_dictionary_extraction_deterministic(self):
        path = self.root / 'material.txt'
        path.write_text('신경망 학습 신경망 Python Python Python', encoding='utf-8')
        self.assertEqual(dictionary_candidates(path).splitlines(), ['Python', '신경망', '학습'])

    def test_reused_id_with_valid_new_content_rejected(self):
        from smt2.core import digest
        self.hub.ingest(self.bundle)
        (self.bundle / 'dictionary.txt').write_text('different dictionary')
        path = self.bundle / 'request.json'
        request = json.loads(path.read_text())
        request['dictionary_sha256'] = digest(self.bundle / 'dictionary.txt')
        path.write_text(json.dumps(request))
        with self.assertRaisesRegex(ValueError, 'reused'):
            self.hub.ingest(self.bundle)

    def test_no_transcription_on_corrupt_backend_output(self):
        self.hub.ingest(self.bundle)
        with self.assertRaises(ValueError):
            self.hub.run_one(lambda *args: {'text': None, 'segments': []})
        self.assertEqual(self.hub.jobs()[0]['state'], 'FAILED')
        self.assertEqual(list(self.hub.home.glob('results/*/*/complete.json')), [])

    def test_done_job_cannot_be_retried(self):
        job = self.hub.ingest(self.bundle)
        self.hub.run_one(fake)
        with self.assertRaises(ValueError):
            self.hub.change(job, 'retry')

    def test_oversize_output_is_not_marked_done(self):
        self.hub.ingest(self.bundle)
        with self.assertRaisesRegex(ValueError, '4 MB'):
            self.hub.run_one(lambda *args: {'text': 'x' * 4_000_001, 'segments': []})
        self.assertEqual(self.hub.jobs()[0]['state'], 'FAILED')

    def test_single_writer_lock(self):
        with exclusive(self.hub.home):
            with self.assertRaises(RuntimeError):
                self.hub.ingest(self.bundle)


if __name__ == '__main__':
    unittest.main()
