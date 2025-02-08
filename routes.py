import os
import base64
from flask import request, jsonify, render_template, session
from app import app
from utils.ai_processor import process_image_and_text
from utils.calendar import generate_ics
from utils.location_service import get_client_ip, get_location_from_ip
from utils.config import MAX_IMAGE_SIZE, ALLOWED_IMAGE_TYPES
import uuid

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
            from utils.config import MAX_IMAGE_SIZE, ALLOWED_IMAGE_TYPES
            
            # Validate file size
            image.seek(0, 2)  # Seek to end
            size = image.tell()
            image.seek(0)  # Reset file pointer
            
            if size > MAX_IMAGE_SIZE:
                return jsonify({
                    'success': False,
                    'error_type': 'unsafe_prompt',
                    'error': 'Please limit your image to 4mb'
                }), 400

            # Validate file type
            if image.content_type not in ALLOWED_IMAGE_TYPES:
                return jsonify({
                    'success': False,
                    'error_type': 'unsafe_prompt',
                    'error': 'Please use png, jpg, jpeg, or tiff images only'
                }), 400

            image_data = base64.b64encode(image.read()).decode('utf-8')
        else:
            image_data = None

        # Get timezone from request
        timezone = request.headers.get('X-Timezone', 'UTC')
        # Process with AI
        result = process_image_and_text(image_data, text, None, timezone)
        
        # Check if there was a safety validation error
        if isinstance(result, dict) and 'error' in result:
            return jsonify({
                'success': False,
                'error_type': 'unsafe_prompt',
                'user_message': result['error'],
                'reason': result.get('reason', '')
            }), 400

        # Store in session
        session['current_events'] = result

        return jsonify({
            'success': True,
            'events': result
        })
    except Exception as e:
        error_type = str(e)
        app.logger.error(f"Process error in session {session.get('session_id', 'unknown')}: {error_type}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': error_type,
            'user_message': 'There was an error. Please try again in a few seconds.'
        }), 400

@app.route('/correct', methods=['POST'])
def correct():
    try:
        correction = request.json.get('correction')
        events = session.get('current_events', [])
        timezone = request.headers.get('X-Timezone', 'UTC')

        # Process correction with AI
        updated_events = process_image_and_text(None, correction, events, timezone)

        # Update session
        session['current_events'] = updated_events

        return jsonify({
            'success': True,
            'events': updated_events
        })
    except Exception as e:
        error_type = str(e)
        app.logger.error(f"Correction error: {error_type}", exc_info=True)
        if error_type in ["initial_process_failed", "address_lookup_failed"]:
            return jsonify({
                'success': False,
                'error_type': error_type,
                'user_message': 'There was an error. Please try again in a few seconds.'
            }), 400
        return jsonify({
            'success': False,
            'error_type': 'unknown_error',
            'user_message': 'There was an error. Please try again in a few seconds.'
        }), 400

@app.route('/download-ics', methods=['POST'])
def download_ics():
    try:
        events = session.get('current_events', [])
        if not events:
            return jsonify({'success': False, 'error': 'No events found'}), 400

        timezone = request.headers.get('X-Timezone', 'UTC')
        ics_content = generate_ics(events, timezone)

        return jsonify({
            'success': True,
            'ics_content': ics_content
        })
    except Exception as e:
        error_type = str(e)
        app.logger.error(f"Download ICS error: {error_type}", exc_info=True)
        if error_type in ["initial_process_failed", "address_lookup_failed"]:
            return jsonify({
                'success': False,
                'error_type': error_type,
                'user_message': 'There was an error. Please try again in a few seconds.'
            }), 400
        return jsonify({
            'success': False,
            'error_type': 'unknown_error',
            'user_message': 'There was an error. Please try again in a few seconds.'
        }), 400

@app.route('/clear-session', methods=['POST'])
def clear_session():
    session.clear()
    session['session_id'] = str(uuid.uuid4())
    return jsonify({'success': True})