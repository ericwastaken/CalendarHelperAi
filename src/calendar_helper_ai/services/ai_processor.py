"""Calendar-only multimodal extraction with bounded, privacy-safe provider errors."""
import json
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app
from openai import APIConnectionError, APIStatusError, APITimeoutError

from ..observability import log_event, safe_identifier
from ..prompts import CALENDAR_SYSTEM_PROMPT, CORRECTION_SYSTEM_PROMPT
from .events import normalize_event


class ProcessingError(Exception):


    def __init__(self, kind, message, status=502):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.status = status


class SafetyValidationError(ProcessingError):


    def __init__(self):
        super().__init__('unsupported_request', 'This helper can extract or update calendar events. Add an appointment image or event details.', 400)


def get_openai_client():
    client = current_app.extensions.get('openai')
    if client is None:
        raise ProcessingError('provider_configuration', 'Event processing is temporarily unavailable. Please try again later.', 503)
    return client


def call_model(messages, stage):
    started = time.monotonic()
    try:
        response = get_openai_client().chat.completions.create(
            model='gpt-4o', messages=messages, response_format={'type': 'json_object'},
            timeout=45)
    except ProcessingError:
        raise
    except Exception as error:
        status = getattr(error, 'status_code', None)
        code = safe_identifier(getattr(error, 'code', None))
        kind, http_status = 'provider_error', 502
        message = 'The event service could not complete this request. Please try again.'
        if isinstance(error, APITimeoutError):
            kind, http_status = 'provider_timeout', 504
            message = 'The event service took too long. Your details are still here; please try again.'
        elif isinstance(error, APIConnectionError):
            kind, http_status = 'provider_connection', 503
        elif isinstance(error, APIStatusError):
            if status in (401, 403):
                kind, http_status = 'provider_authentication', 503
                message = 'Event processing is temporarily unavailable. Please try again later.'
            elif status == 429:
                kind = 'provider_quota' if code == 'insufficient_quota' else 'provider_rate_limit'
                http_status = 503 if kind == 'provider_quota' else 429
                message = 'The event service is temporarily at capacity. Please try again later.'
        log_event('provider_failed', logging.ERROR, stage=stage, error_type=kind,
                  exception_class=type(error).__name__, provider_status=status,
                  provider_code=code, provider_request_id=safe_identifier(getattr(error, 'request_id', None)),
                  elapsed_ms=round((time.monotonic() - started) * 1000))
        raise ProcessingError(kind, message, http_status) from None
    provider_id = safe_identifier(getattr(response, '_request_id', None))
    try:
        parsed = json.loads(response.choices[0].message.content)
        if not isinstance(parsed, dict) or parsed.get('outcome') not in {'events', 'no_events', 'unsupported'}:
            raise ValueError('Invalid outcome')
        if parsed['outcome'] == 'unsupported':
            raise SafetyValidationError()
        if not isinstance(parsed.get('events'), list):
            raise ValueError('Invalid events')
        if parsed['outcome'] == 'no_events' and parsed['events']:
            raise ValueError('Conflicting outcome')
        if any(not isinstance(event, dict) or event.get('time_status') not in {'timed', 'missing', 'all_day'} for event in parsed['events']):
            raise ValueError('Missing time classification')
        events = [normalize_event(event) for event in parsed['events']]
    except SafetyValidationError:
        log_event('request_rejected', logging.WARNING, stage=stage, outcome='unsupported', provider_request_id=provider_id)
        raise
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        log_event('provider_failed', logging.ERROR, stage=stage, error_type='invalid_model_response', provider_request_id=provider_id)
        raise ProcessingError('invalid_model_response', 'We could not read the event service response. Your details are still here; please try again.') from None
    log_event('provider_completed', stage=stage, outcome=parsed['outcome'], event_count=len(events),
              provider_request_id=provider_id, elapsed_ms=round((time.monotonic() - started) * 1000), model='gpt-4o')
    return events


def process_image_and_text(image_data_list=None, text=None, timezone=None):
    zone = timezone or 'UTC'
    now = datetime.now(ZoneInfo(zone))
    images = image_data_list or []
    content = [{'type': 'text', 'text': 'Extract calendar events from the attached images and supplementary instructions. '
                f'Instructions: {text or "Find appointments in these images."}'}]
    for image in images:
        content.append({'type': 'image_url', 'image_url': {'url': f"data:{image.get('mime_type', 'image/jpeg')};base64,{image['data']}"}})
    log_event('processing_started', stage='extract', image_count=len(images))
    return call_model([
        {'role': 'system', 'content': CALENDAR_SYSTEM_PROMPT + f'\nCurrent local date: {now.date()}. User timezone: {zone}.'},
        {'role': 'user', 'content': content}], 'extract')


def process_corrections(text, existing_events, timezone=None):
    normalized = [normalize_event(event) for event in existing_events]
    updated = call_model([
        {'role': 'system', 'content': CORRECTION_SYSTEM_PROMPT + f'\nUser timezone: {timezone or "UTC"}.'},
        {'role': 'user', 'content': json.dumps({'current_events': normalized, 'correction': text})}], 'correct')
    # An unrelated correction cannot silently approve an existing guessed duration.
    for event in updated:
        for previous in normalized:
            if (event.get('start_time'), event.get('end_time')) == (previous.get('start_time'), previous.get('end_time')) and previous.get('duration_assumed'):
                event['duration_assumed'] = True
                event['duration_confirmed'] = previous.get('duration_confirmed') is True
                break
    return updated
