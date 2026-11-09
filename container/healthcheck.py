"""Local-only container readiness probe."""
import json
import os
from pathlib import Path
from urllib.request import urlopen

pids = json.loads(Path('/tmp/runtime/pids.json').read_text())
for pid in pids.values():
    os.kill(pid, 0)
with urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/api/config', timeout=2) as response:
    assert response.status == 200
