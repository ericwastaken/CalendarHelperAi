
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
    try:
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

        if not system_message:
            debug_log("OPENAI_SYSTEM_PROMPT not found in environment variables")
            system_message = f"""You are an AI assistant specialized in interpreting calendar events. 
            Extract event details including title, description, start time, end time, location name, and location address. 
            Whenever a date is incomplete, make assumptions based on the following rules:
            - If the year is not provided, use {current_dt.year}.
            - If the month is not provided, use month {current_dt.month}.
            - If the day is not provided, use day {current_dt.day}.
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
                
                messages.append({
                    "role": "user",
                    "content": f"Here are the current events:\n{json.dumps(formatted_events, indent=2)}\n\nApply this correction: {text}\n\nRespond with the complete updated events including all fields."
                })
            else:
                messages.append({
                    "role": "user",
                    "content": f"Extract calendar events from this text: {text}"
                })

        debug_log("Sending messages to OpenAI:")
        debug_log(json.dumps(messages, indent=2))

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )

        response_content = response.choices[0].message.content
        debug_log(f"OpenAI response: {response_content}")

        events = json.loads(response_content)['events']

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
        logging.error(f"Unexpected error in initial process: {str(e)}")
        raise Exception("initial_process_failed")
