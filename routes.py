import os
import base64
from flask import request, jsonify, render_template
from app import app
from utils.ai_processor import process_image_and_text, process_corrections, SafetyValidationError
from utils.calendar import generate_ics
from utils.location_service import get_client_ip, get_location_from_ip
from utils.config import MAX_IMAGE_SIZE, ALLOWED_IMAGE_TYPES, APP_VERSION
import uuid

from utils.ai_processor import SafetyValidationError

@app.route('/api/config')
def get_config():
    debug_logging = os.environ.get('DEBUG_LOGGING', 'false').lower() == 'true'
    return jsonify({
        'maxImageSize': MAX_IMAGE_SIZE,
        'allowedImageTypes': list(ALLOWED_IMAGE_TYPES),
        'version': APP_VERSION,
        'debug_logging': debug_logging
    })

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    try:
        images = request.files.getlist('image')
        text = request.form.get('text', '').strip()
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
                'user_message': 'No events were found. Please try again.'
            }), 400

        app.logger.info(f"Successfully processed request with {len(result)} events")
        return jsonify({'success': True, 'events': result})

    except SafetyValidationError as e:
        app.logger.warning(f"Safety validation error: {str(e)}")
        return jsonify({
            'success': False,
            'error_type': 'unsafe_prompt',
            'user_message': str(e)
        }), 400
    except Exception as e:
        app.logger.error(f"Unexpected error in process: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': 'processing_error',
            'user_message': 'An unexpected error occurred. Please try again.'
        }), 500

@app.route('/correct', methods=['POST'])
def correct():
    try:
        data = request.json
        correction = data.get('correction')
        events = data.get('current_events', [])
        timezone = request.headers.get('X-Timezone', 'UTC')

        app.logger.debug(f"Current events before correction: {events}")
        updated_events = process_corrections(correction, events, timezone)
        app.logger.debug(f"Updated events after correction: {updated_events}")
        return jsonify({'success': True, 'events': updated_events})

    except SafetyValidationError as e:
        error_message = str(e)
        app.logger.warning(f"Safety validation error: {error_message}")
        return jsonify({
            'success': False,
            'error_type': 'unsafe_prompt',
            'user_message': error_message
        }), 400

    except Exception as e:
        app.logger.error(f"Process error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': 'processing_error', 
            'user_message': 'An unexpected error occurred. Please try again.'
        }), 500

@app.route('/download-ics', methods=['POST'])
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
        app.logger.error(f"Error generating ICS: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': 'processing_error',
            'user_message': 'Error generating calendar file'
        }), 500

