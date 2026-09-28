#!/usr/bin/env python3
"""Split UTF-8 text without dropping text before the first heading."""
import argparse
import re
from pathlib import Path


def split_units(text, pattern):
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if not text.strip():
        raise ValueError('Source is empty or whitespace only')
    if any(m.start() == m.end() for m in matches):
        raise ValueError('Heading pattern must not match empty text')
    starts = [m.start() for m in matches]
    if not starts or starts[0] != 0:
        starts.insert(0, 0)
    ends = starts[1:] + [len(text)]
    return [(text[a:b].splitlines()[0] if text[a:b].splitlines() else '', text[a:b])
            for a, b in zip(starts, ends)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source')
    ap.add_argument('output_dir')
    ap.add_argument('--pattern', default=r'^(#{1,3}\s+.+|第[一二三四五六七八九十百零0-9]+[章节回].*)$')
    ap.add_argument('--force', action='store_true', help='Explicitly replace existing numbered files')
    args = ap.parse_args()
    source = Path(args.source).expanduser()
    output = Path(args.output_dir).expanduser()
    for p in (source, output):
        if any(x.is_symlink() or getattr(x, 'is_junction', lambda: False)() for x in [p, *p.parents]):
            raise ValueError('Links/junctions are not allowed')
    if not source.is_file():
        raise ValueError('Source must be a regular file')
    text = source.read_bytes().decode('utf-8')
    units = split_units(text, args.pattern)
    targets = [output / f'{i:03d}.md' for i in range(1, len(units)+1)]
    for p in targets:
        if p.is_symlink() or p.resolve() == source.resolve():
            raise ValueError('Unsafe destination')
        if p.exists() and (not args.force or not p.is_file()):
            raise ValueError('Destination exists; review it before using --force')
    output.mkdir(parents=True, exist_ok=True)
    for p, (_, body) in zip(targets, units):
        mode = 'wb' if args.force else 'xb'
        with p.open(mode) as f:
            f.write(body.encode('utf-8'))
    print(f'Wrote {len(units)} units; concatenation preserves input text exactly')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, UnicodeError, re.error) as exc:
        raise SystemExit(str(exc))
