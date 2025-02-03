import os
import base64
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

        if image:
            image_data = base64.b64encode(image.read()).decode('utf-8')
        else:
            image_data = None

        # Process with AI
        events = process_image_and_text(image_data, text)

        # Store in session
        session['current_events'] = events

        return jsonify({
            'success': True,
            'events': events
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/correct', methods=['POST'])
def correct():
    try:
        correction = request.json.get('correction')
        events = session.get('current_events', [])

        # Process correction with AI
        updated_events = process_image_and_text(None, correction, events)

        # Update session
        session['current_events'] = updated_events

        return jsonify({
            'success': True,
            'events': updated_events
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/download-ics', methods=['POST'])
def download_ics():
    try:
        events = session.get('current_events', [])
        if not events:
            return jsonify({'success': False, 'error': 'No events found'}), 400

        ics_content = generate_ics(events)

        return jsonify({
            'success': True,
            'ics_content': ics_content
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/clear-session', methods=['POST'])
def clear_session():
    session.clear()
    session['session_id'] = str(uuid.uuid4())
    return jsonify({'success': True})