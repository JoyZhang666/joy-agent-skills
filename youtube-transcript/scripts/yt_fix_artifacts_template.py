#!/usr/bin/env python3
"""Apply reviewed replacements only after unique-match and two-sided probes pass."""
import argparse
import json
import os
from pathlib import Path
import uuid


def propose(text, fixes):
    if not isinstance(fixes,list) or not fixes:raise ValueError('A nonempty JSON fixes list is required')
    result=text
    for f in fixes:
        old,new,probes=f['old'],f['new'],f['probes']
        if not isinstance(old,str) or not old or not isinstance(new,str) or result.count(old)!=1:
            raise ValueError('Each old text must match exactly once')
        if not isinstance(probes,list) or len(probes)<2 or not all(isinstance(p,str) and p and p in text for p in probes):
            raise ValueError('Provide at least two nonempty source probes from both sides')
        result=result.replace(old,new,1)
    if any(p not in result for f in fixes for p in f['probes']):
        raise ValueError('A required probe would be lost; original preserved')
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('path');ap.add_argument('fixes_json')
    ap.add_argument('--apply',action='store_true');a=ap.parse_args();p=Path(a.path)
    if any(x.is_symlink() or getattr(x,'is_junction',lambda:False)() for x in [p,*p.parents]):raise ValueError('Links rejected')
    original=p.read_bytes();text=original.decode('utf-8');out=propose(text,json.loads(Path(a.fixes_json).read_text(encoding='utf-8')))
    if a.apply:
        if p.read_bytes()!=original:raise ValueError('Source changed during review')
        backup=p.with_name(p.name+'.backup-'+uuid.uuid4().hex);tmp=p.with_name(p.name+'.tmp-'+uuid.uuid4().hex)
        with backup.open('xb') as f:f.write(original)
        try:
            with tmp.open('xb') as f:f.write(out.encode('utf-8'))
            if p.read_bytes()!=original:raise ValueError('Source changed during write')
            os.replace(tmp,p)
        finally:
            if tmp.exists():tmp.unlink()
    print('Applied with backup' if a.apply else 'Dry run passed; no files modified')
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,KeyError,TypeError) as exc:raise SystemExit(str(exc))
