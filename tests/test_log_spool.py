"""Verify the persistent stream preserves privacy and correlates distinct events."""
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from flask import g
from calendar_helper_ai import create_app
from calendar_helper_ai.observability import log_event


class SpoolTests(unittest.TestCase):


    def test_allowlist_event_identity_and_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            with patch.dict('os.environ', {'APP_LOG_FILE': str(path)}):
                app = create_app({'TESTING': True, 'OPENAI_API_KEY': None})
                handler = next(h for h in app.logger.handlers if hasattr(h, 'doRollover'))
                with app.app_context():
                    g.request_id = 'same-request'
                    log_event('provider_failed', logging.ERROR, error_type='timeout',
                              prompt='PRIVATE_INPUT', secret='PRIVATE_SECRET')
                    handler.doRollover()
                    log_event('request_finished', status=504)
                handler.close()
                records = [json.loads(line) for file in Path(directory).glob('events.jsonl*')
                           for line in file.read_text().splitlines()]
                self.assertEqual(len(records), 3)
                self.assertEqual(len({r['event_id'] for r in records}), 3)
                self.assertTrue(all(r['schema_version'] == 1 for r in records))
                self.assertEqual(sum(r['request_id'] == 'same-request' for r in records), 2)
                self.assertNotIn('PRIVATE_', json.dumps(records))
