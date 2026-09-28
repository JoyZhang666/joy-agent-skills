#!/usr/bin/env python3
"""Build an index from validated state; preserve any previous index."""
import argparse
import os
from pathlib import Path
from validate_reading_project import validate


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('project');args=ap.parse_args()
    root=Path(args.project).expanduser()
    manifest,state=validate(root)
    done={x['id']:x['note'] for x in state['completed_chunks']}
    lines=['# Reading index','',f"Status: {state['status']}",f"Next chunk: {state['next_chunk']}",'',
           'This index is derived from manifest.json and state/progress.json.','']
    for chunk in manifest['chunks']:
        status='completed' if chunk['id'] in done else 'pending'
        lines.append(f"- {chunk['id']}: {status}; source `{chunk['file']}`; note `{done.get(chunk['id'],'')}`")
    target=root/'MASTER_INDEX.md'; temp=root/'MASTER_INDEX.md.tmp'
    if target.is_symlink() or temp.exists() or temp.is_symlink(): raise ValueError('Unsafe/existing temporary index')
    if target.exists():
        if not target.is_file(): raise ValueError('Index is not a file')
        n=1
        while (root/f'MASTER_INDEX.backup-{n}.md').exists() or (root/f'MASTER_INDEX.backup-{n}.md').is_symlink(): n+=1
        with (root/f'MASTER_INDEX.backup-{n}.md').open('xb') as f: f.write(target.read_bytes())
    try:
        with temp.open('x',encoding='utf-8') as f: f.write('\n'.join(lines)+'\n')
        os.replace(temp,target)
    finally:
        if temp.is_file(): temp.unlink()
    print(target)
    return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except (ValueError,OSError,TypeError,KeyError,AttributeError) as exc: raise SystemExit(str(exc))
