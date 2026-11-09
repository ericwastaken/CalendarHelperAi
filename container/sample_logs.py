"""Emit fictional operational records through the app's actual logging pipeline.

Run only in a disposable local container with an isolated log destination.
"""
import logging
from flask import g
from calendar_helper_ai import create_app
from calendar_helper_ai.observability import log_event

app = create_app({'TESTING': True, 'OPENAI_API_KEY': None})
with app.app_context():
    for index, status in enumerate((200, 200, 400, 429, 504)):
        g.request_id = 'sample-request-' + str(index)
        if status >= 400:
            log_event('provider_failed', logging.ERROR, status=status,
                      error_type={400: 'unsupported', 429: 'rate_limit', 504: 'timeout'}[status],
                      stage='extract')
        log_event('request_finished', status=status, elapsed_ms=(index + 1) * 120,
                  outcome='success' if status == 200 else 'failure', stage='calendar.process')
