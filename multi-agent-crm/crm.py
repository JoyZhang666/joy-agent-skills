"""Single-host, serialized CRM writer. Run as a trusted operating-system user."""
import argparse
from contextlib import contextmanager
from datetime import date
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys

# The database owner administers identities. Protect the coordinator directory
# with OS permissions; access to its files confers administrative authority.


HERE = Path(__file__).resolve().parent
DDL = """
CREATE TABLE config (name TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE actors (actor TEXT PRIMARY KEY, key_hash TEXT NOT NULL);
CREATE TABLE receipts (actor TEXT, session TEXT, contract TEXT, PRIMARY KEY(actor,session));
CREATE TABLE records (kind TEXT, id TEXT, body TEXT, PRIMARY KEY(kind,id));
CREATE TABLE audits (key TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE requests (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE NOT NULL, actor TEXT NOT NULL,
 binding TEXT NOT NULL, contract TEXT NOT NULL, state TEXT NOT NULL, plan TEXT NOT NULL,
 detail TEXT NOT NULL DEFAULT ''
);
"""


class Conflict(ValueError):
    pass


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record_hash(record):
    # Remote numeric cells may represent the same integer as either 3 or 3.0.
    values = {key: int(value) if isinstance(value, float) and value.is_integer() else value
              for key, value in record["fields"].items()}
    return sha(encode({"kind": record["kind"], "id": record["id"],
                       "version": record["version"], "fields": values}).encode())


def contract():
    return sha((HERE / "SKILL.md").read_bytes() + b"\0" + (HERE / "schema.json").read_bytes())


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


