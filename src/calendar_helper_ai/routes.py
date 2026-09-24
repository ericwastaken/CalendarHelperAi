import base64
from flask import Blueprint, current_app, request, jsonify, render_template
from werkzeug.exceptions import RequestEntityTooLarge
from .services.ai_processor import process_image_and_text, process_corrections, SafetyValidationError
from .services.calendar import generate_ics
from .config import MAX_IMAGE_SIZE, ALLOWED_IMAGE_TYPES, APP_VERSION

bp = Blueprint("calendar", __name__)


@bp.route('/api/config')
def get_config():
    debug_logging = current_app.config['DEBUG_LOGGING']
    return jsonify({
        'maxImageSize': MAX_IMAGE_SIZE,
        'allowedImageTypes': list(ALLOWED_IMAGE_TYPES),
        'version': APP_VERSION,
        'debug_logging': debug_logging
    })


@bp.route('/')
def index():
    return render_template('index.html', app_version=APP_VERSION)


@bp.route('/favicon.ico')
def favicon():
    return current_app.send_static_file('icons/favicon.ico')


@bp.route('/process', methods=['POST'])
def process():
    try:
        images = request.files.getlist('image')
        text = request.form.get('text', '').strip()
        if not text and not images:
            return jsonify(success=False, error_type='validation_error', user_message='Choose an image or enter an event name, date, and time.'), 400
        if not text:
            text = "Extract the events in these images."

        if len(images) > 5:
            return jsonify({
                'success': False,
                'error_type': 'validation_error',
                'user_message': 'Please select up to 5 images only'
            }), 400

        image_data_list = []
        total_size = 0
        
        if images:
            for image in images:
                # Validate file size
                image.seek(0, 2)
                size = image.tell()
                image.seek(0)
                total_size += size

                if size > MAX_IMAGE_SIZE:
                    return jsonify({
                        'success': False,
                        'error_type': 'validation_error',
                        'user_message': f'Please limit each image to 4mb. {image.filename} is too large.'
                    }), 400

                if image.content_type not in ALLOWED_IMAGE_TYPES:
                    return jsonify({
                        'success': False,
                        'error_type': 'validation_error',
                        'user_message': f'Invalid file type: {image.filename}. Please use png, jpg, jpeg, or tiff images only.'
                    }), 400

                # Store image data with filename for tracking
                image_data_list.append({
                    'data': base64.b64encode(image.read()).decode('utf-8'),
                    'filename': image.filename
                })

        if total_size > (MAX_IMAGE_SIZE * 5):
            return jsonify({
                'success': False,
                'error_type': 'validation_error',
                'user_message': 'Total size of all images exceeds the limit'
            }), 400

        timezone = request.headers.get('X-Timezone', 'UTC')
        result = process_image_and_text(image_data_list, text, timezone)

        if not result:
            return jsonify({
                'success': False,
                'error_type': 'no_events',
                'user_message': 'Try a clearer image, or add the event name, date, and time.'
            }), 400

        current_app.logger.info(f"Successfully processed request with {len(result)} events")
        return jsonify({'success': True, 'events': result})

    except RequestEntityTooLarge:
        raise
    except SafetyValidationError as e:
        current_app.logger.warning(f"Safety validation error: {str(e)}")
        return jsonify({
            'success': False,
            'error_type': 'unsafe_prompt',
            'user_message': str(e)
        }), 400
    except Exception as e:
        current_app.logger.error(f"Unexpected error in process: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': 'processing_error',
            'user_message': 'An unexpected error occurred. Please try again.'
        }), 500


@bp.route('/correct', methods=['POST'])
def correct():
    try:
        data = request.json
        correction = (data.get('correction') or '').strip()
        events = data.get('current_events', [])
        if not correction or not isinstance(events, list) or not events:
            return jsonify(success=False, error_type='validation_error', user_message='Provide a correction and the events to update.'), 400
        timezone = request.headers.get('X-Timezone', 'UTC')

        current_app.logger.debug(f"Current events before correction: {events}")
        updated_events = process_corrections(correction, events, timezone)
        current_app.logger.debug(f"Updated events after correction: {updated_events}")
        return jsonify({'success': True, 'events': updated_events})

    except SafetyValidationError as e:
        error_message = str(e)
        current_app.logger.warning(f"Safety validation error: {error_message}")
        return jsonify({
            'success': False,
            'error_type': 'unsafe_prompt',
            'user_message': error_message
        }), 400

    except Exception as e:
        current_app.logger.error(f"Process error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': 'processing_error', 
            'user_message': 'An unexpected error occurred. Please try again.'
        }), 500


@bp.route('/download-ics', methods=['POST'])
def download_ics():
    try:
        events = request.json.get('events', [])
        if not events:
            return jsonify({
                'success': False,
                'error_type': 'no_events',
                'user_message': 'No events found to download'
            }), 400

        timezone = request.headers.get('X-Timezone', 'UTC')
        ics_content = generate_ics(events, timezone)
        return jsonify({'success': True, 'ics_content': ics_content})

    except Exception as e:
        current_app.logger.error(f"Error generating ICS: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': 'processing_error',
            'user_message': 'Error generating calendar file'
        }), 500


@bp.app_errorhandler(RequestEntityTooLarge)
def handle_large_request(error):
    return jsonify(success=False, error_type='validation_error', user_message='Choose up to 5 images, no larger than 4 MB each.'), 413
