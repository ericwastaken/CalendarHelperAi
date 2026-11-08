"""Regression coverage for image context, unknown times and safe provider diagnostics."""
import io
import json
import logging
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
from icalendar import Calendar
from openai import AuthenticationError, RateLimitError, APITimeoutError

from calendar_helper_ai import create_app
from calendar_helper_ai.services.events import normalize_event

MISSING = {'title': 'Service visit', 'date': '2026-11-09', 'time_status': 'missing',
           'start_time': None, 'end_time': None, 'location_name': '', 'location_address': ''}
TIMED = dict(MISSING, time_status='timed', start_time='2026-11-09T00:00:00-05:00',
             end_time='2026-11-09T01:00:00-05:00')


def response(events, outcome='events'):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({'outcome': outcome, 'events': events})))], _request_id='req_test123')


class ReliabilityTests(unittest.TestCase):


    def setUp(self):
        self.ai = MagicMock()
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only', 'OPENAI_API_KEY': None,
                               'OPENAI_CLIENT': self.ai, 'DEBUG_LOGGING': True})
        self.client = self.app.test_client()
        self.ai.chat.completions.create.return_value = response([MISSING])


    def test_terse_instruction_and_images_share_one_model_call(self):
        result = self.client.post('/process', data={'text': 'this one', 'image': (io.BytesIO(b'fictional'), 'private.png')})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['events'][0]['time_status'], 'missing')
        self.ai.chat.completions.create.assert_called_once()
        content = self.ai.chat.completions.create.call_args.kwargs['messages'][1]['content']
        self.assertIn('this one', content[0]['text'])
        self.assertTrue(content[1]['image_url']['url'].startswith('data:image/png;base64,'))
        self.assertNotIn('private.png', json.dumps(content))


    def test_image_only_has_calendar_context(self):
        self.assertEqual(self.client.post('/process', data={'image': (io.BytesIO(b'fictional'), 'test.png')}).status_code, 200)
        content = self.ai.chat.completions.create.call_args.kwargs['messages'][1]['content']
        self.assertIn('Find appointments', content[0]['text'])


    def test_correction_contains_existing_unknown_time(self):
        result = self.client.post('/correct', json={'current_events': [MISSING], 'correction': '3 pm'})
        self.assertEqual(result.status_code, 200)
        content = json.loads(self.ai.chat.completions.create.call_args.kwargs['messages'][1]['content'])
        self.assertEqual(content['current_events'][0]['time_status'], 'missing')
        self.assertEqual(content['correction'], '3 pm')


    def test_unrelated_correction_cannot_approve_suggested_duration(self):
        event = normalize_event(dict(TIMED, end_time=None))
        returned = dict(event, title='Updated title')
        returned.pop('duration_assumed')
        returned.pop('duration_confirmed')
        self.ai.chat.completions.create.return_value = response([returned])
        result = self.client.post('/correct', json={'current_events': [event], 'correction': 'Change title'})
        updated = result.json['events'][0]
        self.assertTrue(updated['duration_assumed'])
        self.assertFalse(updated['duration_confirmed'])


    def test_no_events_and_unrelated_request_are_distinct(self):
        for outcome, error in [('no_events', 'no_events'), ('unsupported', 'unsupported_request')]:
            self.ai.chat.completions.create.return_value = response([], outcome)
            result = self.client.post('/process', data={'text': 'synthetic'})
            self.assertEqual(result.json['error_type'], error)


    def test_missing_time_cannot_export_until_explicit_all_day_choice(self):
        result = self.client.post('/download-ics', json={'events': [MISSING]})
        self.assertEqual(result.status_code, 400)
        resolved = self.client.post('/resolve-time', json={'event': MISSING, 'mode': 'all_day'})
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.json['event']['all_day_source'], 'user')
        exported = self.client.post('/download-ics', json={'events': [resolved.json['event']]})
        event = Calendar.from_ical(exported.json['ics_content']).walk('VEVENT')[0]
        self.assertEqual(event.decoded('DTSTART'), date(2026, 11, 9))
        self.assertEqual(event.decoded('DTEND'), date(2026, 11, 10))
        self.assertEqual(event['DTSTART'].params['VALUE'], 'DATE')


    def test_missing_time_can_resolve_to_local_time(self):
        result = self.client.post('/resolve-time', headers={'X-Timezone': 'America/New_York'}, json={
            'event': MISSING, 'mode': 'timed', 'start_local': '2026-11-09T15:00', 'end_local': '2026-11-09T16:00'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['event']['start_time'], '2026-11-09T15:00:00-05:00')
        self.assertEqual(self.client.post('/download-ics', json={'events': [result.json['event']]}).status_code, 200)


    def test_clock_change_ambiguous_and_missing_local_times_are_rejected(self):
        for start, end in [('2026-11-01T01:30', '2026-11-01T03:00'), ('2026-03-08T02:30', '2026-03-08T04:00')]:
            result = self.client.post('/resolve-time', headers={'X-Timezone': 'America/New_York'}, json={
                'event': MISSING, 'mode': 'timed', 'start_local': start, 'end_local': end})
            self.assertEqual(result.status_code, 400)


    def test_real_midnight_remains_timed_and_suggested_end_needs_confirmation(self):
        self.assertEqual(normalize_event(TIMED)['time_status'], 'timed')
        event = normalize_event(dict(TIMED, end_time=None))
        self.assertTrue(event['duration_assumed'])
        self.assertEqual(self.client.post('/download-ics', json={'events': [event]}).status_code, 400)
        result = self.client.post('/resolve-time', json={'event': event, 'mode': 'confirm_duration'})
        self.assertEqual(self.client.post('/download-ics', json={'events': [result.json['event']]}).status_code, 200)


    def test_provider_errors_never_leak_payloads_even_with_debug_enabled(self):
        request = httpx.Request('POST', 'https://api.openai.com/v1/chat/completions')
        cases = [
            (AuthenticationError('sk-secret private appointment', response=httpx.Response(401, request=request, headers={'x-request-id': 'req_auth'}), body={'code': 'invalid_api_key'}), 'provider_authentication', 503),
            (RateLimitError('private appointment', response=httpx.Response(429, request=request), body={'code': 'insufficient_quota'}), 'provider_quota', 503),
            (RateLimitError('private appointment', response=httpx.Response(429, request=request), body={'code': 'rate_limit_exceeded'}), 'provider_rate_limit', 429),
            (APITimeoutError(request), 'provider_timeout', 504),
        ]
        for error, kind, status in cases:
            self.ai.chat.completions.create.side_effect = error
            with self.assertLogs(self.app.logger, logging.INFO) as logs:
                result = self.client.post('/process', data={'text': 'private appointment sk-secret'})
            self.assertEqual(result.status_code, status)
            self.assertEqual(result.json['error_type'], kind)
            self.assertEqual(result.headers['X-Request-ID'], result.json['request_id'])
            self.assertNotIn('private appointment', ''.join(logs.output))
            self.assertNotIn('sk-secret', ''.join(logs.output))
            self.assertIn(kind, ''.join(logs.output))


    def test_malformed_provider_response_is_not_safety_rejection(self):
        self.ai.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='private malformed'))])
        result = self.client.post('/process', data={'text': 'appointment'})
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json['error_type'], 'invalid_model_response')


    def test_request_ids_are_generated_and_health_is_quiet(self):
        with self.assertNoLogs(self.app.logger):
            first = self.client.get('/api/config', headers={'X-Request-ID': 'do-not-trust'})
            second = self.client.get('/api/config')
        self.assertNotEqual(first.headers['X-Request-ID'], second.headers['X-Request-ID'])
        self.assertNotEqual(first.headers['X-Request-ID'], 'do-not-trust')


if __name__ == '__main__':
    unittest.main()
