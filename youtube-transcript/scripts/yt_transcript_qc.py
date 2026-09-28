#!/usr/bin/env python3
"""Heuristic transcript QC; never proof of full source coverage."""
import argparse
from collections import Counter
import json
import re
from pathlib import Path


def check_text(text, anchors=(), max_gram=2):
    clean = re.sub(r'\s+', '', text)
    grams = Counter(clean[i:i+20] for i in range(max(0,len(clean)-19)))
    maximum = max(grams.values(), default=0)
    missing = [x for x in anchors if x.strip() and x.strip() not in text]
    return {'ok': bool(clean) and maximum <= max_gram and not missing,
            'empty': not bool(clean), 'max_20gram': maximum, 'missing_anchors': missing,
            'human_review_required': True}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('path')
    ap.add_argument('--anchors',default='');ap.add_argument('--max-gram',type=int,default=2)
    args=ap.parse_args()
    if args.max_gram<1:ap.error('--max-gram must be positive')
    text=Path(args.path).read_text(encoding='utf-8')
    # Generated transcripts have a header separated by this marker.
    if '\n<!-- transcript -->\n' in text:text=text.split('\n<!-- transcript -->\n',1)[1]
    result=check_text(text,args.anchors.split(','),args.max_gram)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ok'] else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError) as exc:raise SystemExit(str(exc))
