"""Map a dedicated test Base to the public CRM schema using the signed-in CLI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from datetime import date


SCHEMA_FILE = Path(__file__).with_name("schema.json")
SCHEMA = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
TABLES = SCHEMA["tables"]
TYPE = {"text": "text", "number": "number", "integer": "number", "date": "datetime", "ref": "link", "refs": "link"}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9]+", value):
        raise ValueError("Invalid Base or remote resource identifier")
    return value


def cli(base, operation, *options):
    command = ["lark-cli", "base", "+" + operation, "--base-token", identifier(base),
               "--as", "user", "--format", "json", *options]
    result = subprocess.run(command, capture_output=True, encoding="utf-8", timeout=120)
    try:
        response = json.loads(result.stdout if result.stdout.strip() else result.stderr)
    except ValueError:
        raise RuntimeError("Feishu CLI returned no JSON; verify its installation and user login") from None
    if result.returncode or not response.get("ok"):
        error = response.get("error", {})
        raise RuntimeError(f"Feishu {operation} failed: {error.get('subtype', 'unknown')}, code {error.get('code', result.returncode)}")
    return response["data"]


def records(base, table):
    offset = 0
    while True:
        page = cli(base, "record-list", "--table-id", table, "--offset", str(offset), "--limit", "200")
        for rid, values in zip(page["record_id_list"], page["data"], strict=True):
            yield {"record_id": rid, "fields": dict(zip(page["fields"], values, strict=True))}
        if not page.get("has_more"):
            return
        following = page["next_offset"]
        if following <= offset:
            raise ValueError("Incomplete record pagination")
        offset = following

def layout(kind, mappings):
    specs = {"id": {"type": "text"}, **TABLES[kind]["fields"]}
    if kind == "audit":
        specs["entry_json"] = {"type": "text"}
    else:
        specs.update(version={"type": "integer"}, hash={"type": "text"})
    fields = []
    for name, spec in specs.items():
        field = {"name": name, "type": TYPE[spec["type"]]}
        if "target" in spec:
            if spec["target"] not in mappings:
                continue
            field["link_table"] = mappings[spec["target"]]
        fields.append(field)
    return fields


def schema_hash():
    return hashlib.sha256(SCHEMA_FILE.read_bytes()).hexdigest()


def initialize(path):
    base = identifier(os.environ["CRM_FEISHU_BASE_ID"])
    path = Path(path)
    if not path.parent.is_dir():
        raise ValueError("Mapping parent folder must already exist")
    current = {table["name"]: table["id"] for table in cli(base, "table-list")["tables"]}
    if path.exists():
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("base_id") != base or doc.get("schema_hash") != schema_hash():
            raise ValueError("Existing mapping belongs to a different Base or schema")
        mapping = doc["tables"]
        if any(current.get(k) != v for k, v in mapping.items()):
            raise ValueError("Mapped table identity changed")
    else:
        if set(current) & TABLES.keys() or len(current) > 1:
            raise ValueError("Select a new dedicated empty test Base")
        if any(next(records(base, identifier(t)), None) is not None for t in current.values()):
            raise ValueError("Existing starter table contains rows; use a fresh empty test Base")
        mapping = {}
        doc = {"base_id": base, "schema_hash": schema_hash(), "tables": mapping, "ready": False}

    def checkpoint():
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        temporary.replace(path)

    checkpoint()
    for kind in TABLES:
        if kind in mapping:
            continue
        if kind in current:
            raise ValueError("Untracked table found after an interrupted initialization; inspect before continuing")
        created = cli(base, "table-create", "--name", kind, "--fields", json.dumps(layout(kind, {})))
        mapping[kind] = identifier(created["table"]["id"])
        checkpoint()
    for kind, tid in mapping.items():
        expected = layout(kind, mapping)
        existing = {f["name"]: f for f in cli(base, "field-list", "--table-id", tid)["fields"]}
        missing = [f for f in expected if f["name"] not in existing]
        if missing:
            cli(base, "field-create", "--table-id", tid, "--json", json.dumps(missing))
            for attempt in range(8):
                existing = {f["name"]: f for f in cli(base, "field-list", "--table-id", tid)["fields"]}
                if all(f["name"] in existing for f in expected):
                    break
                time.sleep(1)
        for f in expected:
            actual = existing.get(f["name"], {})
            if actual.get("type") != f["type"]:
                raise ValueError(f"Schema verification failed: {kind}.{f['name']}")
            if f.get("link_table") and actual.get("link_table") not in (f["link_table"], next(k for k,v in mapping.items() if v == f["link_table"])):
                raise ValueError(f"Wrong link target: {kind}.{f['name']}")
    doc["ready"] = True
    checkpoint()
    return {"tables": len(mapping), "schema_verified": True}


def text_cell(value):
    if isinstance(value, list):
        return "".join(part["text"] for part in value)
    return value


class Backend:
    def __init__(self, config):
        if not isinstance(config, dict):
            config = json.loads(Path(config).read_text(encoding="utf-8"))
        self.base = identifier(os.environ["CRM_FEISHU_BASE_ID"])
        if (self.base != config["base_id"] or not config.get("ready") or
                config.get("schema_hash") != schema_hash() or set(config["tables"]) != set(TABLES)):
            raise ValueError("Base selection or verified schema does not match local mapping")
        self.tables = {k: identifier(v) for k, v in config["tables"].items()}

    def _index(self, kind):
        result = {}
        for row in records(self.base, self.tables[kind]):
            key = text_cell(row["fields"].get("id"))
            if not key or key in result:
                raise ValueError("Missing or duplicate business identifier in target table")
            result[key] = row
        return result

    def _decode(self, kind, record, cache):
        cells = record["fields"]
        fields = {}
        for name, spec in TABLES[kind]["fields"].items():
            value = cells.get(name)
            if value is None:
                continue
            tag = spec["type"]
            if tag in ("ref", "refs"):
                target = spec["target"]
                if target not in cache:
                    cache[target] = {r["record_id"]: k for k, r in self._index(target).items()}
                # List and search endpoints expose either link objects or a record-id array.
                if isinstance(value, dict):
                    ids = value["link_record_ids"]
                else:
                    ids = [x["id"] if isinstance(x, dict) else x for x in value]
                values = [cache[target][i] for i in ids]
                if tag == "ref" and len(values) != 1:
                    raise ValueError("Expected one linked row")
                if values:
                    fields[name] = values[0] if tag == "ref" else sorted(values)
            elif tag == "date":
                fields[name] = date.fromisoformat(value[:10]).isoformat()
            else:
                fields[name] = text_cell(value)
        return {"kind": kind, "id": text_cell(cells["id"]), "version": cells["version"],
                "hash": text_cell(cells["hash"]), "fields": fields}

    def read(self, kind, ident):
        row = self._index(kind).get(ident)
        return self._decode(kind, row, {}) if row else None

    def list(self, kind):
        cache = {}
        if kind == "audit":
            return [self._audit_entry(r) for r in self._index(kind).values()]
        return [self._decode(kind, r, cache) for r in self._index(kind).values()]

    def apply(self, kind, ident, before, after):
        if kind == "audit" or after["id"] != ident or after["kind"] != kind:
            raise ValueError("Business record target mismatch")
        raw = self._index(kind).get(ident)
        observed = self._decode(kind, raw, {}) if raw else None
        if observed == after:
            return
        if observed != before:
            raise ValueError("Remote record no longer matches preflight")
        cells = {k: after[k] for k in ("id", "hash", "version")}
        for name, spec in TABLES[kind]["fields"].items():
            value = after["fields"].get(name)
            if value is None:
                if before and name in before["fields"]:
                    cells[name] = None
                continue
            if "target" in spec:
                targets = self._index(spec["target"])
                ids = value if spec["type"] == "refs" else [value]
                value = [{"id": targets[i]["record_id"]} for i in ids]
            elif spec["type"] == "date":
                value = date.fromisoformat(value).isoformat() + " 00:00"
            cells[name] = value
        self._upsert(kind, cells, raw["record_id"] if raw else None)

    def _upsert(self, kind, cells, row_id=None):
        args = ["--table-id", self.tables[kind], "--json", json.dumps(cells, ensure_ascii=False)]
        if row_id:
            args.extend(["--record-id", identifier(row_id)])
        return cli(self.base, "record-upsert", *args)

    def _audit_entry(self, row):
        cells = row["fields"]
        entry = json.loads(text_cell(cells["entry_json"]))
        for name in TABLES["audit"]["fields"]:
            if text_cell(cells.get(name)) != entry.get(name):
                raise ValueError("Audit evidence differs from its visible fields")
        return entry

    def audit_read(self, key):
        row = self._index("audit").get(key)
        return self._audit_entry(row) if row else None

    def audit(self, key, entry):
        old = self.audit_read(key)
        if old is not None:
            if old != entry:
                raise ValueError("Audit key already belongs to a different event")
            return
        cells = {k: entry[k] for k in TABLES["audit"]["fields"] if entry.get(k) is not None}
        cells.update(id=key, entry_json=json.dumps(entry, ensure_ascii=False, sort_keys=True))
        self._upsert("audit", cells)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init"])
    parser.add_argument("--mapping", required=True)
    args = parser.parse_args()
    print(json.dumps(initialize(args.mapping)))
