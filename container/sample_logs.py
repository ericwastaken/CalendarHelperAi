"""Emit fictional operational records through the app's actual logging pipeline.

Run only in a disposable local container with an isolated log destination.
"""
import logging
from uuid import uuid4
from flask import g
from calendar_helper_ai import create_app
from calendar_helper_ai.observability import log_event

app = create_app({'TESTING': True, 'OPENAI_API_KEY': None})
with app.app_context():
    for index, status in enumerate((200, 200, 400, 429, 504)):
        g._operational_request_id = uuid4().hex
        if status >= 400:
            log_event('provider_failed', logging.ERROR, status=status,
                      error_type={400: 'unsupported_request', 429: 'provider_rate_limit', 504: 'provider_timeout'}[status],
                      stage='extract')
        log_event('request_finished', status=status, elapsed_ms=(index + 1) * 120,
                  outcome='success' if status == 200 else 'failure', stage='calendar.process')
