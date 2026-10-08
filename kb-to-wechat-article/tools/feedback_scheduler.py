#!/usr/bin/env python3
"""Scan content-ledger.json for due feedback tasks.

This is a scheduler helper, not a daemon. Run it from heartbeat/cron/manual agent
turns. It prints due tasks as JSON and can optionally mark them collecting.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List

TZ = dt.timezone(dt.timedelta(hours=8))


def parse_time(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        parsed = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=TZ)
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--mark-collecting", action="store_true")
    args = ap.parse_args()
    p = Path(args.ledger)
    if not p.exists():
        print(json.dumps({"status": "blocked", "blocker": "ledger_missing", "due": []}, ensure_ascii=False))
        return 2
    data: Dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    now = dt.datetime.now(TZ)
    due: List[Dict[str, Any]] = []
    for art in data.get("articles", []):
        fb = art.get("feedback") or {}
        status = fb.get("status")
        next_due = parse_time(fb.get("next_due_at"))
        if status in {"scheduled", "pending_credentials", "collecting"} and next_due and next_due <= now:
            due.append({
                "article_id": art.get("article_id"),
                "title": art.get("title"),
                "output_dir": art.get("output_dir"),
                "public_url": art.get("public_url"),
                "next_due_at": fb.get("next_due_at"),
                "feedback_status": status,
            })
            if args.mark_collecting:
                fb["status"] = "collecting"
    if args.mark_collecting:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "now": now.isoformat(), "due": due}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
