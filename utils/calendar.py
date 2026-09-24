from datetime import datetime, timezone as datetime_timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event


def generate_ics(events, timezone='UTC'):
    """Preserve event instants, converting aware times to the user's calendar zone."""
    cal = Calendar()
    cal.add('prodid', '-//CalendarHelperAI//Calendar Helper AI//EN')
    cal.add('version', '2.0')
    zone = ZoneInfo(timezone)

    for event_data in events:
        event = Event()
        event.add('uid', f'{uuid4()}@calendarhelperai.com')
        event.add('dtstamp', datetime.now(datetime_timezone.utc))
        event.add('summary', event_data.get('title') or 'Untitled event')
        source_info = f"\nExtracted from: {event_data.get('source_image', 'text input')}"
        event.add('description', (event_data.get('description') or '') + source_info + '\n\nCalendar item created by https://calendarhelperai.com')

        # A timezone offset identifies an instant. Replacing it would shift the event.
        start = datetime.fromisoformat(event_data['start_time'].replace('Z', '+00:00'))
        end = datetime.fromisoformat(event_data['end_time'].replace('Z', '+00:00'))
        start = start.astimezone(zone) if start.tzinfo else start.replace(tzinfo=zone)
        end = end.astimezone(zone) if end.tzinfo else end.replace(tzinfo=zone)
        if end.astimezone(datetime_timezone.utc) <= start.astimezone(datetime_timezone.utc):
            raise ValueError('Event end must be after its start')
        # Local ICS timestamps cannot distinguish the second repeated DST hour.
        # UTC retains that instant without depending on a calendar's fold choice.
        if start.fold or end.fold:
            start = start.astimezone(datetime_timezone.utc)
            end = end.astimezone(datetime_timezone.utc)
        event.add('dtstart', start)
        event.add('dtend', end)
        location = event_data.get('location')
        if location and location.strip().lower() not in {'unknown', 'unknown -', 'none', 'n/a'}:
            event.add('location', location)
        cal.add_component(event)

    return cal.to_ical().decode('utf-8')
