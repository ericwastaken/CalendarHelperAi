"""Validate event dates and represent unknown times without inventing instants."""
from datetime import date, datetime, timedelta, timezone as utc_timezone
from zoneinfo import ZoneInfo


class EventValidationError(ValueError):
    pass


def normalize_event(source):
    if not isinstance(source, dict):
        raise EventValidationError('Invalid event')
    event = dict(source)
    state = event.get('time_status') or ('timed' if event.get('start_time') else 'missing')
    if state not in {'timed', 'missing', 'all_day'}:
        raise EventValidationError('Invalid time status')
    event['time_status'] = state
    if state == 'timed':
        start = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
        event['date'] = start.date().isoformat()
        if not event.get('end_time'):
            event['end_time'] = (start + timedelta(hours=1)).isoformat()
            event['duration_assumed'] = True
            event['duration_confirmed'] = False
        end = datetime.fromisoformat(event['end_time'].replace('Z', '+00:00'))
        if (start.tzinfo is None) != (end.tzinfo is None) or end <= start:
            raise EventValidationError('Invalid event duration')
    else:
        event['start_time'] = None
        event['end_time'] = None
        event['duration_assumed'] = False
        event['duration_confirmed'] = False
        if event.get('date'):
            start_date = date.fromisoformat(event['date'])
            end_date = date.fromisoformat(event['end_date']) if event.get('end_date') else start_date + timedelta(days=1)
            if end_date <= start_date:
                raise EventValidationError('Invalid all-day range')
            event['end_date'] = end_date.isoformat()
        elif state == 'all_day':
            raise EventValidationError('All-day event needs a date')
    for key in ('title', 'description', 'location_name', 'location_address'):
        value = event.get(key) or ''
        if not isinstance(value, str):
            raise EventValidationError('Invalid event text')
        event[key] = value
    location = [event[key].strip() for key in ('location_name', 'location_address')
                if event[key].strip().lower() not in {'', 'unknown', 'none', 'n/a'}]
    event['location'] = ', '.join(location)
    return event


def local_datetime(value, timezone):
    naive = datetime.fromisoformat(value)
    if naive.tzinfo is not None:
        raise EventValidationError('Use a local time')
    zone = ZoneInfo(timezone)
    candidates = [naive.replace(tzinfo=zone, fold=fold) for fold in (0, 1)]
    valid = [dt for dt in candidates if dt.astimezone(utc_timezone.utc).astimezone(zone).replace(tzinfo=None) == naive]
    if not valid or (len(valid) == 2 and valid[0].utcoffset() != valid[1].utcoffset()):
        raise EventValidationError('This time is ambiguous or unavailable because of a clock change. Choose another time.')
    return valid[0]


def resolve_event_time(event, mode, timezone, start_local=None, end_local=None, event_date=None):
    event = normalize_event(event)
    if mode == 'all_day':
        event.update(time_status='all_day', date=event_date or event.get('date'),
                     end_date=None, all_day_source='user', start_time=None, end_time=None)
    elif mode == 'timed':
        start = local_datetime(start_local, timezone)
        end = local_datetime(end_local, timezone)
        event.update(time_status='timed', start_time=start.isoformat(), end_time=end.isoformat(),
                     duration_assumed=False, duration_confirmed=True)
    elif mode == 'confirm_duration' and event['time_status'] == 'timed':
        event['duration_confirmed'] = True
    else:
        raise EventValidationError('Choose a time or an all-day reminder')
    return normalize_event(event)


def require_exportable(event):
    event = normalize_event(event)
    if event['time_status'] == 'missing':
        raise EventValidationError('Set the missing time or choose an all-day reminder before downloading.')
    if event.get('duration_assumed') and event.get('duration_confirmed') is not True:
        raise EventValidationError('Confirm the suggested duration or enter an end time before downloading.')
    return event
