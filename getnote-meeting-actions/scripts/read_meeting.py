"""Read one verified Get note; preserve raw replies and an unmodified text snapshot."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def invoke(cli, args):
    try:
        result = subprocess.run([cli, *args, '-o', 'json'], capture_output=True,
                                encoding='utf-8-sig', errors='strict', timeout=90,
                                shell=False)
        try:
            payload = json.loads(result.stdout)
        except ValueError:
            payload = None
        return {'exit_code': result.returncode, 'stdout': result.stdout,
                'stderr': result.stderr, 'payload': payload}
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        return {'exit_code': -1, 'error': str(exc), 'payload': None}


def data_of(reply):
    payload = reply.get('payload')
    if reply.get('exit_code') != 0 or not isinstance(payload, dict) or payload.get('success') is not True:
        raise ValueError('CLI command failed; inspect the saved raw response')
    data = payload.get('data')
    if not isinstance(data, dict):
        raise ValueError('CLI data is not an object')
    return data


def choose_mode(note, mode):
    if mode != 'auto':
        return mode
    if note.get('audio') or note.get('note_type') not in ('plain_text', 'link', 'img_text'):
        return 'transcript'
    return 'original'


def text_source(note, mode, source_data):
    if mode == 'summary':
        text, scope = note.get('content'), 'summary_only'
    else:
        text = source_data.get(mode)
        if text is None or text == '':
            text, scope = note.get('content'), 'summary_only'
        else:
            scope = 'transcript' if mode == 'transcript' else 'original'
    if not isinstance(text, str) or not text.strip():
        raise ValueError('No usable string content; do not invent a transcript')
    return text, scope


def collect(note_id, out, cli, mode='auto', with_context=False, runner=invoke):
    # Read commands accept a verified numeric ID only; no shell or arbitrary command input.
    if not isinstance(note_id, str) or not re.fullmatch(r'[0-9]+', note_id):
        raise ValueError('Provide a verified numeric note ID as a string, not a URL')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'raw').mkdir()
    metadata = {'note_id': note_id, 'status': 'reading', 'warnings': []}

    def request(name, args, required=True):
        reply = runner(cli, args)
        write_json(out / 'raw' / (name + '.json'), reply)
        try:
            data = data_of(reply)
            returned_id = data.get('note_id')
            if returned_id is not None and returned_id != note_id:
                raise ValueError('Response note ID mismatch')
            return data
        except ValueError as exc:
            if required:
                raise
            metadata['warnings'].append(f'{name}: {exc}')
            return None

    try:
        note = request('detail-before', ['note', note_id]).get('note')
        if not isinstance(note, dict) or note.get('note_id') != note_id:
            raise ValueError('Invalid note detail or note ID mismatch')
        selected = choose_mode(note, mode)
        original = {} if selected == 'summary' else request(selected, ['note', selected, note_id])
        text, scope = text_source(note, selected, original)
        todos = request('todos', ['note', 'todos', note_id], required=False)
        if with_context:
            for name in ('timeline', 'quick-note'):
                request(name, ['note', name, note_id], required=False)
        after = request('detail-after', ['note', note_id]).get('note')
        if not isinstance(after, dict) or after.get('note_id') != note_id:
            raise ValueError('Invalid final note detail')
        for field in ('version', 'updated_at'):
            if note.get(field) != after.get(field):
                raise ValueError('Note changed during collection; retry into a new snapshot directory')
        # Bytes are deterministic and retain every newline/character of the returned string.
        encoded = text.encode('utf-8')
        (out / 'source.txt').write_bytes(encoded)
        metadata.update({
            'status': 'collected', 'note_url': note.get('note_url'), 'title': note.get('title'),
            'note_type': note.get('note_type'), 'version': note.get('version'),
            'updated_at': note.get('updated_at'), 'requested_view': selected,
            'scope': scope, 'content_sha256': hashlib.sha256(encoded).hexdigest(),
            'characters': len(text), 'lines': len(text.splitlines()), 'utf8_bytes': len(encoded),
            'version_observable': any(note.get(k) is not None for k in ('version', 'updated_at')),
            'meeting_todos': todos.get('meeting_todos') if todos else None,
            'upstream_transcription_completeness': 'not_proven_by_transport_check'
        })
        if scope == 'summary_only':
            metadata['warnings'].append('Only summary/body available; do not claim full transcript coverage')
        write_json(out / 'metadata.json', metadata)
        return metadata
    except Exception as exc:
        metadata.update(status='failed', error=str(exc))
        write_json(out / 'metadata.json', metadata)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--note-id', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cli', default='getnote.cmd' if sys.platform == 'win32' else 'getnote')
    parser.add_argument('--mode', choices=['auto', 'original', 'transcript', 'summary'], default='auto')
    parser.add_argument('--with-context', action='store_true')
    args = parser.parse_args()
    cli = shutil.which(args.cli)
    if not cli:
        parser.error('Get CLI not found; provide its executable path with --cli')
    try:
        result = collect(args.note_id, args.out, cli, args.mode, args.with_context)
    except (ValueError, OSError) as exc:
        print(json.dumps({'success': False, 'error': str(exc)}, ensure_ascii=False))
        return 1
    # Full private content stays on disk, not in stdout.
    print(json.dumps({k: result[k] for k in ('status', 'scope', 'characters', 'lines', 'content_sha256', 'warnings')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
