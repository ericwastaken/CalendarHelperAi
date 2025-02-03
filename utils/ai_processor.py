import os
from openai import OpenAI
import json

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)

def process_image_and_text(image_data=None, text=None, existing_events=None):
    messages = []
    
    system_message = """You are an AI assistant specialized in interpreting calendar events. 
    Extract event details including title, description, start time, end time, and location. 
    Respond with JSON in the format:
    {
        "events": [
            {
                "title": "string",
                "description": "string",
                "start_time": "ISO datetime",
                "end_time": "ISO datetime",
                "location": "string"
            }
        ]
    }"""
    
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

    return json.loads(response.choices[0].message.content)['events']
