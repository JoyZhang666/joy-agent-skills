#!/usr/bin/env python3
"""Archive only an authorized snapshot; reconcile interrupted runs without replay."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from getnote_api import ApiError, ApiRejected, Client, topic_ids
from get_recent_notes import created_time
from proposal_gate import decide, input_version, policy_for, read_json


@contextlib.contextmanager
def account_lock(path):
    with Path(path).open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError("Another archive execution holds this account lock") from None
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ValueError("Another archive execution holds this account lock") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def save_json(path, value):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


def summary(rows, reconciled=False):
    kinds = {r["status"] for r in rows}
    return {"status": next(iter(kinds)) if len(kinds) == 1 else "mixed",
            "results": rows, "reconciled": reconciled}


def execute(state_path, client, clock=time.time):
    state_path = Path(state_path).resolve(strict=True)
    state = read_json(state_path)
    version = input_version(state)
    directory = state_path.parent / ".archive-state"
    directory.mkdir(exist_ok=True)
    if directory.is_symlink() or directory.resolve().parent != state_path.parent:
        raise ValueError("Execution state must remain beside the proposal")
    account_key = hashlib.sha256(client.account_id.encode()).hexdigest()
    run_key = hashlib.sha256((client.account_id + "\0" + state["proposal_id"]).encode()).hexdigest()
    ledger_path = directory / (run_key + ".json")

    def current_authorization():
        fresh = read_json(state_path)
        if input_version(fresh) != version:
            raise ValueError("Proposal changed during execution")
        policy = policy_for(fresh, state_path)
        gate = decide(fresh, clock(), client.account_id, policy, client.credential_binding)
        if not gate["allow"]:
            raise ValueError(gate["reason"])
        return fresh, policy

    with account_lock(directory / (account_key + ".lock")):
        state, policy = current_authorization()
        items = state["items"]
        if ledger_path.exists():
            ledger = read_json(ledger_path)
            if ledger.get("input_version") != version:
                raise ValueError("Proposal identity reused for a different snapshot")
            rows = []
            for item in items:
                try:
                    present = item["topic_id"] in topic_ids(client.detail(item["note_id"]))
                    status = "success" if present else "uncertain"
                except ApiError:
                    status = "uncertain"
                rows.append({**item, "status": status, "reason": "reconciliation_only_no_write"})
            ledger.update(phase="reconciled", results=rows)
            save_json(ledger_path, ledger)
            return summary(rows, True)

        rows, pending = [], []
        # Preflight every item. Automatic scope is checked against current API data.
        for item in items:
            try:
                note = client.detail(item["note_id"])
                topics = topic_ids(note)
                if item["topic_id"] in topics:
                    rows.append({**item, "status": "success", "reason": "already_present"})
                    continue
                if policy is not None:
                    age = clock() - created_time(note.get("created_at")).timestamp()
                    if topics or not 0 <= age <= policy["rules"]["max_note_age_hours"] * 3600:
                        rows.append({**item, "status": "failed", "reason": "outside_automatic_scope"})
                        continue
                pending.append(item)
            except ApiError:
                rows.append({**item, "status": "uncertain", "reason": "preflight_unverified_no_write"})
        ledger = {"input_version": version, "phase": "started", "results": rows}
        save_json(ledger_path, ledger)  # Must persist before the first possible cloud write.
        groups = {}
        for item in pending:
            groups.setdefault(item["topic_id"], []).append(item["note_id"])
        def halted(reason):
            completed = {row["note_id"] for row in rows}
            for item in items:
                if item["note_id"] not in completed:
                    rows.append({**item, "status": "failed", "reason": "not_sent_" + reason})
            ledger.update(phase="halted", results=rows)
            save_json(ledger_path, ledger)
            result = summary(rows)
            result["halted"] = True
            return result

        for topic, ids in groups.items():
            try:
                fresh, fresh_policy = current_authorization()
                if fresh_policy != policy or fresh["authorization"] != state["authorization"]:
                    return halted("authorization_changed")
                if policy is not None:
                    eligible, creation_times = [], {}
                    for note_id in ids:
                        try:
                            note = client.detail(note_id)
                            memberships = topic_ids(note)
                            age = clock() - created_time(note.get("created_at")).timestamp()
                            if topic in memberships:
                                rows.append({"note_id": note_id, "topic_id": topic, "status": "success", "reason": "already_present"})
                            elif memberships or not 0 <= age <= policy["rules"]["max_note_age_hours"] * 3600:
                                rows.append({"note_id": note_id, "topic_id": topic, "status": "failed", "reason": "not_sent_outside_automatic_scope"})
                            else:
                                eligible.append(note_id)
                                creation_times[note_id] = created_time(note["created_at"]).timestamp()
                        except ApiError:
                            rows.append({"note_id": note_id, "topic_id": topic, "status": "uncertain", "reason": "not_sent_preflight_unverified"})
                    ids = eligible
                # Re-check immediately after potentially slow note reads.
                fresh, fresh_policy = current_authorization()
                if fresh_policy != policy or fresh["authorization"] != state["authorization"]:
                    return halted("authorization_changed")
            except (OSError, ValueError, TypeError):
                return halted("authorization_unavailable")
            if policy is not None:
                still_eligible = []
                for note_id in ids:
                    if 0 <= clock() - creation_times[note_id] <= policy["rules"]["max_note_age_hours"] * 3600:
                        still_eligible.append(note_id)
                    else:
                        rows.append({"note_id": note_id, "topic_id": topic, "status": "failed", "reason": "not_sent_age_limit"})
                ids = still_eligible
            if not ids:
                continue
            transport_uncertain = False
            try:
                client.add(topic, ids)
            except ApiRejected:
                pass
            except ApiError:
                transport_uncertain = True
            for note_id in ids:
                try:
                    present = topic in topic_ids(client.detail(note_id))
                    status = "success" if present else ("uncertain" if transport_uncertain else "failed")
                except ApiError:
                    status = "uncertain"
                rows.append({"note_id": note_id, "topic_id": topic, "status": status,
                             "reason": "membership_verified" if status == "success" else "membership_not_verified"})
            ledger["results"] = rows
            save_json(ledger_path, ledger)
        ledger["phase"] = "done" if all(r["status"] == "success" for r in rows) else "needs_review"
        save_json(ledger_path, ledger)
        return summary(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", required=True, help="Approved proposal JSON, outside the installed skill")
    args = p.parse_args()
    try:
        result = execute(args.state, Client())
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "success" else 1
    except (ApiError, OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"status": "blocked", "reason": "Cannot safely execute; verify authorization and local state. Any interrupted write must be reconciled."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
