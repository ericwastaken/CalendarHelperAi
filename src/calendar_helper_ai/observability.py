"""Operational records with fixed values and no user/provider payloads."""
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import os
from pathlib import Path
import time
import sys
from datetime import datetime, timezone
from uuid import uuid4

from flask import current_app, g, request
from .config import APP_VERSION

EVENTS = frozenset({'application_started', 'request_finished', 'processing_started', 'provider_usage',
                    'provider_completed', 'provider_failed', 'request_rejected',
                    'processing_failed', 'validation_failed', 'unexpected_failure'})
ENUM_FIELDS = {
    'stage': frozenset({'initialize', 'extract', 'correct', 'calendar.process',
                        'calendar.correct', 'calendar.resolve_time', 'calendar.download_ics'}),
    'outcome': frozenset({'events', 'no_events', 'unsupported', 'success', 'failure'}),
    'error_type': frozenset({'provider_configuration', 'provider_error', 'provider_timeout',
                            'provider_connection', 'provider_authentication', 'provider_quota',
                            'provider_rate_limit', 'invalid_model_response', 'unsupported_request',
                            'validation_error', 'internal_error', 'no_events'}),
    'provider_code': frozenset({'insufficient_quota', 'rate_limit_exceeded', 'invalid_api_key',
                               'model_not_found', 'context_length_exceeded', 'invalid_request_error',
                               'server_error', 'content_policy_violation'}),
    'exception_class': frozenset({'APIError', 'APIStatusError', 'APIConnectionError',
                                 'APITimeoutError', 'APIResponseValidationError',
                                 'AuthenticationError', 'PermissionDeniedError', 'BadRequestError',
                                 'NotFoundError', 'ConflictError', 'UnprocessableEntityError',
                                 'RateLimitError', 'InternalServerError', 'ValueError', 'TypeError',
                                 'KeyError', 'AttributeError', 'IndexError', 'RuntimeError',
                                 'TimeoutError', 'ConnectionError', 'OSError', 'EventValidationError',
                                 'ProcessingError', 'SafetyValidationError', 'OtherError'}),
    'model': frozenset({'gpt-4o', 'gpt-4o-mini', 'gpt-4.1', 'gpt-4.1-mini',
                        'gpt-4.1-nano', 'other'}),
}
INTEGER_FIELDS = {'image_count': (0, 5), 'event_count': (0, 10000),
                  'status': (100, 599), 'provider_status': (100, 599),
                  'input_tokens': (0, 1000000000), 'output_tokens': (0, 1000000000),
                  'cached_input_tokens': (0, 1000000000)}
LEVELS = frozenset({logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL})
DEPENDENCY_LOGGERS = ('openai', 'httpx', 'httpcore', 'urllib3', 'requests', 'werkzeug',
                      'flask', 'dotenv', 'asyncio', 'py.warnings')
_RECORD_TOKEN = object()


class StructuredEventFilter(logging.Filter):


    def filter(self, record):
        # A JSON-looking message, framework exception, or arbitrary logger call
        # is not an operational event. Only this module's emitter holds the token.
        return (getattr(record, '_calendar_record_token', None) is _RECORD_TOKEN
                and isinstance(getattr(record, '_calendar_record', None), dict))


class JsonFormatter(logging.Formatter):


    def format(self, record):
        # Do not use Formatter.format: it appends exception/stack text.
        return json.dumps(record._calendar_record, separators=(',', ':'), allow_nan=False)


def safe_provider_code(value):
    return value if type(value) is str and value in ENUM_FIELDS['provider_code'] else None


def configured_model_label():
    """Never turn arbitrary configuration or provider model strings into log text."""
    model = current_app.config['OPENAI_MODEL']
    return model if model in ENUM_FIELDS['model'] else 'other'


def log_provider_usage(response, stage):
    """Count one returned API response, even if its calendar payload is rejected."""
    usage = getattr(response, 'usage', None)
    fields = safe_fields({
        'input_tokens': getattr(usage, 'prompt_tokens', None),
        'output_tokens': getattr(usage, 'completion_tokens', None),
        'cached_input_tokens': getattr(getattr(usage, 'prompt_tokens_details', None), 'cached_tokens', None),
    })
    # Cached tokens are a subset of input tokens, not additional consumption.
    if 'input_tokens' not in fields or fields.get('cached_input_tokens', 0) > fields['input_tokens']:
        fields.pop('cached_input_tokens', None)
    log_event('provider_usage', stage=stage, model=configured_model_label(), **fields)


def safe_fields(fields):
    safe = {}
    for key, allowed in ENUM_FIELDS.items():
        value = fields.get(key)
        if type(value) is str and value in allowed:
            safe[key] = value
        elif key == 'exception_class' and value is not None:
            safe[key] = 'OtherError'
    for key, (minimum, maximum) in INTEGER_FIELDS.items():
        value = fields.get(key)
        if type(value) is int and minimum <= value <= maximum:
            safe[key] = value
    elapsed = fields.get('elapsed_ms')
    if type(elapsed) in (int, float) and 0 <= elapsed <= 3600000 and math.isfinite(elapsed):
        safe['elapsed_ms'] = round(elapsed)
    return safe


def log_event(event, level=logging.INFO, **fields):
    if not current_app.config['LOGGING_ENABLED'] or type(event) is not str or event not in EVENTS:
        return
    level = level if type(level) is int and level in LEVELS else logging.INFO
    record = {'event': event, 'event_id': uuid4().hex, 'schema_version': 1,
              'version': APP_VERSION, 'level': {20: 'INFO', 30: 'WARNING', 40: 'ERROR', 50: 'CRITICAL'}[level],
              'timestamp': datetime.now(timezone.utc).isoformat(),
              'request_id': getattr(g, '_operational_request_id', None)}
    record.update(safe_fields(fields))
    current_app.logger.log(level, json.dumps(record, separators=(',', ':'), allow_nan=False),
                           extra={'_calendar_record_token': _RECORD_TOKEN,
                                  '_calendar_record': record})


def suppress_dependency_logging():
    # Legacy verbose settings must never let SDK HTTP bodies, URLs or exception
    # strings escape through root logging. Silence existing children as well as
    # the parents inherited by children created later by these libraries.
    names = set(DEPENDENCY_LOGGERS)
    names.update(name for name in logging.Logger.manager.loggerDict
                 if any(name.startswith(prefix + '.') for prefix in DEPENDENCY_LOGGERS))
    for name in names:
        logger = logging.getLogger(name)
        logger.handlers = [logging.NullHandler()]
        logger.propagate = False
        logger.setLevel(logging.CRITICAL + 1)
        logger.disabled = True


def install_logging(app):
    suppress_dependency_logging()
    for previous in app.logger.handlers:
        previous.close()
    app.logger.handlers = []
    if app.config['LOGGING_ENABLED']:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler.addFilter(StructuredEventFilter())
        app.logger.addHandler(handler)
        spool = os.environ.get('APP_LOG_FILE')
        if spool:
            try:
                Path(spool).parent.mkdir(parents=True, exist_ok=True)
                archive = RotatingFileHandler(spool, maxBytes=1024 * 1024, backupCount=10)
            except OSError:
                raise RuntimeError('Operational log storage is unavailable.') from None
            archive.setFormatter(JsonFormatter())
            archive.addFilter(StructuredEventFilter())
            app.logger.addHandler(archive)
    else:
        # Avoid logging.lastResort writing free-text warnings to stderr.
        app.logger.addHandler(logging.NullHandler())
    app.logger.propagate = False
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def begin_request():
        g._operational_request_id = uuid4().hex
        g.request_id = g._operational_request_id
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
