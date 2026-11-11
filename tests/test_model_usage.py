"""Model selection and numeric usage accounting without private provider data."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI

from calendar_helper_ai import create_app
from calendar_helper_ai.config import environment_config

MARKER = 'PRIVATE_CONFIGURATION_OR_PROVIDER_DATA'
EVENT = {'title': MARKER, 'date': '2026-12-01', 'time_status': 'missing',
         'start_time': None, 'end_time': None}
VALID = json.dumps({'outcome': 'events', 'events': [EVENT]})


class ModelUsageTests(unittest.TestCase):


    def exercise(self, payload=VALID, usage=None, model='gpt-4o', enabled=True, status=200):
        sent = []


        def respond(request):
            sent.append(json.loads(request.content))
            if status != 200:
                return httpx.Response(status, json={'error': {'message': MARKER}})
            return httpx.Response(200, json={
                'id': MARKER, 'object': 'chat.completion', 'created': 0, 'model': MARKER,
                'usage': usage,
                'choices': [{'index': 0, 'finish_reason': 'stop',
                             'message': {'role': 'assistant', 'content': payload}}],
            })

        stdout, stderr = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            with patch.dict('os.environ', {'APP_LOG_FILE': str(path)}), redirect_stdout(stdout), redirect_stderr(stderr):
                ai = OpenAI(api_key=MARKER, max_retries=0,
                            http_client=httpx.Client(transport=httpx.MockTransport(respond)))
                app = create_app({'TESTING': True, 'OPENAI_API_KEY': None, 'OPENAI_CLIENT': ai,
                                  'OPENAI_MODEL': model, 'LOGGING_ENABLED': enabled})
                client = app.test_client()
                extract = client.post('/process', data={'text': MARKER,
                    'image': (io.BytesIO(b'synthetic'), 'private.png')})
                correct = client.post('/correct', json={'current_events': [EVENT], 'correction': MARKER})
                for handler in app.logger.handlers:
                    handler.flush()
                    handler.close()
                ai.close()
                archived = path.read_text() if path.exists() else ''
            output = stdout.getvalue() + stderr.getvalue() + archived
            self.assertNotIn(MARKER, output)
            self.assertNotIn('private.png', output)
            self.assertEqual(stderr.getvalue(), '')
            if not enabled:
                self.assertFalse(path.exists())
                self.assertEqual(output, '')
            records = [json.loads(line) for line in archived.splitlines()]
        return SimpleNamespace(sent=sent, records=records, statuses=[extract.status_code, correct.status_code])


    def test_environment_default_override_and_invalid_settings(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(environment_config()['OPENAI_MODEL'], 'gpt-4o')
        with patch.dict('os.environ', {'OPENAI_MODEL': ' gpt-4o-mini '}):
            self.assertEqual(environment_config()['OPENAI_MODEL'], 'gpt-4o-mini')
        for invalid in ('', '  ', 'private value', 'bad\nmodel', 'x' * 129):
            with self.subTest(invalid=invalid), patch.dict('os.environ', {'OPENAI_MODEL': invalid}):
                with self.assertRaisesRegex(ValueError, '^OPENAI_MODEL must be a nonempty model ID of at most 128 characters.$'):
                    environment_config()
        with self.assertRaises(ValueError):
            create_app({'OPENAI_API_KEY': None, 'OPENAI_MODEL': None})


    def test_default_and_override_reach_both_multimodal_and_correction_calls(self):
        for model in ('gpt-4o', 'gpt-4o-mini'):
            with self.subTest(model=model):
                result = self.exercise(model=model)
                self.assertEqual(result.statuses, [200, 200])
                self.assertEqual([r['model'] for r in result.sent], [model, model])
                self.assertEqual(result.sent[0]['messages'][1]['content'][1]['type'], 'image_url')
                self.assertTrue(all(r['response_format'] == {'type': 'json_object'} for r in result.sent))
                self.assertEqual({r['model'] for r in result.records if 'model' in r}, {model})


    def test_usage_is_numeric_correlated_and_only_once_per_returned_response(self):
        result = self.exercise(usage={'prompt_tokens': 120, 'completion_tokens': 30, 'total_tokens': 150,
            'prompt_tokens_details': {'cached_tokens': 80, 'private': MARKER}, 'private': MARKER})
        records = [r for r in result.records if r['event'] == 'provider_usage']
        self.assertEqual(len(records), 2)
        self.assertEqual({r['stage'] for r in records}, {'extract', 'correct'})
        for record in records:
            self.assertEqual((record['input_tokens'], record['output_tokens'], record['cached_input_tokens']), (120, 30, 80))
            self.assertNotIn('total_tokens', record)
            self.assertTrue(any(r['request_id'] == record['request_id'] and r['event'] == 'request_finished' for r in result.records))
        self.assertTrue(all('input_tokens' not in r for r in result.records if r['event'] != 'provider_usage'))


    def test_rejected_or_malformed_payloads_still_record_consumed_tokens(self):
        for payload, status in (('invalid', 502), (json.dumps({'outcome': 'unsupported'}), 400)):
            with self.subTest(payload=payload):
                result = self.exercise(payload=payload, usage={'prompt_tokens': 10, 'completion_tokens': 5})
                self.assertEqual(result.statuses, [status, status])
                self.assertEqual(sum(r.get('input_tokens', 0) for r in result.records), 20)


    def test_missing_usage_is_unknown_not_zero_and_bad_counts_are_dropped(self):
        for usage in (None, {}, {'prompt_tokens': MARKER, 'completion_tokens': -1,
                               'prompt_tokens_details': {'cached_tokens': True}},
                      {'prompt_tokens': 10 ** 20, 'completion_tokens': 1.5}):
            with self.subTest(usage=usage):
                result = self.exercise(usage=usage)
                self.assertEqual(result.statuses, [200, 200])
                for record in result.records:
                    self.assertFalse({'input_tokens', 'output_tokens', 'cached_input_tokens'} & record.keys())


    def test_cached_counts_are_a_subset_and_zero_is_preserved(self):
        for usage, expected in (({'prompt_tokens': 0, 'completion_tokens': 0,
                                 'prompt_tokens_details': {'cached_tokens': 0}}, 0),
                                ({'prompt_tokens': 10, 'completion_tokens': 2,
                                  'prompt_tokens_details': {'cached_tokens': 11}}, None)):
            with self.subTest(usage=usage):
                result = self.exercise(usage=usage)
                for record in result.records:
                    if record['event'] == 'provider_usage':
                        self.assertEqual(record['input_tokens'], usage['prompt_tokens'])
                        self.assertEqual(record.get('cached_input_tokens'), expected)


    def test_unknown_configured_model_is_forwarded_but_never_logged_verbatim(self):
        result = self.exercise(model=MARKER)
        self.assertEqual(result.sent[0]['model'], MARKER)
        self.assertEqual({r['model'] for r in result.records if 'model' in r}, {'other'})


    def test_api_failure_has_no_fabricated_usage(self):
        result = self.exercise(status=401)
        self.assertEqual(result.statuses, [503, 503])
        self.assertFalse(any(r['event'] == 'provider_usage' for r in result.records))


    def test_logging_off_suppresses_usage_and_spool(self):
        result = self.exercise(usage={'prompt_tokens': 10, 'completion_tokens': 5}, enabled=False)
        self.assertEqual(result.statuses, [200, 200])
        self.assertEqual(result.records, [])
