"""Local-only readiness probe; supports app-only and app/collector runtimes."""
import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path('/tmp/runtime')


def check_health():
    setting = os.environ.get('LOGGING_ENABLED', 'true').strip().lower()
    if setting not in {'true', 'false'}:
        return False
    expected = {'app', 'collector'} if setting == 'true' else {'app'}
    pids = json.loads((ROOT / 'pids.json').read_text())
    if not isinstance(pids, dict) or set(pids) != expected:
        return False
    for pid in pids.values():
        if type(pid) is not int or pid <= 1:
            return False
        os.kill(pid, 0)
    with urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/api/config', timeout=2) as response:
        return response.status == 200


if __name__ == '__main__':
    try:
        sys.exit(0 if check_health() else 1)
    except Exception:
        # Readiness failure is represented by the exit status, not log output.
        sys.exit(1)
