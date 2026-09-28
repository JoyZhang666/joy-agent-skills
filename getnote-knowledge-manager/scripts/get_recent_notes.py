#!/usr/bin/env python3
"""Read a complete bounded listing using the documented cursor contract."""
import argparse
import datetime as dt
import json
import sys
from getnote_api import ApiError, Client

TZ = dt.timezone(dt.timedelta(hours=8))


def created_time(value):
    if not isinstance(value, str) or not value:
        raise ApiError("Missing creation time")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ApiError("Invalid creation time") from None
    return parsed.replace(tzinfo=TZ) if parsed.tzinfo is None else parsed


def collect(client, hours=24, now=None, max_pages=1000):
    if type(hours) is not int or hours <= 0:
        raise ApiError("hours must be a positive integer")
    now = now or dt.datetime.now(TZ)
    cutoff = now - dt.timedelta(hours=hours)
    cursor, cursors, ids, found = None, set(), set(), []
    for _ in range(max_pages):
        data = client.list_notes(cursor)
        notes, more = data.get("notes"), data.get("has_more")
        if not isinstance(notes, list) or type(more) is not bool:
            raise ApiError("Invalid list response; no partial success returned")
        for note in notes:
            if not isinstance(note, dict):
                raise ApiError("Invalid note entry")
            note_id = note.get("note_id")
            if not isinstance(note_id, str) or not note_id.isascii() or not note_id.isdecimal():
                raise ApiError("Expected a decimal string note_id")
            created = created_time(note.get("created_at"))
            if note_id not in ids:
                ids.add(note_id)
                if created >= cutoff:
                    found.append(note)
        if not more:
            return {"notes": found, "cutoff": cutoff.isoformat(), "count": len(found), "complete": True}
        next_cursor = data.get("cursor")
        if type(next_cursor) not in (str, int) or str(next_cursor) == "":
            raise ApiError("Missing pagination cursor")
        marker = str(next_cursor)
        if marker in cursors:
            raise ApiError("Pagination cursor repeated; no partial success returned")
        cursors.add(marker)
        cursor = next_cursor
    raise ApiError("Pagination limit reached; no partial success returned")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("hours", type=int, nargs="?", default=24)
    args = p.parse_args()
    try:
        print(json.dumps(collect(Client(), args.hours), ensure_ascii=False))
        return 0
    except ApiError as error:
        print(json.dumps({"status": "failed", "error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
