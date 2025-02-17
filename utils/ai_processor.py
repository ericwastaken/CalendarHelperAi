import os
import logging
from openai import OpenAI
import json
from datetime import datetime, timedelta

class SafetyValidationError(Exception):
    """Custom exception for safety validation failures"""
    pass

# Configure OpenAI logging based on environment variables
openai_http_level = os.environ.get('OPENAI_HTTP_CLIENT_LEVEL', 'ERROR').upper()
openai_api_level = os.environ.get('OPENAI_API_LEVEL', 'ERROR').upper()

# Set OpenAI logging levels
logging.getLogger("openai._base_client").setLevel(getattr(logging, openai_http_level, logging.ERROR))
logging.getLogger("openai._streaming").setLevel(getattr(logging, openai_api_level, logging.ERROR))
logging.getLogger("openai._http_client").setLevel(getattr(logging, openai_http_level, logging.ERROR))

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")
if not OPENAI_API_KEY.startswith('sk-'):
    raise ValueError("Invalid OpenAI API key format")
try:
    client = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    logging.error(f"Error initializing OpenAI client: {str(e)}")
    raise ValueError("Failed to initialize OpenAI client")

def validate_prompt_safety(text):
    """Validate if the prompt is safe and calendar-related."""
    from utils.prompts import SAFETY_VALIDATION_PROMPT
    messages = [
        {"role": "system", "content": SAFETY_VALIDATION_PROMPT},
        {"role": "user", "content": f"Is this prompt safe and calendar-related? Prompt: {text}"}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        debug_log(f"Safety validation result: {result}")
        return result["is_safe"], result["reason"]
    except Exception as e:
        debug_log(f"Error in safety validation: {e}")
        return False, "Safety validation failed"


# Set up debug logging based on environment variable
DEBUG_LOGGING = os.environ.get('DEBUG_LOGGING', 'false').lower() == 'true'

def debug_log(message):
    if DEBUG_LOGGING:
        logging.debug(message)

def lookup_address_details(location):
    """Look up detailed address information using OpenAI."""
    if not location or location.lower() == 'unknown':
        return None

    from utils.prompts import ADDRESS_LOOKUP_PROMPT
    messages = [
        {"role": "system", "content": ADDRESS_LOOKUP_PROMPT},
        {"role": "user", "content": f"Look up the full address for: {location}"}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )
        response_content = response.choices[0].message.content
        try:
            parsed_content = json.loads(response_content)
            debug_log(f"Address lookup response:\n{json.dumps(parsed_content, indent=2)}")
        except json.JSONDecodeError:
            debug_log(f"Address lookup response (invalid JSON):\n{response_content}")
        return json.loads(response_content)
    except Exception as e:
        debug_log(f"Error looking up address: {e}")
        return None

def process_event_dates(event):
    """Helper function to process and validate event dates"""
    start_time = event.get('start_time', '')
    end_time = event.get('end_time')

    start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    if not end_time:
        end_dt = start_dt + timedelta(hours=1)
        event['end_time'] = end_dt.isoformat()
    else:
        datetime.fromisoformat(end_time.replace('Z', '+00:00'))

    return event

def process_location_details(event):
    """Helper function to process location details for an event"""
    event['location_name'] = event.get('location_name', '').strip()
    event['location_address'] = event.get('location_address', '').strip()

    if event['location_name'] or event['location_address']:
        location_query = f"{event['location_name']} {event['location_address']}".strip()
        address_details = lookup_address_details(location_query)
        if address_details:
            event['location_details'] = address_details
            full_address_parts = [
                address_details.get('street_address'),
                address_details.get('city'),
                address_details.get('state'),
                address_details.get('postal_code'),
                address_details.get('country')
            ]
            event['location_address'] = ', '.join(filter(None, full_address_parts))
            event['location'] = f"{event['location_name']} - {event['location_address']}" if event['location_name'] else event['location_address']
    return event

def process_corrections(text, existing_events, timezone=None):
    try:
        # First validate the prompt safety
        is_safe, reason = validate_prompt_safety(text)
        if not is_safe:
            debug_log(f"Unsafe prompt rejected: {reason}")
            raise SafetyValidationError(reason)

        if not existing_events:
            debug_log("No existing events to process")
            raise Exception("no_events_found")

        formatted_events = []
        for event in existing_events:
            formatted_event = {
                "title": event.get('title', ''),
                "description": event.get('description', ''),
                "start_time": event.get('start_time', ''),
                "end_time": event.get('end_time', ''),
                "location_name": event.get('location_name', ''),
                "location_address": event.get('location_address', '')
            }
            formatted_events.append(formatted_event)
        debug_log(f"Formatted events for correction: {json.dumps(formatted_events, indent=2)}")

        from utils.prompts import CORRECTION_SYSTEM_PROMPT, CORRECTION_USER_PROMPT
        correction_prompt = CORRECTION_USER_PROMPT.format(
            events_json=json.dumps(formatted_events, indent=2),
            correction_text=text
        )

        messages = [
            {"role": "system", "content": CORRECTION_SYSTEM_PROMPT},
            {"role": "user", "content": correction_prompt}
        ]

        debug_log("Processing correction with correction prompt")
        debug_log(f"Sending messages to OpenAI: {json.dumps(messages, indent=2)}")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )

        response_content = response.choices[0].message.content
        debug_log(f"OpenAI response: {response_content}") # Added logging here

        parsed_response = json.loads(response_content)
        events = parsed_response.get('events', [])

        if not events:
            debug_log("No events found in response")
            raise Exception("no_events_found")

        # Process dates and locations for corrections
        for event in events:
            event = process_event_dates(event)
            event = process_location_details(event)

        debug_log(f"Final processed events:\n{json.dumps({'events': events}, indent=2)}")
        return events
    except Exception as e:
        error_type = str(e)
        logging.error(f"Error in correction process: {error_type}")
        raise

