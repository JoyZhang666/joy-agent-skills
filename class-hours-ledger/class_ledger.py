#!/usr/bin/env python3
"""Local course ledger. Explicit DB, serialized writes, idempotent requests."""
import argparse
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

TYPES = ('purchase', 'bonus', 'attend', 'adjust', 'expire')
DEFAULT_COURSE = '私教'


def date_value(value):
    if dt.date.fromisoformat(value).isoformat() != value:
        raise ValueError('Date must be YYYY-MM-DD')
    return value


def validate_fields(date, kind, change, paid, course, coach, valid_until, note):
    date_value(date)
    if type(change) is not int or change == 0 or abs(change) > 1000000:
        raise ValueError('Hours must be a nonzero integer within +/-1000000')
    if kind not in TYPES or (kind in ('purchase', 'bonus') and change < 0) or (kind in ('attend', 'expire') and change > 0):
        raise ValueError('Invalid type/hour direction')
    amount = Decimal(str(paid))
    if not amount.is_finite() or amount < 0 or amount > Decimal('1000000000') or amount * 100 != (amount * 100).to_integral_value():
        raise ValueError('Paid amount must be finite, nonnegative, with at most two decimal places')
    if kind != 'purchase' and amount != 0:
        raise ValueError('Only purchase may have a paid amount')
    if valid_until is not None and valid_until != '无限期':
        date_value(valid_until)
    if not all(isinstance(x, str) for x in (course, coach, note)):
        raise ValueError('Course, coach and note must be text')
    return {'date': date, 'type': kind, 'change': change, 'paid_cents': int(amount * 100),
            'course': course, 'coach': coach, 'valid_until': valid_until, 'note': note}


def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def safe_path(path):
    path = Path(path).expanduser().absolute()
    if any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in (path, *path.parents)):
        raise ValueError('Links/junctions are not allowed for ledger paths')
    return path


def connect(path, create=False):
    path = safe_path(path)
    if not create and not path.is_file():
        raise ValueError('Database does not exist; use init explicitly')
    con = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    return con


def require_schema(con):
    if con.execute('PRAGMA user_version').fetchone()[0] != 2:
        raise ValueError('Unsupported database schema; do not use an old database without reviewed migration')


def initialize(path):
    path = safe_path(path)
    if not path.parent.is_dir():
        raise ValueError('Create the chosen data directory first')
    with path.open('xb'):
        pass
    con = connect(path)
    try:
        con.execute('BEGIN IMMEDIATE')
        con.execute('CREATE TABLE class_flow (\n id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL UNIQUE,\n date TEXT NOT NULL, type TEXT NOT NULL, change INTEGER NOT NULL,\n balance_after INTEGER NOT NULL, paid_cents INTEGER NOT NULL,\n course TEXT NOT NULL, coach TEXT NOT NULL, valid_until TEXT,\n note TEXT NOT NULL, payload_sha256 TEXT NOT NULL, created_at TEXT NOT NULL)')
        con.execute('PRAGMA user_version=2')
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def verify_connection(con):
    require_schema(con)
    if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise ValueError('SQLite integrity check failed')
    rows = con.execute('SELECT * FROM class_flow ORDER BY id').fetchall()
    balance = 0
    for row in rows:
        if type(row['paid_cents']) is not int:
            raise ValueError('Invalid stored money type')
        fields = validate_fields(row['date'], row['type'], row['change'], Decimal(row['paid_cents'])/100,
                                 row['course'], row['coach'], row['valid_until'], row['note'])
        balance += row['change']
        if row['balance_after'] != balance or row['payload_sha256'] != fingerprint(fields):
            raise ValueError(f"Inconsistent entry id={row['id']}")
    return rows, balance


def backup(path):
    path = safe_path(path)
    directory = safe_path(path.parent / (path.name + '.backups'))
    directory.mkdir(exist_ok=True)
    target = safe_path(directory / (dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid.uuid4().hex + '.db'))
    with target.open('xb'):
        pass
    source = connect(path)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
        if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Backup integrity failed')
    finally:
        source.close()
        dest.close()
    return str(target)


def add_entry(path, request_id, date, kind, change, paid='0', course=DEFAULT_COURSE,
              coach='', valid_until=None, note=''):
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
        raise ValueError('A stable request ID (1-128 characters) is required')
    fields = validate_fields(date, kind, change, paid, course, coach, valid_until, note)
    con = connect(path)
    try:
        con.execute('BEGIN IMMEDIATE')
        rows, balance = verify_connection(con)
        old = con.execute('SELECT * FROM class_flow WHERE request_id=?', (request_id,)).fetchone()
        if old:
            if old['payload_sha256'] != fingerprint(fields):
                raise ValueError('Request ID already used with different fields')
            result = {'committed': True, 'replayed': True, 'entry_id': old['id'],
                      'balance_after_entry': old['balance_after'], 'current_balance': balance}
        else:
            balance += change
            cur = con.execute('INSERT INTO class_flow (request_id,date,type,change,balance_after,paid_cents,course,coach,valid_until,note,payload_sha256,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                              (request_id,date,kind,change,balance,fields['paid_cents'],course,coach,valid_until,note,
                               fingerprint(fields),dt.datetime.now(dt.timezone.utc).isoformat()))
            result = {'committed': True, 'replayed': False, 'entry_id': cur.lastrowid,
                      'balance_after_entry': balance, 'current_balance': balance}
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    try:
        result['backup'] = backup(path)
        result['backup_ok'] = True
    except (OSError, sqlite3.Error, ValueError):
        result.update(backup_ok=False, warning='Entry is committed. Backup failed; retry ONLY with the same request ID.')
    if result['current_balance'] < 0:
        result['balance_warning'] = 'Negative balance: reconcile missing purchase/adjustment records'
    return result


def read_ledger(path):
    con = connect(path)
    try:
        con.execute('BEGIN')
        rows,balance = verify_connection(con)
        return {'verified': True, 'balance': balance, 'entries': [dict(r) for r in rows],
                'total_paid_cents': sum(r['paid_cents'] for r in rows)}
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', required=True, help='Explicit database path outside the Skill directory')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init')
    add = sub.add_parser('add')
    add.add_argument('date');add.add_argument('type',choices=TYPES);add.add_argument('change',type=int)
    add.add_argument('--request-id', required=True)
    add.add_argument('--paid', default='0');add.add_argument('--course',default=DEFAULT_COURSE)
    add.add_argument('--coach',default='');add.add_argument('--valid-until');add.add_argument('--note',default='')
    for cmd in ('verify','report','balance','backup'):sub.add_parser(cmd)
    args = ap.parse_args()
    db = safe_path(args.db)
    if db.is_relative_to(Path(__file__).resolve().parent):
        raise ValueError('Keep private databases outside the Skill directory')
    if args.cmd == 'init':
        initialize(db);result={'initialized': True}
    elif args.cmd == 'add':
        result=add_entry(db,args.request_id,args.date,args.type,args.change,args.paid,args.course,args.coach,args.valid_until,args.note)
    elif args.cmd == 'backup':
        read_ledger(db);result={'backup': backup(db)}
    else:
        result=read_ledger(db)
        if args.cmd != 'report':result.pop('entries')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 2 if result.get('backup_ok') is False else 0


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ValueError, OSError, sqlite3.Error, InvalidOperation) as exc:
        print('Error: '+str(exc),file=__import__('sys').stderr)
        raise SystemExit(1)