@contextmanager
def writer(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        db.rollback()
        raise
    else:
        db.commit()


class Local:
    def __init__(self, db):
        self.db = db

    def read(self, kind, ident):
        row = self.db.execute("SELECT body FROM records WHERE kind=? AND id=?", (kind, ident)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, kind):
        return [json.loads(row[0]) for row in self.db.execute("SELECT body FROM records WHERE kind=? ORDER BY id", (kind,))]

    def apply(self, kind, ident, before, after):
        if self.read(kind, ident) != before:
            raise Conflict("record changed since preflight")
        self.db.execute("INSERT OR REPLACE INTO records VALUES (?,?,?)", (kind, ident, encode(after)))

    def audit(self, key, entry):
        self.db.execute("INSERT INTO audits VALUES (?,?)", (key, encode(entry)))

    def audit_read(self, key):
        row = self.db.execute("SELECT body FROM audits WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None


def backend(db):
    row = db.execute("SELECT value FROM config WHERE name='feishu'").fetchone()
    if not row:
        return Local(db)
    from feishu import Backend
    return Backend(json.loads(row[0]))


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value


def identity(db):
    actor = required_text(os.getenv("CRM_ACTOR"), "CRM_ACTOR")
    session = required_text(os.getenv("CRM_SESSION"), "CRM_SESSION")
    path = required_text(os.getenv("CRM_KEY_FILE"), "CRM_KEY_FILE")
    key_hash = sha(Path(path).read_bytes().strip())
    row = db.execute("SELECT key_hash FROM actors WHERE actor=?", (actor,)).fetchone()
    if not row or not hmac.compare_digest(key_hash, row[0]):
        raise ValueError("invalid actor credential")
    return actor, session


def validate_fields(store, definition, fields):
    if not isinstance(fields, dict) or fields.keys() - definition.keys():
        raise ValueError("fields must contain declared field names only")
    for name, spec in definition.items():
        value = fields.get(name)
        if value is None:
            if spec.get("required"):
                raise ValueError(f"missing required field {name}")
            continue
        typ = spec["type"]
        if typ in ("text", "date", "ref"):
            required_text(value, name)
            if typ == "date" and date.fromisoformat(value).isoformat() != value:
                raise ValueError(f"{name} must be YYYY-MM-DD")
        elif typ == "integer":
            if type(value) is not int:
                raise ValueError(f"{name} must be an integer")
        elif typ == "number":
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        elif typ == "refs":
            if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value) or len(value) != len(set(value)):
                raise ValueError(f"{name} must contain distinct record IDs")
        else:
            raise ValueError(f"unsupported schema type {typ}")
        if typ in ("ref", "refs"):
            for ref in ([value] if typ == "ref" else value):
                if store.read(spec["target"], ref) is None:
                    raise ValueError(f"missing reference {name}: {ref}")


def preflight(store, b, tables):
    keys = {"request_key", "kind", "id", "expected_version", "expected_hash", "fields", "source_ref"}
    if not isinstance(b, dict) or set(b) != keys:
        raise ValueError("batch requires exactly: " + ", ".join(sorted(keys)))
    for key in ("kind", "id", "request_key", "source_ref"):
        required_text(b[key], key)
    kind, ident = b["kind"], b["id"]
    if kind not in tables or kind == "audit":
        raise ValueError("unknown or system-owned entity")
    if not isinstance(b["fields"], dict) or type(b["expected_version"]) is not int:
        raise ValueError("invalid fields or expected_version")
    before = store.read(kind, ident)
    if before and record_hash(before) != before["hash"]:
        raise Conflict("stored fields differ from their recorded hash")
    version = before["version"] if before else 0
    if (version, before["hash"] if before else None) != (b["expected_version"], b["expected_hash"]):
        raise Conflict("stale version or hash")
    fields = {**(before["fields"] if before else {}), **b["fields"]}
    definition = tables[kind]["fields"]
    validate_fields(store, definition, fields)
    # Both a cleared optional value and an empty multi-link become absent cells.
    fields = {key: sorted(value) if definition[key]["type"] == "refs" else value for key, value in fields.items()
              if value is not None and not (definition[key]["type"] == "refs" and value == [])}
    if kind == "opportunities":
        if "estimated_amount" in fields and "currency" not in fields:
            raise ValueError("an estimate requires its currency")
        if "currency" in fields and not re.fullmatch(r"[A-Z]{3}", fields["currency"]):
            raise ValueError("currency must be a three-letter uppercase code")
    after = {"kind": kind, "id": ident, "version": version + 1, "fields": fields}
    after["hash"] = record_hash(after)
    if before and before["fields"] == fields:
        after = before
    return before, after


def status(state, **data):
    return {"state": state, **data}


def deliver(db, key, actor, tables, reconcile=False):
    # Persist execution intent before the first possible remote side effect.
    with writer(db):
        row = db.execute("SELECT * FROM requests WHERE key=? AND actor=?", (key, actor)).fetchone()
        if not row:
            raise ValueError("unknown request for actor")
        plan = json.loads(row["plan"])
        if row["state"] == "rejected":
            raise Conflict(row["detail"])
        if row["state"] == "verified":
            store = backend(db)
            if store.audit_read(key) != plan["audit"]:
                raise ValueError("verified request's audit no longer matches")
            return status("already_verified", seq=row["seq"], record=plan["after"])
        head = db.execute("SELECT key FROM requests WHERE state IN ('queued','executing') ORDER BY seq LIMIT 1").fetchone()
        if not head or head[0] != key:
            return status("queued", seq=row["seq"])
        fresh = row["state"] == "queued"
        if fresh:
            if row["contract"] != contract():
                reason = "contract changed since submission"
            else:
                try:
                    preflight(backend(db), plan["batch"], tables)
                    reason = ""
                except ValueError as exc:
                    # Only a positively identified stale record can cancel the head.
                    if not isinstance(exc, Conflict):
                        raise
                    reason = str(exc)
            if reason:
                db.execute("UPDATE requests SET state='rejected',detail=? WHERE key=?", (reason,key))
            else:
                db.execute("UPDATE requests SET state='executing' WHERE key=?", (key,))
        else:
            reason = ""
    if reason:
        raise Conflict(reason)
    before, after, audit = plan["before"], plan["after"], plan["audit"]
    with writer(db):
        store = backend(db)
        state_now = db.execute("SELECT state FROM requests WHERE key=?", (key,)).fetchone()[0]
        if state_now == "verified":
            if store.audit_read(key) != audit:
                raise ValueError("audit mismatch on replay")
            return status("already_verified", seq=row["seq"], record=after)
        current = store.read(after["kind"], after["id"])
        existing_audit = store.audit_read(key)
        if current == after and existing_audit == audit:
            pass
        elif current == before and existing_audit is None and (fresh or isinstance(store, Local) and reconcile):
            store.apply(after["kind"], after["id"], before, after)
            store.audit(key, audit)
        else:
            return status("uncertain", seq=row["seq"], recovery="independently reconcile original business and audit rows")
    # Fresh backend reads after the business transaction has committed.
    with writer(db):
        store = backend(db)
        if store.read(after["kind"], after["id"]) != after or store.audit_read(key) != audit:
            return status("uncertain", seq=row["seq"])
        db.execute("UPDATE requests SET state='verified' WHERE key=?", (key,))
    return status("saved_and_verified", seq=row["seq"], record=after)


def run(args):
    path = Path(args.db).resolve()
    if args.command == "init":
        cfg = read_json(args.feishu_config) if args.feishu_config else None
        if cfg is not None:
            if set(cfg) != {"base_id", "tables", "schema_hash", "ready"}:
                raise ValueError("use only the generated mapping; credentials never belong in it")
            from feishu import Backend
            Backend(cfg)
        path.touch(mode=0o600, exist_ok=False)
        db = sqlite3.connect(path)
        try:
            db.executescript(DDL)
            if cfg is not None:
                db.execute("INSERT INTO config VALUES ('feishu',?)", (encode(cfg),))
            db.commit()
        finally:
            db.close()
        return status("initialized")
    if not path.is_file():
        raise ValueError("initialize coordinator first")
    db = sqlite3.connect(path, timeout=45, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        if args.command == "register":
            actor = required_text(args.actor, "actor")
            token = secrets.token_urlsafe(32).encode()
            with writer(db):
                db.execute("INSERT INTO actors VALUES (?,?)", (actor,sha(token)))
                descriptor = os.open(args.key_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(descriptor, "wb") as output:
                    output.write(token)
            return status("registered",actor=actor)
        actor, session = identity(db)
        digest = contract()
        tables = read_json(HERE / "schema.json")["tables"]
        if args.command == "handbook":
            db.execute("INSERT OR REPLACE INTO receipts VALUES (?,?,?)", (actor,session,digest))
            return status("handbook_delivered",contract=digest,handbook=(HERE/"SKILL.md").read_text(encoding="utf-8"))
        store = backend(db)
        if args.command == "query":
            if args.kind not in tables or args.kind == "audit":
                raise ValueError("unknown business entity")
            if args.id is None:
                records = store.list(args.kind)
            else:
                record = store.read(args.kind, args.id)
                records = [record] if record else []
            return status("found" if records else "not_found", records=records)
        if args.command == "history":
            results = []
            for key, payload in db.execute("SELECT key,plan FROM requests WHERE state='verified' ORDER BY seq"):
                audit = json.loads(payload)["audit"]
                if (audit["table_name"],audit["record_id"]) == (args.kind,args.id):
                    if store.audit_read(key) != audit:
                        raise ValueError("stored audit mismatch")
                    results.append(audit)
            return status("found",audits=results)
        receipt = db.execute("SELECT contract FROM receipts WHERE actor=? AND session=?", (actor,session)).fetchone()
        if not receipt or receipt[0] != digest:
            raise ValueError("read current handbook in this session")
        if args.command in ("resume","reconcile"):
            return deliver(db,args.key,actor,tables,args.command=="reconcile")
        b = read_json(args.batch)
        if args.dry_run:
            before,after = preflight(store,b,tables)
            return status("dry_run",write_ready=True,cloud_written=False,record=after,unchanged=before==after)
        required_text(args.authorization,"authorization")
        key = required_text(b.get("request_key"), "request_key")
        binding = sha(encode([actor,b,args.authorization]).encode())
        with writer(db):
            row = db.execute("SELECT actor,binding FROM requests WHERE key=?", (key,)).fetchone()
            if row and (row["actor"],row["binding"]) != (actor,binding):
                raise Conflict("request key reused with different identity, authorization or payload")
            if not row:
                before,after = preflight(store,b,tables)
                audit = dict(request_key=key,actor=actor,session=session,table_name=b["kind"],record_id=b["id"],
                             version_before=b["expected_version"],version_after=after["version"],hash_before=b["expected_hash"],
                             hash_after=after["hash"],authorization=args.authorization,source_ref=b["source_ref"])
                plan = dict(before=before,after=after,audit=audit,batch=b)
                db.execute("INSERT INTO requests(key,actor,binding,contract,state,plan) VALUES (?,?,?,?,'queued',?)",
                           (key,actor,binding,digest,encode(plan)))
        if args.enqueue_only:
            row = db.execute("SELECT state,seq FROM requests WHERE key=?", (key,)).fetchone()
            return status(row["state"],seq=row["seq"])
        return deliver(db,key,actor,tables)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="trusted local coordinator database")
    sub = parser.add_subparsers(dest="command",required=True)
    sub.add_parser("init").add_argument("--feishu-config")
    reg = sub.add_parser("register")
    reg.add_argument("actor")
    reg.add_argument("--key-file", required=True)
    sub.add_parser("handbook")
    for command in ("query","history"):
        p = sub.add_parser(command)
        p.add_argument("kind")
        p.add_argument("id",nargs="?" if command=="query" else None)
    for command in ("resume","reconcile"):
        sub.add_parser(command).add_argument("key")
    sync = sub.add_parser("sync")
    sync.add_argument("batch")
    sync.add_argument("--authorization")
    mode = sync.add_mutually_exclusive_group()
    mode.add_argument("--dry-run",action="store_true")
    mode.add_argument("--enqueue-only",action="store_true")
    args = parser.parse_args()
    try:
        result = run(args)
    except subprocess.TimeoutExpired:
        print(encode(status("failed",error="backend timeout; reconcile the original request before retrying")))
        return 1
    except (ValueError, OSError, RuntimeError, sqlite3.Error) as exc:
        print(encode(status("conflict" if isinstance(exc,Conflict) else "failed",error=str(exc))))
        return 1
    print(encode(result))
    return int(result["state"]=="uncertain")


if __name__ == "__main__":
    sys.exit(main())
