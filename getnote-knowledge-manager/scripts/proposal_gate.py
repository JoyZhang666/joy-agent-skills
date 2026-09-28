#!/usr/bin/env python3
"""Validate recorded user authorization; a record is not proof of human consent."""
import argparse
import hashlib
import json
import math
import re
import time
from pathlib import Path


def stamp(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def read_json(path):
    raw = Path(path).read_bytes()
    if len(raw) > 1024 * 1024:
        raise ValueError("State exceeds size limit")
    def reject_constant(_):
        raise ValueError("Non-finite JSON")
    value = json.loads(raw, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("State must be an object")
    return value


def input_version(state):
    items = state.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 20:
        raise ValueError("A proposal must contain 1 to 20 items")
    for item in items:
        if not isinstance(item, dict) or set(item) != {"note_id", "topic_id"}:
            raise ValueError("Each item requires only note_id and topic_id")
        if not isinstance(item["note_id"], str) or not item["note_id"].isascii() or not item["note_id"].isdecimal():
            raise ValueError("note_id must be a decimal string")
        if not isinstance(item["topic_id"], str) or not item["topic_id"].strip():
            raise ValueError("topic_id must be a nonempty string")
    if len({i["note_id"] for i in items}) != len(items):
        raise ValueError("Duplicate note_id in proposal")
    for field in ("proposal_id", "account_id"):
        if not isinstance(state.get(field), str) or not state[field].strip():
            raise ValueError("Proposal and account identities are required")
    binding = state.get("credential_binding")
    if not isinstance(binding, str) or not re.fullmatch(r"[0-9a-f]{64}", binding):
        raise ValueError("A credential binding is required")
    payload = {k: state[k] for k in ("proposal_id", "account_id", "credential_binding")}
    payload["items"] = sorted(items, key=lambda i: (i["note_id"], i["topic_id"]))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def policy_for(state, state_path):
    auth = state.get("authorization", {})
    if not isinstance(auth, dict):
        raise ValueError("Invalid authorization")
    if auth.get("mode") != "automatic":
        return None
    name = auth.get("policy_file")
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".json"):
        raise ValueError("policy_file must be a JSON filename next to the proposal")
    parent = Path(state_path).resolve().parent
    path = (parent / name).resolve(strict=True)
    if path.parent != parent:
        raise ValueError("Policy must remain in the proposal directory")
    return read_json(path)


def decide(state, now, account_id, policy=None, credential_binding=None):
    def deny(reason):
        return {"allow": False, "status": "blocked", "reason": reason}
    try:
        version = input_version(state)
        if state.get("schema_version") != 1 or state.get("input_version") != version:
            return deny("Proposal snapshot mismatch")
        if not credential_binding or state["credential_binding"] != credential_binding:
            return deny("Runtime credential binding mismatch")
        if state["account_id"] != account_id:
            return deny("Runtime account mismatch")
        reply = state.get("reply")
        if not isinstance(reply, dict) or reply.get("decision") not in ("approve", "none"):
            return deny("Missing reply check, rejection or revision")
        checked = reply.get("checked_at")
        if not stamp(checked) or not 0 <= now - checked <= 300:
            return deny("Reply check missing or stale")
        auth = state.get("authorization")
        if not isinstance(auth, dict):
            return deny("Explicit authorization required")
        if auth.get("mode") == "manual":
            when = auth.get("approved_at")
            if (reply["decision"] != "approve" or not auth.get("evidence_ref")
                    or auth.get("account_id") != account_id or auth.get("input_version") != version
                    or not stamp(when) or when > checked):
                return deny("Approval must bind this account and proposal snapshot")
        elif auth.get("mode") == "automatic":
            if not isinstance(policy, dict) or policy.get("enabled") is not True:
                return deny("Automatic mode has not been explicitly enabled")
            if (not policy.get("evidence_ref") or not policy.get("policy_id")
                    or policy.get("policy_id") != auth.get("policy_id") or policy.get("account_id") != account_id
                    or policy.get("credential_binding") != credential_binding):
                return deny("Automatic authorization identity mismatch")
            start, end = policy.get("authorized_at"), policy.get("expires_at")
            if not stamp(start) or not stamp(end) or not start <= now < end:
                return deny("Automatic authorization expired or invalid")
            rules, topics = policy.get("rules"), policy.get("allowed_topic_ids")
            if (not isinstance(rules, dict) or rules.get("unarchived_only") is not True
                    or type(rules.get("max_note_age_hours")) is not int or rules["max_note_age_hours"] <= 0
                    or type(rules.get("max_notes_per_run")) is not int or not 1 <= rules["max_notes_per_run"] <= 20
                    or len(state["items"]) > rules["max_notes_per_run"] or not isinstance(topics, list)
                    or any(not isinstance(t, str) or not t for t in topics)
                    or any(i["topic_id"] not in topics for i in state["items"])):
                return deny("Proposal exceeds automatic scope")
            sent = state.get("sent_at")
            if (not stamp(sent) or sent < start or now - sent < 60 or checked < sent + 60
                    or not state.get("message_id") or not state.get("target") or state.get("send_status") != "sent"):
                return deny("Successful proposal delivery and adjustment window required")
        else:
            return deny("Unknown authorization mode")
        return {"allow": True, "status": "ready", "input_version": version}
    except (ValueError, TypeError, KeyError, AttributeError):
        return deny("Invalid authorization state")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("state_file", nargs="?")
    p.add_argument("--account-id")
    p.add_argument("--print-credential-binding", action="store_true")
    p.add_argument("--digest", action="store_true", help="Print digest only; does not grant approval")
    args = p.parse_args()
    try:
        if args.print_credential_binding:
            from getnote_api import Client
            print(Client().credential_binding)
            return 0
        if not args.state_file or not args.account_id:
            p.error("state_file and --account-id are required")
        state = read_json(args.state_file)
        if args.digest:
            print(input_version(state))
            return 0
        from getnote_api import Client
        client = Client()
        result = decide(state, time.time(), client.account_id, policy_for(state, args.state_file), client.credential_binding)
        if args.account_id != client.account_id:
            result = {"allow": False, "status": "blocked", "reason": "Runtime account mismatch"}
    except (OSError, ValueError, TypeError, RuntimeError):
        result = {"allow": False, "status": "blocked", "reason": "Cannot validate state"}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["allow"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
