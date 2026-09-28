"""Read back a completed Get save and compare text and knowledge-base membership."""
import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from read_meeting import invoke, data_of, write_json


def normalize(text):
    return text.replace('\r\n', '\n')


def saved_note(receipt):
    data = data_of(receipt)
    note = data.get('note')
    if not isinstance(note, dict) or any(not isinstance(note.get(k), str) or not note[k] for k in ('note_id', 'title', 'note_url')):
        raise ValueError('Save is pending/failed or has no final note; query the original task, do not create again')
    if not re.fullmatch(r'[0-9]+', note['note_id']):
        raise ValueError('Invalid returned note ID')
    return note


def compare(text, note_id, original, kb):
    if original.get('note_id') != note_id or not isinstance(original.get('original'), str):
        raise ValueError('Readback has no original for the saved note')
    if normalize(text) != normalize(original['original']):
        raise ValueError('Readback differs from the local result; archive is not verified')
    notes = kb.get('notes')
    if not isinstance(notes, list) or not any(isinstance(n, dict) and n.get('note_id') == note_id for n in notes):
        raise ValueError('Saved note was not found in the requested knowledge base')
    return hashlib.sha256(normalize(text).encode('utf-8')).hexdigest()


def verify(receipt, text, topic_id, out, cli, runner=invoke):
    note = saved_note(receipt)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', topic_id):
        raise ValueError('Provide the verified topic ID, not its display name')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    result = {'note_id': note['note_id'], 'note_url': note['note_url'], 'topic_id': topic_id, 'status': 'checking'}
    try:
        original_reply = runner(cli, ['note', 'original', note['note_id']])
        write_json(out / 'original.json', original_reply)
        original = data_of(original_reply)
        # CLI 1.5.10 exposes --all rather than a public cursor flag; omit unrelated bodies.
        kb_reply = runner(cli, ['kb', topic_id, '--all', '--no-content'])
        write_json(out / 'knowledge-base.json', kb_reply)
        kb = data_of(kb_reply)
        digest = compare(text, note['note_id'], original, kb)
        result.update(status='verified', normalized_content_sha256=digest)
    except (ValueError, OSError) as exc:
        result.update(status='blocked', error=str(exc))
        write_json(out / 'verification.json', result)
        raise
    write_json(out / 'verification.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True, help='JSON object with exit_code and payload from the save command')
    parser.add_argument('--content-file', type=Path, required=True)
    parser.add_argument('--topic-id', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cli', default='getnote.cmd' if sys.platform == 'win32' else 'getnote')
    args = parser.parse_args()
    cli = shutil.which(args.cli)
    if not cli:
        parser.error('Get CLI not found; provide --cli')
    try:
        receipt = json.loads(args.receipt.read_text(encoding='utf-8-sig'))
        text = args.content_file.read_bytes().decode('utf-8')
        result = verify(receipt, text, args.topic_id, args.out, cli)
    except (ValueError, OSError) as exc:
        print(json.dumps({'success': False, 'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
