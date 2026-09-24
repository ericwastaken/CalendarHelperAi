"""Regression checks for the input/review/export workflow. No external API calls."""
import io
import json
import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from unittest.mock import patch

# Tests never depend on or transmit the developer's credentials.
os.environ['OPENAI_API_KEY'] = 'sk-local-unit-test-only'
os.environ['DEBUG_LOGGING'] = 'false'
from app import app
from utils import ai_processor
from utils.calendar import generate_ics
from icalendar import Calendar

EVENT = {
    'title': 'Design review', 'description': 'Synthetic event',
    'start_time': '2026-10-02T14:00:00+00:00',
    'end_time': '2026-10-02T15:00:00+00:00',
    'location_name': 'unknown', 'location_address': '',
}


def ai_response(events):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({'events': events})))])


class ExtractionTests(unittest.TestCase):


    def test_text_and_image_use_one_extraction_and_return_events(self):
        for images in ([], [{'data': 'synthetic-base64', 'filename': 'test.png'}]):
            with self.subTest(images=bool(images)), app.test_request_context('/'), patch.object(ai_processor, 'validate_prompt_safety', return_value=(True, '')), patch.object(ai_processor.client.chat.completions, 'create', return_value=ai_response([EVENT])) as create:
                result = ai_processor.process_image_and_text(images, 'October 2, 2026, 10 AM', 'America/New_York')
                self.assertEqual(result[0]['title'], EVENT['title'])
                self.assertNotIn('location', result[0])
                self.assertEqual(create.call_count, 1)


    def test_no_events_is_a_valid_empty_result(self):
        with app.test_request_context('/'), patch.object(ai_processor, 'validate_prompt_safety', return_value=(True, '')), patch.object(ai_processor.client.chat.completions, 'create', return_value=ai_response([])):
            self.assertEqual(ai_processor.process_image_and_text([], 'No appointments', 'UTC'), [])


    def test_malformed_model_result_is_not_success(self):
        with app.test_request_context('/'), patch.object(ai_processor, 'validate_prompt_safety', return_value=(True, '')), patch.object(ai_processor.client.chat.completions, 'create', return_value=ai_response('invalid')):
            with self.assertRaises(Exception):
                ai_processor.process_image_and_text([], 'An event', 'UTC')


class EndpointTests(unittest.TestCase):


    def setUp(self):
        self.client = app.test_client()


    def test_empty_input_does_not_call_ai(self):
        with patch('routes.process_image_and_text') as process:
            response = self.client.post('/process', data={})
            self.assertEqual(response.status_code, 400)
            process.assert_not_called()


    def test_empty_result_is_actionable(self):
        with patch('routes.process_image_and_text', return_value=[]):
            response = self.client.post('/process', data={'text': 'No calendar events here'})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json['error_type'], 'no_events')


    def test_later_oversized_image_rejected_before_ai(self):
        with patch('routes.process_image_and_text') as process:
            response = self.client.post('/process', data={'image': [(io.BytesIO(b'small'), 'first.png'), (io.BytesIO(b'0' * (4 * 1024 * 1024 + 1)), 'second.png')]})
            self.assertEqual(response.status_code, 400)
            self.assertIn('second.png', response.json['user_message'])
            process.assert_not_called()
            response.request.input_stream.close()
            response.request.close()
            response.close()


    def test_five_four_megabyte_files_fit_request_limit(self):
        with patch('routes.process_image_and_text', return_value=[EVENT]) as process:
            files = [(io.BytesIO(b'0' * (4 * 1024 * 1024)), f'{i}.png') for i in range(5)]
            response = self.client.post('/process', data={'image': files})
            self.assertEqual(response.status_code, 200)
            process.assert_called_once()
            response.request.input_stream.close()
            response.request.close()
            response.close()


    def test_oversized_request_returns_json(self):
        response = self.client.post('/process', data=b'0' * (22 * 1024 * 1024), content_type='multipart/form-data; boundary=example')
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json['error_type'], 'validation_error')


    def test_blank_correction_preserves_events(self):
        with patch('routes.process_corrections') as correct:
            response = self.client.post('/correct', json={'correction': ' ', 'current_events': [EVENT]})
            self.assertEqual(response.status_code, 400)
            correct.assert_not_called()


class CalendarTests(unittest.TestCase):


    def test_aware_dates_preserve_instant_across_zones(self):
        cal = Calendar.from_ical(generate_ics([EVENT], 'America/New_York'))
        event = cal.walk('VEVENT')[0]
        self.assertEqual(event.decoded('DTSTART').hour, 10)
        self.assertEqual(event.decoded('DTSTART').astimezone(timezone.utc), datetime(2026, 10, 2, 14, tzinfo=timezone.utc))
        self.assertEqual(str(event['DTSTART'].params['TZID']), 'America/New_York')
        self.assertTrue(event['UID'])
        self.assertTrue(event['DTSTAMP'])


    def test_dst_and_naive_local_time(self):
        data = dict(EVENT, start_time='2026-11-01T06:30:00Z', end_time='2026-11-01T07:30:00Z')
        event = Calendar.from_ical(generate_ics([data], 'America/New_York')).walk('VEVENT')[0]
        self.assertEqual(event.decoded('DTSTART').astimezone(timezone.utc), datetime(2026, 11, 1, 6, 30, tzinfo=timezone.utc))
        self.assertEqual(event.decoded('DTSTART').astimezone(ZoneInfo('America/New_York')).utcoffset().total_seconds(), -18000)
        data.update(start_time='2026-10-02T10:00:00', end_time='2026-10-02T11:00:00')
        event = Calendar.from_ical(generate_ics([data], 'America/New_York')).walk('VEVENT')[0]
        self.assertEqual(event.decoded('DTSTART').hour, 10)


    def test_invalid_event_fails_instead_of_silently_disappearing(self):
        with self.assertRaises(ValueError):
            generate_ics([dict(EVENT, end_time='2026-10-02T12:00:00Z')], 'UTC')


    def test_event_crossing_repeated_hour_keeps_positive_duration(self):
        data = dict(EVENT, start_time='2026-11-01T01:45:00-04:00', end_time='2026-11-01T01:15:00-05:00')
        event = Calendar.from_ical(generate_ics([data], 'America/New_York')).walk('VEVENT')[0]
        self.assertEqual((event.decoded('DTEND') - event.decoded('DTSTART')).total_seconds(), 1800)


if __name__ == '__main__':
    unittest.main()
