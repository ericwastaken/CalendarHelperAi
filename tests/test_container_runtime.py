"""Logging-off runtime isolation, quiet child processes and readiness checks."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[1]


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, REPO / 'container' / file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


runtime = module('container_runtime', 'runtime.py')
healthcheck = module('container_healthcheck', 'healthcheck.py')


class Process:


    def __init__(self, pid):
        self.pid = pid
        self.returncode = None
        self.terminated = False
        self.killed = False


    def poll(self):
        return self.returncode


    def terminate(self):
        self.terminated = True
        self.returncode = 0


    def wait(self, timeout=None):
        return self.returncode


    def kill(self):
        self.killed = True
        self.returncode = -9


class RuntimeLoggingTests(unittest.TestCase):


    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'runtime'
        self.logs = Path(self.temp.name) / 'logs'
        for target, name, value in ((runtime, 'ROOT', self.root),
                                    (runtime, 'LOGS', self.logs),
                                    (healthcheck, 'ROOT', self.root)):
            item = patch.object(target, name, value)
            item.start()
            self.addCleanup(item.stop)


    def test_disabled_configuration_ignores_all_collector_settings_and_writes_nothing(self):
        with patch.dict(os.environ, {'LOGGING_ENABLED': ' false ', 'LOG_OUTPUT': 'invalid',
                                     'APP_LOG_FILE': '/not-a-valid/spool'}, clear=True):
            self.assertFalse(runtime.configure())
        self.assertFalse(self.root.exists())
        self.assertFalse(self.logs.exists())


    def test_disabled_runtime_has_one_quiet_child_and_drains_without_collector(self):
        app = Process(4101)
        observed = []


        def tick(seconds):
            self.assertEqual(seconds, 0.5)
            observed.append(json.loads((self.root / 'pids.json').read_text()))
            runtime.stopping(None, None)

        output = io.StringIO()
        with patch.dict(os.environ, {'LOGGING_ENABLED': 'false', 'LOG_OUTPUT': 's3',
                                     'APP_LOG_FILE': '/ignored', 'LOG_S3_BUCKET': 'unused',
                                     'AWS_ACCESS_KEY_ID': 'unused', 'AWS_SECRET_ACCESS_KEY': 'unused'}, clear=True), \
                patch.object(runtime.subprocess, 'Popen', return_value=app) as spawn, \
                patch.object(runtime.signal, 'signal'), patch.object(runtime.time, 'sleep', side_effect=tick), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            self.assertEqual(runtime.main(), 0)
        self.assertEqual(observed, [{'app': 4101}])
        spawn.assert_called_once()
        command = spawn.call_args.args[0]
        options = spawn.call_args.kwargs
        self.assertEqual(command[0], 'gunicorn')
        self.assertEqual(command[command.index('--access-logfile') + 1], '/dev/null')
        self.assertEqual(command[command.index('--error-logfile') + 1], '/dev/null')
        self.assertEqual(options['stdout'], subprocess.DEVNULL)
        self.assertEqual(options['stderr'], subprocess.DEVNULL)
        self.assertNotIn('APP_LOG_FILE', options['env'])
        self.assertNotIn('LOG_S3_BUCKET', options['env'])
        self.assertNotIn('AWS_ACCESS_KEY_ID', options['env'])
        self.assertNotIn('AWS_SECRET_ACCESS_KEY', options['env'])
        self.assertEqual(options['env']['LOGGING_ENABLED'], 'false')
        self.assertTrue(app.terminated)
        self.assertFalse(self.logs.exists())
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(output.getvalue(), '')


    def test_enabled_default_starts_collector_and_publishes_both_pids(self):
        app, collector = Process(4201), Process(4202)
        observed = []
        settings = {'APP_LOG_FILE': str(self.logs / 'spool/events.jsonl'),
                    'LOG_PROJECT': 'calendarhelperai', 'LOG_ENV': 'dev', 'LOG_INSTANCE': 'test'}


        def tick(seconds):
            if seconds == 0.5:
                observed.append(json.loads((self.root / 'pids.json').read_text()))
                runtime.stopping(None, None)

        with patch.dict(os.environ, settings, clear=True), \
                patch.object(runtime.subprocess, 'Popen', side_effect=[collector, app]) as spawn, \
                patch.object(runtime.signal, 'signal'), patch.object(runtime.time, 'sleep', side_effect=tick):
            self.assertEqual(runtime.main(), 0)
        self.assertEqual(spawn.call_count, 2)
        self.assertEqual(spawn.call_args_list[0].args[0][0], '/fluent-bit/bin/fluent-bit')
        self.assertIsNone(spawn.call_args_list[1].kwargs['stdout'])
        self.assertEqual(spawn.call_args_list[1].kwargs['stderr'], subprocess.DEVNULL)
        self.assertEqual(observed, [{'app': 4201, 'collector': 4202}])
        self.assertTrue((self.root / 'fluent-bit.conf').is_file())
        self.assertTrue((self.root / 'parsers.conf').is_file())
        self.assertTrue((self.logs / 'spool').is_dir())
        self.assertTrue(app.terminated)
        self.assertTrue(collector.terminated)
        self.assertFalse((self.root / 'pids.json').exists())


    def test_enabled_s3_still_requires_destination_settings(self):
        settings = {'APP_LOG_FILE': str(self.logs / 'spool/events.jsonl'),
                    'LOG_PROJECT': 'calendarhelperai', 'LOG_ENV': 'prod', 'LOG_OUTPUT': 's3'}
        with patch.dict(os.environ, settings, clear=True):
            with self.assertRaisesRegex(ValueError, 'LOG_S3_BUCKET'):
                runtime.configure()


    def test_disabled_forced_shutdown_does_not_emit_diagnostics(self):
        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('worker', 1), 0]
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            runtime.drain(process, 1, emit_diagnostics=False)
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(output.getvalue(), '')


    def test_readiness_requires_app_only_when_disabled_and_collector_when_enabled(self):
        self.root.mkdir()
        pids = self.root / 'pids.json'
        pids.write_text(json.dumps({'app': 5101}))
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch.dict(os.environ, {'LOGGING_ENABLED': 'false'}, clear=True), \
                patch.object(healthcheck.os, 'kill') as check_pid, \
                patch.object(healthcheck, 'urlopen', return_value=response):
            self.assertTrue(healthcheck.check_health())
            check_pid.assert_called_once_with(5101, 0)
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(healthcheck.check_health())
        pids.write_text(json.dumps({'app': 5101, 'collector': 5102}))
        with patch.dict(os.environ, {}, clear=True), patch.object(healthcheck.os, 'kill') as check_pid, \
                patch.object(healthcheck, 'urlopen', return_value=response):
            self.assertTrue(healthcheck.check_health())
            self.assertEqual(check_pid.call_count, 2)
        with patch.dict(os.environ, {'LOGGING_ENABLED': 'false'}, clear=True):
            self.assertFalse(healthcheck.check_health())


    def test_invalid_toggle_fails_with_constant_error_without_echoing_value(self):
        settings = {**os.environ, 'LOGGING_ENABLED': 'private-content-marker'}
        result = subprocess.run([sys.executable, str(REPO / 'container/runtime.py')],
                                env=settings, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, 'runtime: configuration or startup failed\n')


if __name__ == '__main__':
    unittest.main()
