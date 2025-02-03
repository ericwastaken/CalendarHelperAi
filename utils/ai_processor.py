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

def get_current_datetime_prompt():
    # Get current time in ET
    et_timezone = pytz.timezone('US/Eastern')
    current_time = datetime.now(et_timezone)

    # Format the date components
    current_date_str = current_time.strftime("%-m/%-d/%Y")  # e.g., 2/3/2025
    current_time_str = current_time.strftime("%-I:%M%p ET")  # e.g., 11:36PM ET

    return (
        f"Today's date is {current_date_str}. "
        f"The current time is {current_time_str}. "
        f"If the year is not provided, assume current year ({current_time.year}). "
        f"If the month is not provided, assume current month ({current_time.month}). "
        f"If the day is not provided, assume current day ({current_time.day})"
    )

def process_image_and_text(image_data=None, text=None, existing_events=None):
    try:
        if not text and not image_data:
            raise ValueError("Either text or image data must be provided")

        messages = []

        # Get the base system prompt from environment
        base_system_prompt = os.environ.get('OPENAI_SYSTEM_PROMPT')
        if not base_system_prompt:
            debug_log("OPENAI_SYSTEM_PROMPT not found in environment variables")
            raise ValueError("System prompt not configured")

        # Insert current date/time information
        current_date_info = get_current_datetime_prompt()
        system_message = base_system_prompt.format(current_date_prompt=current_date_info)

        debug_log(f"System prompt: {system_message}")
        debug_log(f"Current date info: {current_date_info}")

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
        else:
            # Text-only processing
            content = text
            if existing_events:
                content = f"Update these events based on the correction:\n{json.dumps(existing_events, indent=2)}\n\nCorrection: {text}"
            messages.append({
                "role": "user",
                "content": content
            })

        debug_log("Sending messages to OpenAI:")
        debug_log(json.dumps(messages, indent=2))

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )

        response_content = response.choices[0].message.content
        debug_log(f"OpenAI response content: {response_content}")

        try:
            parsed_response = json.loads(response_content)
            debug_log(f"Parsed JSON response: {json.dumps(parsed_response, indent=2)}")

            if not isinstance(parsed_response, dict):
                raise ValueError("Response is not a dictionary")

            if 'events' not in parsed_response:
                raise ValueError("Response missing 'events' key")

            events = parsed_response['events']
            if not isinstance(events, list):
                raise ValueError("Events must be a list")

            if not events:
                raise ValueError("No events were extracted")

            # Validate each event has required fields
            for event in events:
                required_fields = ['title', 'description', 'start_time', 'end_time']
                missing_fields = [field for field in required_fields if field not in event]
                if missing_fields:
                    raise ValueError(f"Event missing required fields: {', '.join(missing_fields)}")

            debug_log(f"Successfully parsed {len(events)} events")
            return events

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse OpenAI response as JSON: {str(e)}"
            debug_log(error_msg)
            debug_log(f"Raw response content: {response_content}")
            raise ValueError(error_msg)

        except Exception as e:
            error_msg = f"Error processing OpenAI response: {str(e)}"
            debug_log(error_msg)
            raise ValueError(error_msg)

    except Exception as e:
        debug_log(f"Error in process_image_and_text: {str(e)}")
        raise ValueError(str(e))