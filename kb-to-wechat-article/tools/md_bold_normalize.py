#!/usr/bin/env python3
"""Conservative CJK bold normalization; skips fenced/inline code, keeps unique backup."""
import argparse,re,sys,time
from pathlib import Path
CLOSE=re.compile(r'\*\*([^*\n]+?)([。！？；，、：」』）])\*\*(?=[^\s<`*])')
def normalize(text):
    changes=[]
    def fix(m):
        changes.append('bold punctuation adjusted')
        return '**'+m[1]+'**'+m[2]
    # Code snippets are literal text, not prose. Conservative fence splitting.
    parts=re.split(r'(?ms)(^[ \t]*(?:```|~~~).*?^[ \t]*(?:```|~~~)[^\n]*$|`+[^`\n]*`+)',text)
    for i in range(0,len(parts),2):parts[i]=CLOSE.sub(fix,parts[i])
    return ''.join(parts),changes
def main():
    p=argparse.ArgumentParser();p.add_argument('path');a=p.parse_args();path=Path(a.path)
    if path.is_symlink():raise ValueError('拒绝修改符号链接')
    text=path.read_text(encoding='utf-8');new,changes=normalize(text)
    if changes:
        backup=path.with_name(path.name+'.bak-normalize-'+str(time.time_ns()))
        with backup.open('x',encoding='utf-8') as f:f.write(text)
        path.write_text(new,encoding='utf-8')
    print('规范化修改数：'+str(len(changes))+'；修改后仍需检查文意和渲染。');return 0
if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:print('规范化停止：'+type(e).__name__);sys.exit(2)
