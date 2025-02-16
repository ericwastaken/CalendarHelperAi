import os
import base64
from flask import request, jsonify, render_template, session
from app import app
from utils.ai_processor import process_image_and_text, process_corrections, SafetyValidationError
from utils.calendar import generate_ics
from utils.location_service import get_client_ip, get_location_from_ip
from utils.config import MAX_IMAGE_SIZE, ALLOWED_IMAGE_TYPES
import uuid

from utils.ai_processor import SafetyValidationError

@app.route('/api/config')
def get_config():
    return jsonify({
        'maxImageSize': MAX_IMAGE_SIZE,
        'allowedImageTypes': list(ALLOWED_IMAGE_TYPES)
    })

@app.route('/')
def index():
    session['session_id'] = str(uuid.uuid4())
    ip = get_client_ip()
    location = get_location_from_ip(ip)
    if location:
        session['location'] = location
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    try:
        image = request.files.get('image')
        text = request.form.get('text', '').strip()
        if not text:
            text = "Extract the events in this image."

        if image:
            # Validate file size
            image.seek(0, 2)
            size = image.tell()
            image.seek(0)

            if size > MAX_IMAGE_SIZE:
                return jsonify({
                    'success': False,
                    'error_type': 'validation_error',
                    'user_message': 'Please limit your image to 4mb'
                }), 400

            if image.content_type not in ALLOWED_IMAGE_TYPES:
                return jsonify({
                    'success': False,
                    'error_type': 'validation_error',
                    'user_message': 'Please use png, jpg, jpeg, or tiff images only'
                }), 400

            image_data = base64.b64encode(image.read()).decode('utf-8')
        else:
            image_data = None

        timezone = request.headers.get('X-Timezone', 'UTC')
        result = process_image_and_text(image_data, text, timezone)

        if not result:
            return jsonify({
                'success': False,
                'error_type': 'no_events',
                'user_message': 'No events were found. Please try again.'
            }), 400

        session['current_events'] = result
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
        correction = request.json.get('correction')
        events = session.get('current_events', [])
        timezone = request.headers.get('X-Timezone', 'UTC')

        updated_events = process_corrections(correction, events, timezone)
        session['current_events'] = updated_events
        
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
        events = session.get('current_events', [])
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

@app.route('/clear-session', methods=['POST'])
def clear_session():
    session.clear()
    session['session_id'] = str(uuid.uuid4())
    return jsonify({'success': True})