
from icalendar import Calendar, Event
from datetime import datetime

def generate_ics(events):
    cal = Calendar()
    cal.add('prodid', '-//Calendar App//mxm.dk//')
    cal.add('version', '2.0')

    for event_data in events:
        event = Event()
        event.add('summary', event_data['title'])
        event.add('description', event_data['description'] + "\n\nCalendar item created by https://calendarhelperai.com")

        try:
            # Handle both datetime strings with and without timezone
            start_str = event_data['start_time'].replace('Z', '+00:00') if 'Z' in event_data['start_time'] else event_data['start_time']
            end_str = event_data['end_time'].replace('Z', '+00:00') if 'Z' in event_data['end_time'] else event_data['end_time']
            
            start = datetime.fromisoformat(start_str)
            end = datetime.fromisoformat(end_str)

            event.add('dtstart', start)
            event.add('dtend', end)

            # Use combined location field
            if event_data.get('location'):
                event.add('location', event_data['location'])

            cal.add_component(event)
        except (ValueError, KeyError) as e:
            print(f"Error processing event: {e}")
            continue

    return cal.to_ical().decode('utf-8')
