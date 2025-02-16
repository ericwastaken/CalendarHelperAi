import os
import base64
from flask import request, jsonify, render_template, session
from app import app
from utils.ai_processor import process_image_and_text, process_corrections
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

        try:
            result = process_image_and_text(image_data, text, timezone)

            # Check if there was a safety validation error
            if not result or not isinstance(result, list):
                raise Exception("invalid_result_format")

            # Store in session and return success
            session['current_events'] = result
            return jsonify({
                'success': True,
                'events': result
            })

        except Exception as e:
            error_type = str(e)
            app.logger.error(f"Process error: {error_type}", exc_info=True)

            # Handle safety check errors
            if isinstance(e, Exception) and str(e).startswith('unsafe_prompt:'):
                try:
                    reason = str(e).split(':', 1)[1].strip()
                    return jsonify({
                        'success': False,
                        'error_type': 'unsafe_prompt',
                        'error': 'Your request was rejected for safety reasons.',
                        'reason': reason
                    }), 400
                except:
                    return jsonify({
                        'success': False,
                        'error_type': 'unsafe_prompt',
                        'error': 'Your request was rejected for safety reasons.'
                    }), 400

            error_messages = {
                "no_events_found": {
                    'error_type': 'no_events',
                    'error': 'No events were found in the image. Please try with a different photo that contains calendar events.'
                },
                "invalid_result_format": {
                    'error_type': 'processing_error',
                    'error': 'Invalid result format received'
                },
                "initial_process_failed": {
                    'error_type': 'processing_error',
                    'error': 'Error processing the request'
                }
            }

            response_data = error_messages.get(error_type, {
                'error_type': 'processing_error',
                'error': 'An unexpected error occurred'
            })
            response_data['success'] = False

            return jsonify(response_data), 400

        # Store in session
        session['current_events'] = result

        return jsonify({
            'success': True,
            'events': result
        })
    except Exception as e:
        error_type = str(e)
        app.logger.error(f"Process error in session {session.get('session_id', 'unknown')}: {error_type}", exc_info=True)

        if error_type == "no_events_found":
            return jsonify({
                'success': False,
                'error_type': 'no_events_found',
                'user_message': 'Error processing your image. Make sure there are events in the image and perhaps try with a different photo.'
            }), 400

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
        updated_events = process_corrections(correction, events, timezone)

        # Update session
        session['current_events'] = updated_events

        return jsonify({
            'success': True,
            'events': updated_events
        })
    except Exception as e:
        error_type = str(e)
        app.logger.error(f"Correction error: {error_type}", exc_info=True)
        
        if isinstance(e, Exception) and str(e).startswith('unsafe_prompt:'):
            reason = str(e).split(':', 1)[1].strip() if ':' in str(e) else 'Unknown safety violation'
            return jsonify({
                'success': False,
                'error_type': 'unsafe_prompt',
                'error': 'Your request was rejected for safety reasons.',
                'reason': reason,
                'details': 'Please ensure your correction request is related to calendar events.'
            }), 400
        elif error_type in ["initial_process_failed", "address_lookup_failed"]:
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