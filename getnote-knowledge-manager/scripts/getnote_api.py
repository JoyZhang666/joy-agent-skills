"""Fixed-origin API client. Never expose credentials or remote error bodies."""
import json
import hashlib
import os
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://openapi.biji.com/open/api/v1/resource"


class ApiError(RuntimeError):
    pass


class ApiRejected(ApiError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ApiError("API redirect refused")


class Client:
    def __init__(self):
        self.key = os.environ.get("GETNOTE_API_KEY", "")
        self.account_id = os.environ.get("GETNOTE_CLIENT_ID", "")
        if not self.key or not self.account_id:
            raise ApiError("GETNOTE_API_KEY and GETNOTE_CLIENT_ID are required")
        self.credential_binding = hashlib.sha256(
            ("getnote-binding-v1\0" + self.account_id + "\0" + self.key).encode()).hexdigest()
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, query=None, payload=None):
        url = BASE + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": self.key, "X-Client-ID": self.account_id,
            "Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ApiError("API response exceeds size limit")
            result = json.loads(raw)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise ApiError("API transport or response error; write outcome may be uncertain") from None
        if not isinstance(result, dict):
            raise ApiError("Invalid API response")
        if result.get("success") is False:
            raise ApiRejected("API rejected the request")
        if result.get("success") is not True:
            raise ApiError("API did not confirm success")
        data = result.get("data")
        if not isinstance(data, dict):
            raise ApiError("API data has an unexpected shape")
        return data

    def list_notes(self, cursor):
        return self.request("/note/list", None if cursor is None else {"cursor": cursor})

    def detail(self, note_id):
        data = self.request("/note/detail", {"id": note_id})
        note = data.get("note")
        if not isinstance(note, dict) or not isinstance(note.get("topics"), list):
            raise ApiError("Note detail has an unexpected shape")
        if str(note.get("note_id", note.get("id", ""))) != note_id:
            raise ApiError("Note detail identity mismatch")
        return note

    def add(self, topic_id, note_ids):
        if not 1 <= len(note_ids) <= 20:
            raise ApiError("Batch must contain 1 to 20 notes")
        return self.request("/knowledge/note/batch-add", payload={
            "topic_id": topic_id, "note_ids": note_ids})


def topic_ids(note):
    topics = note.get("topics")
    if not isinstance(topics, list):
        raise ApiError("Missing topics in detail")
    result = []
    for topic in topics:
        if not isinstance(topic, dict):
            raise ApiError("Invalid topic entry")
        value = topic.get("topic_id", topic.get("id"))
        if type(value) not in (str, int) or not str(value):
            raise ApiError("Missing topic identity")
        result.append(str(value))
    return result
