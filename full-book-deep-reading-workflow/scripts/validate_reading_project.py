#!/usr/bin/env python3
"""Validate canonical schema 2.0 structure; not semantic reading quality."""
import argparse
import json
from pathlib import Path, PurePosixPath


def regular_path(root, value, prefix=None):
    if not isinstance(value,str) or not value or '\\' in value or ':' in value:
        raise ValueError('Expected a safe relative path')
    parts = PurePosixPath(value)
    if parts.is_absolute() or '..' in parts.parts:
        raise ValueError('Path escape rejected')
    if prefix and not value.startswith(prefix + '/'):
        raise ValueError('Unexpected path directory')
    path = root.joinpath(*parts.parts)
    if any(p.is_symlink() or getattr(p,'is_junction',lambda:False)() for p in [path,*path.parents]):
        raise ValueError('Links/junctions are not allowed')
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file() or path.stat().st_size == 0:
        raise ValueError('Missing, empty or outside file')
    return path


def validate(root):
    regular_path(root,'PROJECT.md')
    manifest=json.loads(regular_path(root,'manifest.json').read_text(encoding='utf-8'))
    state=json.loads(regular_path(root,'state/progress.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version')!='2.0' or state.get('schema_version')!='2.0':
        raise ValueError('Expected schema_version 2.0; migrate legacy state first')
    chunks=manifest.get('chunks')
    if not isinstance(chunks,list) or not chunks: raise ValueError('No manifest chunks')
    ids=[]; sources=[]
    for chunk in chunks:
        ident=chunk.get('id')
        if not isinstance(ident,str) or not ident.strip() or ident in ids: raise ValueError('Invalid/duplicate chunk ID')
        source=regular_path(root,chunk.get('file'),'chapters')
        if source in sources: raise ValueError('Duplicate source mapping')
        ids.append(ident);sources.append(source)
    done=state.get('completed_chunks'); failed=state.get('failed_chunks')
    if not isinstance(done,list) or not isinstance(failed,list): raise ValueError('Invalid state lists')
    completed=[]; notes=[]
    for row in done:
        if not isinstance(row,dict): raise ValueError('Completed entry must contain id and note')
        note=regular_path(root,row.get('note'),'notes/chapters')
        if note in notes: raise ValueError('Duplicate note mapping')
        completed.append(row.get('id'));notes.append(note)
    if completed!=ids[:len(completed)]: raise ValueError('Completed IDs must be an ordered prefix')
    if any(not isinstance(x,str) or x not in ids or x in completed for x in failed) or len(set(failed))!=len(failed):
        raise ValueError('Invalid failed chunk IDs')
    expected=ids[len(completed)] if len(completed)<len(ids) else None
    if state.get('next_chunk')!=expected: raise ValueError('next_chunk mismatch')
    if state.get('status') not in ('running','paused','completed'): raise ValueError('Invalid status')
    if state['status']=='completed':
        if expected is not None or failed: raise ValueError('Incomplete coverage')
        regular_path(root,state.get('synthesis'),'notes')
    return manifest,state


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('project');args=ap.parse_args()
    manifest,state=validate(Path(args.project).expanduser())
    print(f"Valid structure: {len(state['completed_chunks'])}/{len(manifest['chunks'])}; {state['status']}")
    return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except (ValueError,OSError,TypeError,KeyError,AttributeError) as exc: raise SystemExit(str(exc))
