import os
import logging
from openai import OpenAI
import json
from datetime import datetime
import pytz

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)

# Set up debug logging based on environment variable
DEBUG_LOGGING = os.environ.get('DEBUG_LOGGING', 'false').lower() == 'true'

def debug_log(message):
    if DEBUG_LOGGING:
        logging.debug(message)

def get_current_datetime_info():
    # Get current time in ET
    et_timezone = pytz.timezone('US/Eastern')
    current_time = datetime.now(et_timezone)

    return f"""
    - Today's date is {current_time.strftime('%-m/%-d/%Y')}
    - Current time is {current_time.strftime('%-I:%M%p ET')}
    - Current year is {current_time.year}
    - Current month is {current_time.month}
    - Current day is {current_time.day}
    """

def process_image_and_text(image_data=None, text=None, existing_events=None):
    try:
        if not text and not image_data:
            raise ValueError("Either text or image data must be provided")

        messages = []

        # Get and format system prompt
        base_prompt = os.environ.get('OPENAI_SYSTEM_PROMPT')
        if not base_prompt:
            debug_log("OPENAI_SYSTEM_PROMPT not found in environment variables")
            raise ValueError("System prompt not configured")

        # Get current date info and format system message
        date_info = get_current_datetime_info()
        system_message = base_prompt.format(date_info=date_info)

        debug_log(f"Using system prompt: {system_message}")
        messages.append({"role": "system", "content": system_message})

        # Format user message
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
        else:
            content = text
            if existing_events:
                content = f"Update these events based on the correction:\n{json.dumps(existing_events, indent=2)}\n\nCorrection: {text}"
            messages.append({
                "role": "user",
                "content": content
            })

        debug_log("Sending request to OpenAI with messages:")
        debug_log(json.dumps(messages, indent=2))

        # Make API request
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )

        response_content = response.choices[0].message.content
        debug_log(f"Received response from OpenAI: {response_content}")

        # Parse and validate response
        try:
            data = json.loads(response_content)
            if not isinstance(data, dict) or 'events' not in data:
                raise ValueError("Invalid response format - missing 'events' key")

            events = data['events']
            if not isinstance(events, list):
                raise ValueError("Events must be a list")

            if not events:
                raise ValueError("No events were extracted")

            # Validate each event
            for event in events:
                required = ['title', 'description', 'start_time', 'end_time']
                missing = [field for field in required if field not in event]
                if missing:
                    raise ValueError(f"Event missing required fields: {', '.join(missing)}")

            debug_log(f"Successfully extracted {len(events)} events")
            return events

        except json.JSONDecodeError as e:
            debug_log(f"JSON parsing error: {str(e)}")
            debug_log(f"Raw response: {response_content}")
            raise ValueError("Failed to parse AI response")

    except Exception as e:
        debug_log(f"Error in process_image_and_text: {str(e)}")
        raise ValueError(str(e))