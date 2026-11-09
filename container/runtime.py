"""Supervise the app and its collector; drain the app before final log flush."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

ROOT = Path('/tmp/runtime')
LOGS = Path('/logs')
STOP = False


def value(name, default=None):
    result = os.environ.get(name, default)
    if result is None or not re.fullmatch(r'[A-Za-z0-9_./:\-]+', result):
        raise ValueError('Missing or invalid configuration: ' + name)
    return result


def logging_enabled():
    setting = os.environ.get('LOGGING_ENABLED', 'true').strip().lower()
    if setting not in {'true', 'false'}:
        raise ValueError('LOGGING_ENABLED must be true or false')
    return setting == 'true'


def configure():
    if not logging_enabled():
        return False
    ROOT.mkdir(parents=True, exist_ok=True)
    for directory in ('spool', 'state', 'output'):
        (LOGS / directory).mkdir(parents=True, exist_ok=True)
    if os.environ.get('APP_LOG_FILE') != str(LOGS / 'spool/events.jsonl'):
        raise ValueError('Container APP_LOG_FILE must be /logs/spool/events.jsonl')
    project, environment = value('LOG_PROJECT'), value('LOG_ENV')
    instance = value('LOG_INSTANCE', os.environ.get('HOSTNAME', 'unknown'))
    config = '''[SERVICE]
    Flush 1
    Grace 12
    Log_Level info
    Parsers_File /tmp/runtime/parsers.conf
    storage.path /logs/state/chunks
    storage.sync full
    storage.checksum on
    storage.backlog.mem_limit 5M
[INPUT]
    Name tail
    Tag app
    Path /logs/spool/events.jsonl*
    Parser app_json
    DB /logs/state/tail.db
    DB.Sync Full
    Read_from_Head On
    Refresh_Interval 1
    Rotate_Wait 10
    Buffer_Max_Size 256k
    Skip_Long_Lines On
    storage.type filesystem
[FILTER]
    Name modify
    Match app
'''
    config += f'    Set project {project}\n    Set environment {environment}\n    Set service web\n    Set instance {instance}\n'
    output = value('LOG_OUTPUT', 'file')
    if output == 'file':
        config += '''[OUTPUT]
    Name file
    Match app
    Path /logs/output
    File events-%Y-%m-%d-%H.jsonl
    Enable_Strftime On
    Fallback_File events-undated.jsonl
    Format plain
    Mkdir On
    Retry_Limit False
    storage.total_limit_size 64M
'''
    elif output == 's3':
        bucket = value('LOG_S3_BUCKET')
        endpoint = value('LOG_S3_ENDPOINT')
        region = value('LOG_S3_REGION')
        prefix = value('LOG_S3_PREFIX').strip('/')
        if '..' in prefix.split('/'):
            raise ValueError('Invalid LOG_S3_PREFIX')
        config += f'''[OUTPUT]
    Name s3
    Match app
    bucket {bucket}
    region {region}
    endpoint {endpoint}
    use_put_object On
    total_file_size 1M
    upload_timeout 5s
    store_dir /logs/state/s3
    store_dir_limit_size 64M
    retry_limit 1000
    retry_exhausted_action quarantine
    quarantine_dir_limit_size 64M
    compression gzip
    s3_key_format /{prefix}/%Y/%m/%d/%H/%M/%S-$UUID.jsonl.gz
    preserve_data_ordering On
'''
    else:
        raise ValueError('LOG_OUTPUT must be file or s3')
    (ROOT / 'fluent-bit.conf').write_text(config)
    (ROOT / 'parsers.conf').write_text('[PARSER]\n    Name app_json\n    Format json\n')
    return True


def stopping(signum, frame):
    global STOP
    STOP = True


def drain(process, timeout, emit_diagnostics=True):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        if emit_diagnostics:
            print('runtime: child exceeded shutdown deadline', flush=True)


def app_environment(enabled):
    environment = os.environ.copy()
    environment['LOGGING_ENABLED'] = 'true' if enabled else 'false'
    # Only the collector needs object-storage credentials. Do not give the
    # application worker access to its log writer credential.
    for key in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN'):
        environment.pop(key, None)
    if not enabled:
        environment.pop('APP_LOG_FILE', None)
        for key in list(environment):
            if key.startswith('LOG_S3_'):
                environment.pop(key)
    return environment


def main():
    global STOP
    STOP = False
    enabled = configure()
    # Readiness metadata is required in both modes. It contains PIDs, not logs.
    ROOT.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, stopping)
    signal.signal(signal.SIGINT, stopping)
    collector_cmd = ['/fluent-bit/bin/fluent-bit', '-c', str(ROOT / 'fluent-bit.conf')]
    collector = app = None
    code = 0
    try:
        if enabled:
            collector = subprocess.Popen(collector_cmd)
            time.sleep(1)
            if collector.poll() is not None:
                raise RuntimeError('Collector failed to start')
        # One worker owns the rotating log file. Do not increase workers without
        # replacing the spool with a multiprocess-safe transport.
        # Gunicorn's native diagnostics can contain request lines and client IPs.
        # The structured app logger owns enabled operational records instead.
        app = subprocess.Popen(['gunicorn', '--workers', '1', '--worker-class', 'gthread',
                                '--threads', '2', '--timeout', '120', '--graceful-timeout', '20',
                                '--access-logfile', '/dev/null', '--error-logfile', '/dev/null',
                                '--worker-tmp-dir', '/tmp', '--bind', '0.0.0.0:' + value('PORT', '8080'),
                                'calendar_helper_ai:create_app()'],
                               env=app_environment(enabled),
                               stdout=None if enabled else subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        restarts = []
        while not STOP:
            if app.poll() is not None:
                code = app.returncode or 1
                break
            if enabled and collector.poll() is not None:
                (ROOT / 'pids.json').unlink(missing_ok=True)
                restarts = [t for t in restarts if time.monotonic() - t < 60]
                if len(restarts) >= 3:
                    raise RuntimeError('Collector repeatedly failed; stopping container')
                restarts.append(time.monotonic())
                print('runtime: restarting failed collector', flush=True)
                collector = subprocess.Popen(collector_cmd)
            pids = {'app': app.pid}
            if enabled:
                pids['collector'] = collector.pid
            temporary = ROOT / 'pids.tmp'
            temporary.write_text(json.dumps(pids))
            temporary.replace(ROOT / 'pids.json')
            time.sleep(0.5)
    finally:
        (ROOT / 'pids.json').unlink(missing_ok=True)
        drain(app, 22, emit_diagnostics=enabled)
        if enabled:
            # Tail gets a final opportunity to read writes made while requests drained.
            time.sleep(2)
            drain(collector, 15)
    return code


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        # No exception repr, configuration value, request data or traceback.
        print('runtime: configuration or startup failed', file=sys.stderr, flush=True)
        sys.exit(1)
