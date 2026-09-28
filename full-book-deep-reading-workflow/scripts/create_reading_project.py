#!/usr/bin/env python3
"""Create only missing scaffold files beside an existing source."""
import argparse
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source')
    ap.add_argument('--title', default='')
    ap.add_argument('--author', default='')
    ap.add_argument('--output', default='')
    args = ap.parse_args()
    source = Path(args.source).expanduser()
    if not source.is_file():
        raise ValueError('Source must exist and be a file')
    root = Path(args.output).expanduser() if args.output else source.parent/'reading-project'
    dirs = ['source','chapters','notes/chapters','notes/characters','notes/concepts','notes/themes','discussions','state']
    paths = [source, root] + [root/p for p in dirs] + [root/'PROJECT.md', root/'MASTER_INDEX.md']
    for p in paths:
        if any(x.is_symlink() or getattr(x, 'is_junction', lambda: False)() for x in [p,*p.parents]):
            raise ValueError('Links/junctions are not allowed')
    for rel in dirs:
        (root/rel).mkdir(parents=True, exist_ok=True)
    docs = {'PROJECT.md': f'# {args.title or source.stem}\n\nAuthor: {args.author}\nSource: {source.resolve()}\nStatus: initialized\n\nConfirm scope and initialize manifest/state before reading.\n',
            'MASTER_INDEX.md':'# Reading index\n\nNo verified chunks yet.\n'}
    for name, text in docs.items():
        try:
            with (root/name).open('x',encoding='utf-8') as f: f.write(text)
        except FileExistsError:
            if not (root/name).is_file(): raise ValueError('Scaffold path is not a file')
    print(root.resolve())
    return 0


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ValueError,OSError) as exc: raise SystemExit(str(exc))
