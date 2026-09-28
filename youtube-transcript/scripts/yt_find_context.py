#!/usr/bin/env python3
"""Locate exact keyword context in a local UTF-8 transcript."""
import argparse
from pathlib import Path
import re


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('path');ap.add_argument('keywords',nargs='+')
    ap.add_argument('--ctx',type=int,default=50);args=ap.parse_args()
    if not 0<=args.ctx<=2000:ap.error('--ctx must be 0..2000')
    text=Path(args.path).read_text(encoding='utf-8')
    for word in args.keywords:
        if not word:continue
        for m in re.finditer(re.escape(word),text):
            print(f'{word} @ {m.start()}: '+text[max(0,m.start()-args.ctx):m.end()+args.ctx])
    return 0


if __name__=='__main__':raise SystemExit(main())
