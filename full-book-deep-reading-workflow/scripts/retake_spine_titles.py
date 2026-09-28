#!/usr/bin/env python3
"""Pre-reading title correction; rejects unsafe paths and collisions."""
import argparse
import json
import os
import re
from pathlib import Path
from validate_reading_project import regular_path


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('project_root')
    ap.add_argument('--header',help='Optional running-header regular expression')
    args=ap.parse_args();root=Path(args.project_root).expanduser()
    mfpath=regular_path(root,'manifest.json')
    if (root/'state/progress.json').exists() or (root/'notes').is_symlink():
        raise ValueError('Run only before reading state exists')
    if (root/'notes').exists() and any(p.is_file() for p in (root/'notes').rglob('*')):
        raise ValueError('Run only before notes exist')
    original=mfpath.read_bytes();mf=json.loads(original)
    header=re.compile(args.header) if args.header else (re.compile(re.escape(mf['book'])) if mf.get('book') else None)
    sections=mf.get('sections')
    if not isinstance(sections,list) or not sections: raise ValueError('Expected pre-reading sections manifest')
    ids=set();sources=set();targets=set();plan=[]
    for s in sections:
        ident=s.get('section_id')
        if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',ident) or ident in ids:
            raise ValueError('Unsafe/duplicate section ID')
        ids.add(ident);old=regular_path(root,s.get('file'),'chapters')
        if old in sources: raise ValueError('Duplicate source')
        sources.add(old)
        lines=[x.strip().lstrip('#').strip() for x in old.read_text(encoding='utf-8').splitlines() if x.strip()]
        title=next((x for x in lines if len(x)>1 and not(header and header.search(x))),ident)[:40]
        safe=re.sub(r'[^\w-]+','_',title).strip('_')[:40] or 'section'
        new=root/'chapters'/f'{ident}_{safe}.md'
        key=str(new).casefold()
        if key in targets or new.is_symlink() or (new!=old and new.exists()): raise ValueError('Destination collision')
        targets.add(key);plan.append((old,new));s['title']=title;s['file']=new.relative_to(root).as_posix()
    backup=root/'manifest.before-title-retake.json';tmp=root/'manifest.title-retake.tmp'
    if any(p.exists() or p.is_symlink() for p in (backup,tmp)): raise ValueError('Backup/temp exists; inspect before retry')
    with backup.open('xb') as f: f.write(original)
    created=[]
    try:
        # Exclusive copies keep all originals intact until manifest commit.
        for old,new in plan:
            if old!=new:
                with new.open('xb') as f: f.write(old.read_bytes())
                created.append(new)
        with tmp.open('x',encoding='utf-8') as f: json.dump(mf,f,ensure_ascii=False,indent=2)
        os.replace(tmp,mfpath)
    except Exception:
        for p in created: p.unlink()
        if tmp.is_file(): tmp.unlink()
        raise
    # Preserve old source files as recovery material; manifest selects canonical files.
    print(f'Updated {len(plan)} titles; original chapter files and manifest backup retained')
    return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except (ValueError,OSError,TypeError,KeyError,AttributeError,re.error) as exc: raise SystemExit(str(exc))
