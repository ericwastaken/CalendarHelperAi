import os
import logging
from openai import OpenAI
import json
from datetime import datetime

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)

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
    messages = []
    current_dt = datetime.now()
    if timezone:
        from zoneinfo import ZoneInfo
        current_dt = datetime.now(ZoneInfo(timezone))

    current_date_prompt = f"""- If the year is not provided, use {current_dt.year}.
- If the month is not provided, use month {current_dt.month}.
- If the day is not provided, use day {current_dt.day}.
- The current time is {current_dt.strftime('%H:%M')}.
- The current timezone is {timezone or 'UTC'}."""

    system_message = os.environ.get('OPENAI_SYSTEM_PROMPT')
    if system_message:
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

    if not system_message:
        debug_log("OPENAI_SYSTEM_PROMPT not found in environment variables")
        system_message = f"""You are an AI assistant specialized in interpreting calendar events. 
        Extract event details including title, description, start time, end time, location name, and location address. 
        Whenever a date is incomplete, make assumptions based on the following rules:
        - If the year is not provided, use {current_year}.
        - If the month is not provided, use month {current_month}.
        - If the day is not provided, use day {current_day}.
        For locations, provide both the name of the location (e.g. 'Panera Bread') and its address separately.
        Respond with JSON in the format:
        {{
            "events": [
                {{
                    "title": "string",
                    "description": "string",
                    "start_time": "ISO datetime",
                    "end_time": "ISO datetime",
                    "location_name": "string",
                    "location_address": "string"
                }}
            ]
        }}"""

    messages.append({"role": "system", "content": system_message})

    if image_data and text:
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
        if existing_events:
            # Ensure we preserve location structure in corrections
            correction_prompt = (
                "Update these events based on the correction. "
                "Maintain separate location_name and location_address fields in your response. "
                f"Current events: {json.dumps(existing_events)}\n"
                f"Correction: {text}"
            )
            messages.append({
                "role": "user",
                "content": correction_prompt
            })
        else:
            messages.append({
                "role": "user",
                "content": f"Extract calendar events from this text: {text}"
            })

    debug_log("Sending messages to OpenAI:")
    debug_log(json.dumps(messages, indent=2))

    try:
        debug_log("Making API call to OpenAI...")
        response = client.chat.completions.create(
            model="gpt-4",  # Changed from gpt-4o to gpt-4 as that model doesn't exist
            messages=messages,
            response_format={"type": "json_object"}
        )
        debug_log("OpenAI API call completed")
        
        response_content = response.choices[0].message.content
        debug_log(f"OpenAI response content: {response_content}")
    except Exception as e:
        debug_log(f"Error during OpenAI API call: {str(e)}")
        raise Exception(f"OpenAI API error: {str(e)}")

    try:
        parsed_response = json.loads(response_content)
        debug_log(f"Parsed JSON response: {json.dumps(parsed_response, indent=2)}")
        if 'events' not in parsed_response:
            debug_log("No 'events' key in response")
            raise KeyError("Missing 'events' in response")
        events = parsed_response['events']

        # Process and validate dates for all events
        if events:
            for event in events:
                try:
                    # Ensure proper ISO format for dates
                    start_time = event.get('start_time', '')
                    end_time = event.get('end_time', '')
                    
                    # Convert to datetime objects to validate
                    datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    debug_log(f"Invalid date format: start={start_time}, end={end_time}")
                    raise Exception("Invalid date format received from AI")

            # Process locations only for initial creation, not corrections
            if not existing_events:
                for event in events:
                    if event.get('location_name'):
                        location_query = f"{event['location_name']} {event.get('location_address', '')}".strip()
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
                            
            # Always maintain separate location fields and create combined display version
            for event in events:
                if event.get('location_name') or event.get('location_address'):
                    location_parts = []
                    if event.get('location_name'):
                        location_parts.append(event['location_name'])
                    if event.get('location_address'):
                        location_parts.append(event['location_address'])
                    event['location'] = ' - '.join(location_parts)

        debug_log(f"Parsed events with address details: {json.dumps(events, indent=2)}")
        return events
    except (json.JSONDecodeError, KeyError) as e:
        error_msg = f"Error parsing OpenAI response: {e}"
        debug_log(error_msg)
        raise Exception("Failed to parse the AI response")