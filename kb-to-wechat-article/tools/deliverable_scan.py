#!/usr/bin/env python3
"""Bounded heuristic Markdown-residue check for rendered HTML, not release approval."""
import argparse, html, re, sys
from pathlib import Path
PATTERNS=[r'\*\*[^*\n]+\*\*',r'(?m)^\s*#{1,6}\s+\S',r'\[[^\]\n]{1,80}\]\([^)\n]{1,200}\)',r'(?m)^\s*```',r'~~[^~\n]+~~',r'(?m)^\|[\s:|-]{3,}\|$']
def visible_text(raw):
    t=re.sub(r'<(style|script)[^>]*>.*?</\1>','',raw,flags=re.S|re.I)
    t=re.sub(r'<!--.*?-->','',t,flags=re.S)
    t=re.sub(r'<br\s*/?>','\n',t,flags=re.I)
    t=re.sub(r'</(?:p|div|section|h[1-6]|li|blockquote|tr)>','\n',t,flags=re.I)
    return html.unescape(re.sub(r'<[^>]+>','',t))
def scan_text(raw):
    text=visible_text(raw)
    hits=['empty body'] if not text.strip() else []
    hits += ['Markdown residue'] if any(re.search(p,text) for p in PATTERNS) else []
    if re.search(r'(?m)^\s*[-*]\s+\S[^\n]*\n\s*[-*]\s+\S',text):hits.append('list residue')
    return hits
def scan_html(path):
    return scan_text(Path(path).read_text(encoding='utf-8'))
def main():
    p=argparse.ArgumentParser();p.add_argument('target');a=p.parse_args()
    target=Path(a.target)
    files=sorted(target.glob('*.html')) if target.is_dir() else [target]
    if not files or any(not f.is_file() or f.suffix.lower()!='.html' for f in files):
        print('未执行检查：需要存在的 HTML 文件');return 2
    hits=[]
    for f in files:hits.extend(scan_html(f))
    print('残留扫描失败' if hits else 'Markdown 残留扫描通过；不代表完整发布验收')
    return 1 if hits else 0
if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,UnicodeError):print('文件无法读取');sys.exit(2)
