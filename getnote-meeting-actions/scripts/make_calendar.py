"""Prepare a single local iCalendar event, without sending or importing it."""
import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def escape(value):
    return value.replace('\\', '\\\\').replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def fold(line):
    """RFC 5545 physical lines are <=75 UTF-8 octets, without splitting a code point."""
    lines, current = [], ''
    for char in line:
        if len((current + char).encode('utf-8')) > 75:
            lines.append(current)
            current = ' '
        current += char
    lines.append(current)
    return '\r\n'.join(lines)


def zone(name):
    match = re.fullmatch(r'UTC([+-])(\d{2}):(\d{2})', name)
    if match:
        hours, minutes = int(match[2]), int(match[3])
        if hours > 23 or minutes > 59:
            raise ValueError('Invalid fixed UTC offset')
        offset = timedelta(hours=hours, minutes=minutes)
        return timezone(offset if match[1] == '+' else -offset)
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError('Timezone unavailable; use a confirmed UTC+HH:MM/UTC-HH:MM offset or available IANA zone') from exc


def build_event(title, start, minutes, tz_name, uid, description='', now=None):
    if not title.strip():
        raise ValueError('A non-empty title is required')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9@._-]{0,127}', uid):
        raise ValueError('Use a stable ASCII event UID without spaces/control characters')
    if not isinstance(minutes, int) or minutes <= 0:
        raise ValueError('Duration must be a positive whole number of minutes')
    dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('Start must include the confirmed UTC offset')
    if dt.microsecond:
        raise ValueError('Start must use whole seconds')
    actual_zone = zone(tz_name)
    if dt.astimezone(actual_zone).utcoffset() != dt.utcoffset():
        raise ValueError('Start offset does not agree with the specified timezone on this date')
    first = dt.astimezone(timezone.utc)
    last = first + timedelta(minutes=minutes)
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    fmt = '%Y%m%dT%H%M%SZ'
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Get Meeting Actions//EN',
             'CALSCALE:GREGORIAN', 'X-WR-TIMEZONE:' + escape(tz_name),
             'BEGIN:VEVENT', 'UID:' + uid, 'DTSTAMP:' + stamp.strftime(fmt),
             'DTSTART:' + first.strftime(fmt), 'DTEND:' + last.strftime(fmt),
             'SUMMARY:' + escape(title), 'DESCRIPTION:' + escape(description),
             'END:VEVENT', 'END:VCALENDAR']
    return ('\r\n'.join(fold(line) for line in lines) + '\r\n').encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--title', required=True)
    parser.add_argument('--start', required=True, help='ISO datetime with explicit UTC offset')
    parser.add_argument('--minutes', required=True, type=int)
    parser.add_argument('--timezone', required=True)
    parser.add_argument('--uid', required=True)
    parser.add_argument('--description-file', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        description = args.description_file.read_text(encoding='utf-8') if args.description_file else ''
        content = build_event(args.title, args.start, args.minutes, args.timezone, args.uid, description)
        with args.output.open('xb') as stream:
            stream.write(content)
    except (ValueError, OSError, OverflowError) as exc:
        print(f'Calendar preparation failed: {exc}', file=sys.stderr)
        return 1
    print('Prepared local .ics; not imported, no availability checked, no invitation sent.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
