"""Suggest local work slots from a complete, freshly fetched calendar result."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def _instant(value, default_zone):
    if value.get('date_time'):
        result = datetime.fromisoformat(value['date_time'].replace('Z', '+00:00'))
        if result.tzinfo is None:
            result = result.replace(tzinfo=ZoneInfo(value.get('time_zone') or default_zone.key))
        return result.astimezone(timezone.utc)
    if value.get('date'):
        return datetime.combine(date.fromisoformat(value['date']), time.min, default_zone).astimezone(timezone.utc)
    raise ValueError('calendar event has no valid start or end')


def suggest(events, day, zone_name, work_start, work_end, duration, buffer_minutes=0, step=30, after=None, limit=5):
    zone = ZoneInfo(zone_name)
    day = date.fromisoformat(day)
    start_time, end_time = time.fromisoformat(work_start), time.fromisoformat(work_end)
    if start_time.tzinfo or end_time.tzinfo or end_time <= start_time:
        raise ValueError('working hours must be local and end after start')
    if duration <= 0 or buffer_minutes < 0 or step <= 0 or limit <= 0:
        raise ValueError('duration, step and limit must be positive; buffer must be nonnegative')
    begin = datetime.combine(day, start_time, zone).astimezone(timezone.utc)
    end = datetime.combine(day, end_time, zone).astimezone(timezone.utc)
    after = after or datetime.now(timezone.utc)
    if after.utcoffset() is None:
        raise ValueError('after requires a timezone')
    busy = []
    buffer = timedelta(minutes=buffer_minutes)
    for event in events:
        if event.get('status') == 'cancelled':
            continue
        a, b = _instant(event['start'], zone), _instant(event['end'], zone)
        if b <= a:
            raise ValueError('calendar event end must be after start')
        busy.append((a-buffer, b+buffer))
    result = []
    cursor = begin
    while cursor + timedelta(minutes=duration) <= end and len(result) < limit:
        finish = cursor + timedelta(minutes=duration)
        if cursor >= after and not any(cursor < b and finish > a for a, b in busy):
            result.append({'start': cursor.astimezone(zone).isoformat(timespec='minutes'), 'end': finish.astimezone(zone).isoformat(timespec='minutes')})
        cursor += timedelta(minutes=step)
    return result
