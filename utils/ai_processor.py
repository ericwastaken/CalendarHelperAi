import os
import logging
from openai import OpenAI
import json
from datetime import datetime, timedelta

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

    messages = [
        {"role": "system", "content": "You are a location lookup assistant. For the given location, return the full address in JSON format with these fields: street_address, city, state, country, postal_code. Use null for unknown fields."},
        {"role": "user", "content": f"Look up the full address for: {location}"}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        debug_log(f"Error looking up address: {e}")
        return None

def process_image_and_text(image_data=None, text=None, existing_events=None, timezone=None):
    try:
        # First validate the prompt safety
        is_safe, reason = validate_prompt_safety(text)
        if not is_safe:
            debug_log(f"Unsafe prompt rejected: {reason}")
            return {"error": "There was an issue with your correction."}

        messages = []
        
        # Handle corrections first
        if existing_events and text:
            debug_log("Processing correction request")
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

            from utils.prompts import CORRECTION_SYSTEM_PROMPT, CORRECTION_USER_PROMPT
            correction_prompt = CORRECTION_USER_PROMPT.format(
                events_json=json.dumps(formatted_events, indent=2),
                correction_text=text
            )
            messages = [
                {"role": "system", "content": CORRECTION_SYSTEM_PROMPT},
                {"role": "user", "content": correction_prompt}
            ]
        else:
            # Handle initial extraction
            current_dt = datetime.now()
            if timezone:
                from zoneinfo import ZoneInfo
                current_dt = datetime.now(ZoneInfo(timezone))

            current_date_prompt = f"""- If the year is not provided, use {current_dt.year}.
- If the month is not provided, use month {current_dt.month}.
- If the day is not provided, use day {current_dt.day}.
- The current time is {current_dt.strftime('%H:%M')}.
- The current timezone is {timezone or 'UTC'}."""

            if existing_events:
                from utils.prompts import CORRECTION_SYSTEM_PROMPT
                system_message = CORRECTION_SYSTEM_PROMPT
            else:
                from utils.prompts import CALENDAR_SYSTEM_PROMPT
                system_message = CALENDAR_SYSTEM_PROMPT
                # Handle date prompt
                system_message = system_message.replace('{current_date_prompt}', current_date_prompt)

                # Handle location prompt from session
                from flask import session
                location = session.get('location', {})
                current_location_prompt = f"""- If an event location city is not provided assume: '{location.get('city', 'unknown')}'
- If an event state or region is not provided assume: '{location.get('region', 'unknown')}'
- If an event country is not provided, assume: '{location.get('country', 'unknown')}'
Always lookup the addresses for all event locations."""
                system_message = system_message.replace('{current_location_prompt}', current_location_prompt)

            debug_log(f"System prompt: {system_message}")
            debug_log(f"Current date and location prompts applied")

        messages.append({"role": "system", "content": system_message})

        if image_data and text:
            if os.environ.get('DEBUG_LOG_IMAGE', 'false').lower() == 'true':
                debug_log(f"Processing image data: {image_data[:100]}...")

            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Extract calendar events from this image and text: {text}"
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                    }
                ]
            })
        elif text:
            if not existing_events:
                messages.append({
                    "role": "user",
                    "content": f"Extract calendar events from this text: {text}"
                })

        # Create sanitized copy of messages for logging
        sanitized_messages = []
        for msg in messages:
            sanitized_msg = msg.copy()
            content = msg.get('content')

            if isinstance(content, list):
                sanitized_content = []
                for item in content:
                    if item['type'] == 'image_url':
                        sanitized_content.append({
                            'type': 'image_url',
                            'image_url': {'url': '[IMAGE DATA REDACTED]'}
                        })
                    else:
                        sanitized_content.append(item)
                sanitized_msg['content'] = sanitized_content
            elif isinstance(content, str) and 'data:image' in content:
                sanitized_msg['content'] = '[IMAGE DATA REDACTED]'
            sanitized_messages.append(sanitized_msg)

        debug_log("Sending messages to OpenAI:")
        debug_log(json.dumps(sanitized_messages, indent=2))

        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=messages,
            response_format={"type": "json_object"}
        )

        if not response or not response.choices or not response.choices[0].message:
            debug_log("Invalid response structure from OpenAI")
            raise Exception("initial_process_failed")

        response_content = response.choices[0].message.content
        if not response_content:
            debug_log("Empty response content from OpenAI")
            raise Exception("no_events_found")

        debug_log(f"OpenAI response: {response_content}")

        parsed_response = json.loads(response_content)
        events = parsed_response.get('events', [])

        if not events or len(events) == 0:
            debug_log("No events found in response")
            raise Exception("no_events_found")

        # Process and validate dates for all events
        for event in events:
            try:
                # Ensure proper ISO format for dates
                start_time = event.get('start_time', '')
                end_time = event.get('end_time')

                # Convert to datetime objects to validate
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))

                # If end_time is not provided, set it to start_time + 1 hour
                if not end_time:
                    end_dt = start_dt + timedelta(hours=1)
                    event['end_time'] = end_dt.isoformat()
                else:
                    datetime.fromisoformat(end_time.replace('Z', '+00:00'))

            except (ValueError, AttributeError):
                debug_log(f"Invalid date format: start={start_time}, end={end_time}")
                raise Exception("Invalid date format received from AI")

        # Process locations for both initial creation and corrections
        for event in events:
            # Ensure both fields exist
            event['location_name'] = event.get('location_name', '').strip()
            event['location_address'] = event.get('location_address', '').strip()

            # Do address lookup if we have a location to process
            if event['location_name'] or event['location_address']:
                location_query = f"{event['location_name']} {event['location_address']}".strip()
                try:
                    address_details = lookup_address_details(location_query)
                    if address_details:
                        event['location_details'] = address_details
                        # Always update the location address with full details
                        full_address_parts = [
                            address_details.get('street_address'),
                            address_details.get('city'),
                            address_details.get('state'),
                            address_details.get('postal_code'),
                            address_details.get('country')
                        ]
                        event['location_address'] = ', '.join(filter(None, full_address_parts))

                    # Always create combined display version
                    if event['location_name'] and event['location_address']:
                        event['location'] = f"{event['location_name']} - {event['location_address']}"
                    elif event['location_name']:
                        event['location'] = event['location_name']
                    elif event['location_address']:
                        event['location'] = event['location_address']
                    else:
                        event['location'] = ''
                except Exception as e:
                    logging.error(f"Address lookup failed for {location_query}: {str(e)}")
                    raise Exception("address_lookup_failed")

        debug_log(f"Parsed events with address details: {json.dumps(events, indent=2)}")
        return events
    except json.JSONDecodeError as e:
        error_msg = f"Error parsing OpenAI response: {e}"
        logging.error(error_msg)
        raise Exception("initial_process_failed")
    except Exception as e:
        error_type = str(e)
        logging.error(f"Unexpected error in initial process: {error_type}")
        # If it's our known error type, propagate it directly
        if error_type in ["no_events_found", "address_lookup_failed"]:
            raise
        # Otherwise wrap unknown errors
        raise Exception("initial_process_failed") from e