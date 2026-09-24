"""Contracts that must survive installing the app outside its source tree."""
import unittest
from html.parser import HTMLParser
from importlib.metadata import version
from unittest.mock import MagicMock, patch

from calendar_helper_ai import create_app


class AssetLinks(HTMLParser):


    def __init__(self):
        super().__init__()
        self.paths = []


    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in {'href', 'src'} and value.startswith('/static/'):
                self.paths.append(value)


class ApplicationTests(unittest.TestCase):


    def make_app(self, **overrides):
        config = {'TESTING': True, 'SECRET_KEY': 'test-only',
                  'OPENAI_API_KEY': None, 'DEBUG_LOGGING': False}
        config.update(overrides)
        return create_app(config)


    def test_homepage_and_all_linked_assets_are_packaged(self):
        client = self.make_app().test_client()
        response = client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(f'v{version("calendar-helper-ai")}', response.get_data(as_text=True))
        parser = AssetLinks()
        parser.feed(response.get_data(as_text=True))
        self.assertGreaterEqual(len(parser.paths), 7)
        paths = parser.paths + ['/favicon.ico', '/static/terms.html',
                                '/static/example-images-and-prompts.html',
                                '/static/images/example-event-cards-2026-09.png']
        for path in paths:
            with self.subTest(path=path), client.get(path) as asset:
                self.assertEqual(asset.status_code, 200)
                self.assertGreater(len(asset.data), 0)


    def test_apps_have_independent_config_and_ai_clients(self):
        first_client, second_client = MagicMock(), MagicMock()
        first = self.make_app(OPENAI_CLIENT=first_client, DEBUG_LOGGING=True)
        second = self.make_app(OPENAI_CLIENT=second_client)
        self.assertIs(first.extensions['openai'], first_client)
        self.assertIs(second.extensions['openai'], second_client)
        self.assertTrue(first.test_client().get('/api/config').json['debug_logging'])
        self.assertFalse(second.test_client().get('/api/config').json['debug_logging'])
        self.assertEqual(second.test_client().get('/api/config').json['version'],
                         version('calendar-helper-ai'))


    def test_test_configuration_skips_dotenv_and_real_client(self):
        with patch('calendar_helper_ai.load_dotenv') as dotenv, patch('calendar_helper_ai.OpenAI') as client:
            app = self.make_app()
            dotenv.assert_not_called()
            client.assert_not_called()
            self.assertIsNone(app.extensions['openai'])


    def test_correction_and_export_are_registered_on_blueprint(self):
        client = self.make_app().test_client()
        event = {'title': 'Synthetic review', 'start_time': '2026-10-02T10:00:00-04:00',
                 'end_time': '2026-10-02T11:00:00-04:00'}
        with patch('calendar_helper_ai.routes.process_corrections', return_value=[event]) as correct:
            response = client.post('/correct', json={'current_events': [event], 'correction': 'Keep the time'},
                                   headers={'X-Timezone': 'America/New_York'})
            self.assertEqual(response.status_code, 200)
            correct.assert_called_once_with('Keep the time', [event], 'America/New_York')
        response = client.post('/download-ics', json={'events': response.json['events']},
                               headers={'X-Timezone': 'America/New_York'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('BEGIN:VEVENT', response.json['ics_content'])
