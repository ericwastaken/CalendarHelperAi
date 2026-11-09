"""Small, allowlisted operational records. Never log user or provider payloads."""
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import time
import sys
from datetime import datetime, timezone
from uuid import uuid4

from flask import current_app, g, request
from .config import APP_VERSION

FIELDS = {'stage', 'outcome', 'elapsed_ms', 'image_count', 'event_count', 'status',
          'error_type', 'exception_class', 'provider_status', 'provider_code',
          'provider_request_id', 'model'}


class JsonFormatter(logging.Formatter):


    def format(self, record):
        return record.getMessage()


def log_event(event, level=logging.INFO, **fields):
    record = {'event': event, 'event_id': uuid4().hex, 'schema_version': 1,
              'version': APP_VERSION, 'level': logging.getLevelName(level),
              'timestamp': datetime.now(timezone.utc).isoformat(),
              'request_id': getattr(g, 'request_id', None)}
    record.update({key: value for key, value in fields.items() if key in FIELDS})
    current_app.logger.log(level, json.dumps(record, separators=(',', ':')))


def safe_identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value) else None


def install_logging(app):
    for previous in app.logger.handlers:
        previous.close()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    app.logger.handlers = [handler]
    # Only allowlisted operational events use this dedicated spool. Server and
    # third-party diagnostics stay on stdout/stderr, outside the archive.
    spool = os.environ.get('APP_LOG_FILE')
    if spool:
        Path(spool).parent.mkdir(parents=True, exist_ok=True)
        archive = RotatingFileHandler(spool, maxBytes=1024 * 1024, backupCount=10)
        archive.setFormatter(JsonFormatter())
        app.logger.addHandler(archive)
    app.logger.propagate = False
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def begin_request():
        g.request_id = uuid4().hex
        g.started_at = time.monotonic()

    @app.after_request
    def finish_request(response):
        response.headers['X-Request-ID'] = g.request_id
        if request.path in {'/process', '/correct', '/resolve-time', '/download-ics'}:
            log_event('request_finished', stage=request.endpoint, status=response.status_code,
                      elapsed_ms=round((time.monotonic() - g.started_at) * 1000),
                      outcome='success' if response.status_code < 400 else 'failure')
            if response.is_json:
                body = response.get_json()
                if isinstance(body, dict):
                    body['request_id'] = g.request_id
                    response.set_data(app.json.dumps(body))
        return response
