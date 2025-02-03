from icalendar import Calendar, Event
from datetime import datetime

def generate_ics(events):
    cal = Calendar()
    cal.add('prodid', '-//Calendar App//mxm.dk//')
    cal.add('version', '2.0')
    
    for event_data in events:
        event = Event()
        event.add('summary', event_data['title'])
        event.add('description', event_data['description'])
        
        # Convert string timestamps to datetime objects
        start = datetime.fromisoformat(event_data['start_time'])
        end = datetime.fromisoformat(event_data['end_time'])
        
        event.add('dtstart', start)
        event.add('dtend', end)
        
        if event_data.get('location'):
            event.add('location', event_data['location'])
            
        cal.add_component(event)
    
    return cal.to_ical().decode('utf-8')
