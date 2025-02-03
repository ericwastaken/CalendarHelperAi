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
        Extract event details including title, description, start time, end time, and location. 
        Whenever a date is incomplete, make assumptions based on the following rules:
        - If the year is not provided, use {current_year}.
        - If the month is not provided, use month {current_month}.
        - If the day is not provided, use day {current_day}.
        Respond with JSON in the format:
        {{
            "events": [
                {{
                    "title": "string",
                    "description": "string",
                    "start_time": "ISO datetime",
                    "end_time": "ISO datetime",
                    "location": "string"
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
            messages.append({
                "role": "user",
                "content": f"Update these events based on the correction: {json.dumps(existing_events)}\nCorrection: {text}"
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

    try:
        events = json.loads(response_content)['events']
        
        # Only lookup addresses for initial event creation, not corrections
        if not existing_events and events:
            for event in events:
                if event.get('location'):
                    address_details = lookup_address_details(event['location'])
                    if address_details:
                        event['location_details'] = address_details
                        # Keep original location name and append full address
                        full_address_parts = [
                            address_details.get('street_address'),
                            address_details.get('city'),
                            address_details.get('state'),
                            address_details.get('postal_code'),
                            address_details.get('country')
                        ]
                        full_address = ', '.join(filter(None, full_address_parts))
                        if full_address:
                            original_location = event['location']
                            event['location'] = f"{original_location} ({full_address})"
        
        debug_log(f"Parsed events with address details: {json.dumps(events, indent=2)}")
        return events
    except (json.JSONDecodeError, KeyError) as e:
        error_msg = f"Error parsing OpenAI response: {e}"
        debug_log(error_msg)
        raise Exception("Failed to parse the AI response")