def process_image_and_text(image_data=None, text=None, timezone=None):
    try:
        # Validate prompt safety
        is_safe, reason = validate_prompt_safety(text)
        if not is_safe:
            debug_log(f"Unsafe prompt rejected: {reason}")
            raise SafetyValidationError(reason)

        # Prepare current date/time context
        current_dt = datetime.now()
        if timezone:
            from zoneinfo import ZoneInfo
            current_dt = datetime.now(ZoneInfo(timezone))

        # Get system prompt and insert current context
        from utils.prompts import CALENDAR_SYSTEM_PROMPT
        from flask import session

        # Insert date context
        location = session.get('location', {})
        from utils.prompts import DATE_PROMPT_TEMPLATE, LOCATION_PROMPT_TEMPLATE

        current_date_prompt = DATE_PROMPT_TEMPLATE.format(
            year=current_dt.year,
            month=current_dt.month,
            day=current_dt.day,
            time=current_dt.strftime('%H:%M'),
            timezone=timezone or 'UTC'
        )

        # Insert location context
        current_location_prompt = LOCATION_PROMPT_TEMPLATE.format(
            city=location.get('city', 'unknown'),
            region=location.get('region', 'unknown'),
            country=location.get('country', 'unknown')
        )

        system_message = CALENDAR_SYSTEM_PROMPT.replace('{current_date_prompt}', current_date_prompt).replace('{current_location_prompt}', current_location_prompt)

        # Prepare messages for OpenAI
        messages = [{"role": "system", "content": system_message}]

        if image_data and text:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Extract calendar events from this image and text: {text}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ]
            })
        elif text:
            messages.append({
                "role": "user",
                "content": f"Extract calendar events from this text: {text}"
            })

        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )

        # Parse and validate response
        if not response.choices or not response.choices[0].message.content:
            raise Exception("initial_process_failed")

        response_content = response.choices[0].message.content
        try:
            parsed_content = json.loads(response_content)
            debug_log(f"OpenAI response content:\n{json.dumps(parsed_content, indent=2)}")
        except json.JSONDecodeError:
            debug_log(f"OpenAI response content (invalid JSON):\n{response_content}")
        events = json.loads(response_content).get('events', [])
        try:
            debug_log(f"Extracted events:\n{json.dumps(events, indent=2)}")
        except json.JSONDecodeError:
            debug_log(f"Extracted events (invalid JSON):\n{events}")
        if not events:
            raise Exception("no_events_found")

        # Process dates and locations
        for event in events:
            # Process dates and location details
            event = process_event_dates(event)
            event = process_location_details(event)

        debug_log(f"Final processed events:\n{json.dumps({'events': events}, indent=2)}")
        return events

    except SafetyValidationError as e:
        logging.error(f"Safety validation error in process_image_and_text: {str(e)}")
        raise
    except Exception as e:
        error_type = str(e)
        logging.error(f"Error in process_image_and_text: {error_type}")
        if error_type in ["no_events_found", "address_lookup_failed"]:
            raise
        raise Exception("initial_process_failed") from e