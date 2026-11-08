"""HTTP boundary validation and stable, payload-free error responses."""
import base64
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, request, jsonify, render_template
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from .services.ai_processor import process_image_and_text, process_corrections, ProcessingError
from .services.events import EventValidationError, resolve_event_time
from .services.calendar import generate_ics
from .observability import log_event
from .config import MAX_IMAGE_SIZE, ALLOWED_IMAGE_TYPES, APP_VERSION

bp = Blueprint('calendar', __name__)


def user_timezone():
    timezone = request.headers.get('X-Timezone', 'UTC')
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise EventValidationError('Choose a valid calendar timezone.') from None
    return timezone


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise EventValidationError('Send a valid calendar request.')
    return data


@bp.route('/api/config')
def get_config():
    from flask import current_app
    return jsonify(maxImageSize=MAX_IMAGE_SIZE, allowedImageTypes=list(ALLOWED_IMAGE_TYPES),
                   version=APP_VERSION, debug_logging=current_app.config['DEBUG_LOGGING'])


@bp.route('/')
def index():
    return render_template('index.html', app_version=APP_VERSION)


@bp.route('/favicon.ico')
def favicon():
    from flask import current_app
    return current_app.send_static_file('icons/favicon.ico')


@bp.route('/process', methods=['POST'])
def process():
    images = request.files.getlist('image')
    text = request.form.get('text', '').strip()
    if not text and not images:
        raise EventValidationError('Choose an image or enter an event name, date, and time.')
    if len(images) > 5:
        raise EventValidationError('Please select up to 5 images only.')
    image_data_list = []
    for image in images:
        data = image.read(MAX_IMAGE_SIZE + 1)
        if len(data) > MAX_IMAGE_SIZE:
            # Filenames can contain personal data; do not put them in logs.
            raise EventValidationError(f'Please limit each image to 4mb. {image.filename} is too large.')
        if image.content_type not in ALLOWED_IMAGE_TYPES or not data:
            raise EventValidationError('Choose a nonempty PNG, JPG, JPEG, or TIFF image.')
        image_data_list.append({'data': base64.b64encode(data).decode('ascii'),
                                'filename': image.filename, 'mime_type': image.content_type})
    result = process_image_and_text(image_data_list, text, user_timezone())
    if not result:
        return jsonify(success=False, error_type='no_events',
                       user_message='No appointments were found. Try a clearer image or add event details.'), 400
    return jsonify(success=True, events=result)


@bp.route('/correct', methods=['POST'])
def correct():
    data = json_body()
    correction = data.get('correction')
    events = data.get('current_events')
    if not isinstance(correction, str) or not correction.strip() or not isinstance(events, list) or not events:
        raise EventValidationError('Provide a correction and the events to update.')
    result = process_corrections(correction.strip(), events, user_timezone())
    if not result:
        return jsonify(success=False, error_type='no_events', user_message='No updated events were returned. Your previous events are unchanged.'), 400
    return jsonify(success=True, events=result)


@bp.route('/resolve-time', methods=['POST'])
def resolve_time():
    data = json_body()
    result = resolve_event_time(data.get('event'), data.get('mode'), user_timezone(),
                                data.get('start_local'), data.get('end_local'), data.get('date'))
    return jsonify(success=True, event=result)


@bp.route('/download-ics', methods=['POST'])
def download_ics():
    events = json_body().get('events')
    if not isinstance(events, list) or not events:
        raise EventValidationError('No events found to download.')
    return jsonify(success=True, ics_content=generate_ics(events, user_timezone()))


@bp.errorhandler(ProcessingError)
def processing_error(error):
    log_event('processing_failed', logging.WARNING, error_type=error.kind, status=error.status)
    return jsonify(success=False, error_type=error.kind, user_message=error.message), error.status


@bp.errorhandler(EventValidationError)
def validation_error(error):
    log_event('validation_failed', logging.WARNING, error_type='validation_error')
    return jsonify(success=False, error_type='validation_error', user_message=str(error)), 400


@bp.app_errorhandler(RequestEntityTooLarge)
def handle_large_request(error):
    return jsonify(success=False, error_type='validation_error', user_message='Choose up to 5 images, no larger than 4 MB each.'), 413


@bp.errorhandler(Exception)
def unexpected_error(error):
    if isinstance(error, (ValueError, TypeError, KeyError, AttributeError)):
        return jsonify(success=False, error_type='validation_error', user_message='Check the event dates and times, then try again.'), 400
    if isinstance(error, HTTPException):
        return jsonify(success=False, error_type='validation_error', user_message='The calendar request could not be read.'), error.code
    log_event('unexpected_failure', logging.ERROR, error_type='internal_error', exception_class=type(error).__name__)
    return jsonify(success=False, error_type='internal_error', user_message='An unexpected error occurred. Please try again.'), 500
