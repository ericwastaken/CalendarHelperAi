import os
import base64
import logging
from flask import request, jsonify, render_template, session
from app import app
from utils.ai_processor import process_image_and_text
from utils.calendar import generate_ics
import uuid

@app.route('/')
def index():
    session['session_id'] = str(uuid.uuid4())
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    try:
        image = request.files.get('image')
        text = request.form.get('text', '')

        logging.debug(f"Processing request - Image: {'Yes' if image else 'No'}, Text: {text}")

        if not text and not image:
            raise ValueError("Please provide either text or an image with text")

        if image:
            image_data = base64.b64encode(image.read()).decode('utf-8')
        else:
            image_data = None

        # Process with AI
        events = process_image_and_text(image_data, text)

        # Validate events
        if not events or not isinstance(events, list):
            raise ValueError("No valid events could be extracted from the provided input")

        # Store in session
        session['current_events'] = events

        logging.debug(f"Successfully processed events: {events}")
        return jsonify({
            'success': True,
            'events': events
        })

    except Exception as e:
        logging.error(f"Error in process route: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/correct', methods=['POST'])
def correct():
    try:
        correction = request.json.get('correction')
        if not correction:
            raise ValueError("No correction text provided")

        events = session.get('current_events', [])
        logging.debug(f"Processing correction with existing events: {events}")

        # Process correction with AI
        updated_events = process_image_and_text(None, correction, events)

        if not updated_events:
            raise ValueError("No events could be extracted from the correction")

        # Update session
        session['current_events'] = updated_events

        logging.debug(f"Successfully processed correction: {updated_events}")
        return jsonify({
            'success': True,
            'events': updated_events
        })
    except Exception as e:
        logging.error(f"Error in correct route: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/download-ics', methods=['POST'])
def download_ics():
    try:
        events = session.get('current_events', [])
        if not events:
            raise ValueError('No events found')

        ics_content = generate_ics(events)

        return jsonify({
            'success': True,
            'ics_content': ics_content
        })
    except Exception as e:
        logging.error(f"Error in download_ics route: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/clear-session', methods=['POST'])
def clear_session():
    try:
        session.clear()
        session['session_id'] = str(uuid.uuid4())
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"Error in clear_session route: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400