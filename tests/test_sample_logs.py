"""The disposable fixture must exercise the real structured logging contract."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


class SampleLogTests(unittest.TestCase):


    def test_sample_records_keep_request_correlation_and_error_categories(self):
        script = Path(__file__).resolve().parents[1] / 'container' / 'sample_logs.py'
        environment = {**os.environ, 'LOGGING_ENABLED': 'true', 'APP_LOG_FILE': ''}
        result = subprocess.run([sys.executable, str(script)], env=environment,
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stderr, '')
        records = [json.loads(line) for line in result.stdout.splitlines()]
        requests = [record for record in records if record['event'] == 'request_finished']
        failures = [record for record in records if record['event'] == 'provider_failed']
        self.assertEqual([record['status'] for record in requests], [200, 200, 400, 429, 504])
        self.assertEqual(len({record['request_id'] for record in requests}), 5)
        self.assertEqual(len({record['event_id'] for record in records}), len(records))
        by_request = {record['request_id']: record for record in requests}
        expected = {400: 'unsupported_request', 429: 'provider_rate_limit', 504: 'provider_timeout'}
        self.assertEqual(len(failures), 3)
        for request in requests:
            self.assertRegex(request['request_id'], r'^[0-9a-f]{32}$')
        for failure in failures:
            self.assertEqual(failure['error_type'], expected[failure['status']])
            self.assertEqual(by_request[failure['request_id']]['status'], failure['status'])
            self.assertEqual(by_request[failure['request_id']]['outcome'], 'failure')
        self.assertTrue(all(record['schema_version'] == 1 for record in records))


if __name__ == '__main__':
    unittest.main()
