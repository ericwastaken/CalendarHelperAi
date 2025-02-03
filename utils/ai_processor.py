import os
import logging
from openai import OpenAI
import json
from datetime import datetime

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)

def process_image_and_text(image_data=None, text=None, existing_events=None):
    messages = []
    current_year = datetime.now().year
    current_month = datetime.now().month
    current_day = datetime.now().day

    system_message = os.environ.get('OPENAI_SYSTEM_PROMPT')
    if not system_message:
        system_message = f"""You are an AI assistant specialized in interpreting calendar events. 
        Extract event details including title, description, start time, end time, and location. 
        Whenever a date is incomplete, make assumptions based on the following rules:
        - The current year is {current_year}. If the year is not provided, use {current_year}.
        - The current month is {current_month}. If the month is not provided, use month {current_month}.
        - The current day is {current_day}. If the day is not provided, use day {current_day}.
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

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        response_format={"type": "json_object"}
    )

    response_content = response.choices[0].message.content

    try:
        events = json.loads(response_content)['events']
        return events
    except (json.JSONDecodeError, KeyError) as e:
        raise Exception("Failed to parse the AI response")