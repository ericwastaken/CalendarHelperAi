"""Operational output must exclude submitted data and be completely optional."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import httpx
from flask import g
from openai import OpenAI

from calendar_helper_ai import create_app
from calendar_helper_ai.config import environment_config
from calendar_helper_ai.observability import DEPENDENCY_LOGGERS, log_event

MARKER = 'PRIVATE_PERSONAL_CANARY_5551212'
MISSING = {'title': MARKER, 'date': '2026-11-09', 'time_status': 'missing',
           'start_time': None, 'end_time': None}


class SpoolTests(unittest.TestCase):


    def close_handlers(self, app):
        for handler in app.logger.handlers:
            handler.flush()
            handler.close()


    def test_allowlist_event_identity_and_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            with patch.dict('os.environ', {'APP_LOG_FILE': str(path)}):
                app = create_app({'TESTING': True, 'OPENAI_API_KEY': None})
                handler = next(h for h in app.logger.handlers if hasattr(h, 'doRollover'))
                with app.test_request_context('/process'):
                    app.preprocess_request()
                    request_id = g.request_id
                    log_event('provider_failed', logging.ERROR, error_type='provider_timeout',
                              prompt=MARKER, secret=MARKER)
                    handler.doRollover()
                    log_event('request_finished', status=504)
                self.close_handlers(app)
                records = [json.loads(line) for file in Path(directory).glob('events.jsonl*')
                           for line in file.read_text().splitlines()]
                self.assertEqual(len(records), 3)
                self.assertEqual(len({r['event_id'] for r in records}), 3)
                self.assertTrue(all(r['schema_version'] == 1 for r in records))
                self.assertEqual(sum(r['request_id'] == request_id for r in records), 2)
                self.assertNotIn(MARKER, json.dumps(records))


    def test_values_and_direct_exception_logs_cannot_enter_stdout_or_spool(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            with patch.dict('os.environ', {'APP_LOG_FILE': str(path)}), redirect_stdout(stdout), redirect_stderr(stderr):
                app = create_app({'TESTING': True, 'OPENAI_API_KEY': None})
                with app.app_context():
                    g.request_id = MARKER
                    # This formerly regex-valid provider identifier is still personal data.
                    log_event('provider_failed', stage=MARKER, outcome=MARKER,
                              error_type=MARKER, exception_class=MARKER,
                              provider_code=MARKER, provider_request_id=MARKER, model=MARKER,
                              status=MARKER, provider_status=MARKER, event_count=MARKER,
                              image_count=MARKER, elapsed_ms=MARKER, request_id=MARKER)
                    log_event(MARKER, message=MARKER)
                    log_event('request_finished', status=1000, provider_status=-1,
                              event_count=True, image_count=6, elapsed_ms=float('nan'))
                    log_event('request_finished', elapsed_ms=10 ** 1000)
                    try:
                        raise RuntimeError(MARKER)
                    except RuntimeError:
                        app.logger.exception(MARKER)
                        app.logger.error('{"event":"provider_failed","payload":"%s"}', MARKER)
                    app.logger.warning(MARKER, extra={'_calendar_record': {'event': MARKER}})
                self.close_handlers(app)
                archived = path.read_text()
            combined = stdout.getvalue() + stderr.getvalue() + archived
            self.assertNotIn(MARKER, combined)
            self.assertNotIn('Traceback', combined)
            records = [json.loads(line) for line in archived.splitlines()]
            self.assertEqual(len(records), 4)
            self.assertEqual(records[1]['exception_class'], 'OtherError')
            for record in records[1:]:
                self.assertNotIn('provider_request_id', record)
                self.assertNotIn('elapsed_ms', record)
                self.assertNotIn('status', record)
                self.assertNotIn('event_count', record)


    def test_real_sdk_verbose_http_logs_and_hostile_provider_metadata_are_silent(self):
        stdout, stderr, root_output = io.StringIO(), io.StringIO(), io.StringIO()
        root = logging.getLogger()
        root_handler = logging.StreamHandler(root_output)
        old_level = root.level
        root.setLevel(logging.DEBUG)
        root.addHandler(root_handler)
        calls = []


        def respond(request):
            calls.append(request.content)
            if len(calls) == 1:
                content = json.dumps({'outcome': 'events', 'events': [MISSING]})
                return httpx.Response(200, headers={'x-request-id': MARKER}, json={
                    'id': MARKER, 'object': 'chat.completion', 'created': 0, 'model': 'gpt-4o',
                    'choices': [{'index': 0, 'finish_reason': 'stop',
                                 'message': {'role': 'assistant', 'content': content}}]})
            return httpx.Response(401, headers={'x-request-id': MARKER}, json={
                'error': {'message': MARKER, 'code': MARKER, 'type': MARKER}})


        def make_client(**kwargs):
            return OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond)))

        try:
            # Simulate legacy verbose configuration and pre-existing SDK handlers.
            for name in ('openai', 'openai._base_client', 'httpx', 'httpcore', 'urllib3', 'werkzeug'):
                logger = logging.getLogger(name)
                logger.disabled = False
                logger.setLevel(logging.DEBUG)
                logger.propagate = True
                logger.addHandler(root_handler)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'events.jsonl'
                with patch.dict('os.environ', {'APP_LOG_FILE': str(path), 'OPENAI_LOG': 'debug',
                                               'DEBUG_LOGGING': 'true', 'OPENAI_HTTP_CLIENT_LEVEL': 'DEBUG',
                                               'OPENAI_API_LEVEL': 'DEBUG'}), redirect_stdout(stdout), redirect_stderr(stderr):
                    with patch('calendar_helper_ai.OpenAI', side_effect=make_client):
                        app = create_app({'TESTING': True, 'OPENAI_API_KEY': MARKER})
                    client = app.test_client()
                    result = client.post('/process', data={'text': MARKER,
                        'image': (io.BytesIO(MARKER.encode()), MARKER + '.png')})
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual(result.json['events'][0]['title'], MARKER)
                    result = client.post('/process', data={'text': MARKER})
                    self.assertEqual(result.status_code, 503)
                    self.assertEqual(result.json['error_type'], 'provider_authentication')
                    # Late-created dependency children must not reach root, either.
                    for name in DEPENDENCY_LOGGERS:
                        logging.getLogger(name + '.late_child').error(MARKER)
                    self.close_handlers(app)
                    app.extensions['openai'].close()
                    archived = path.read_text()
            self.assertEqual(len(calls), 2)
            self.assertIn(MARKER.encode(), calls[0])
            combined = stdout.getvalue() + stderr.getvalue() + root_output.getvalue() + archived
            self.assertNotIn(MARKER, combined)
            self.assertNotIn('provider_request_id', combined)
            self.assertIn('provider_authentication', archived)
            self.assertEqual(root_output.getvalue(), '')
        finally:
            root.removeHandler(root_handler)
            root.setLevel(old_level)


    def test_unexpected_framework_and_factory_errors_do_not_log_raw_exceptions(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with patch('calendar_helper_ai.OpenAI', side_effect=RuntimeError(MARKER)):
                app = create_app({'TESTING': True, 'OPENAI_API_KEY': MARKER})
            hostile_error = type(MARKER, (Exception,), {})


            @app.before_request
            def fail_outside_blueprint():
                from flask import request
                if request.path.startswith('/unknown-'):
                    raise hostile_error(MARKER)

            result = app.test_client().post('/process', data={'text': MARKER})
            self.assertEqual(result.status_code, 503)
            self.assertEqual(result.json['error_type'], 'provider_configuration')
            result = app.test_client().get('/unknown-' + MARKER)
            self.assertEqual(result.status_code, 500)
            self.assertEqual(result.json['error_type'], 'internal_error')
            self.assertIn('X-Request-ID', result.headers)
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertNotIn(MARKER, combined)
        self.assertIn('OtherError', combined)


    def test_disabled_logging_creates_no_spool_or_output_but_retains_request_ids(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'never-created' / 'events.jsonl'
            with patch.dict('os.environ', {'APP_LOG_FILE': str(path), 'LOGGING_ENABLED': 'FaLsE',
                                           'DEBUG_LOGGING': 'true', 'OPENAI_LOG': 'debug'}), redirect_stdout(stdout), redirect_stderr(stderr):
                ai = MagicMock()
                ai.chat.completions.create.side_effect = RuntimeError(MARKER)
                app = create_app({'TESTING': True, 'OPENAI_CLIENT': ai, 'OPENAI_API_KEY': None})
                result = app.test_client().post('/process', data={'text': MARKER},
                                               headers={'X-Request-ID': MARKER})
                self.assertEqual(result.status_code, 502)
                self.assertEqual(result.json['request_id'], result.headers['X-Request-ID'])
                self.assertRegex(result.json['request_id'], r'^[0-9a-f]{32}$')
                self.assertNotEqual(result.json['request_id'], MARKER)
                with app.app_context():
                    log_event('provider_failed', error_type='provider_error')
                    app.logger.error(MARKER)
                self.assertFalse(path.parent.exists())
            self.assertEqual(stdout.getvalue(), '')
            self.assertEqual(stderr.getvalue(), '')


    def test_logging_switch_is_strict_and_errors_do_not_echo_input(self):
        with patch.dict('os.environ', {'LOGGING_ENABLED': ' TrUe '}):
            self.assertTrue(environment_config()['LOGGING_ENABLED'])
        with patch.dict('os.environ', {'LOGGING_ENABLED': MARKER}):
            with self.assertRaisesRegex(ValueError, '^LOGGING_ENABLED must be true or false.$'):
                environment_config()
