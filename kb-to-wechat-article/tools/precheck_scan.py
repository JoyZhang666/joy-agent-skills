#!/usr/bin/env python3
"""Local precheck. Requires Pillow for image validation; no network or credentials."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from safe_common import Blocked,root,local,ident,check_html,cli_error
from draft_verify import metadata
def main():
    p=argparse.ArgumentParser();p.add_argument('adir');p.add_argument('--selected-theme',required=True);a=p.parse_args()
    adir=root(a.adir);theme=ident(a.selected_theme)
    fields=metadata(local(adir,'article.md').read_text(encoding='utf-8'))
    if any(v.startswith('<') for v in fields.values()):raise Blocked('署名或标题仍为占位符')
    from PIL import Image
    with Image.open(local(adir,'cover.png')) as im:
        if im.format!='PNG' or abs(im.width/im.height-2.35)>=.02:raise Blocked('封面应为约 2.35:1 PNG')
        im.verify()
    check_html(adir,local(adir,'previews/'+theme+'.html').read_text(encoding='utf-8'))
    print('本地基础预检通过；未确认文风、事实、图片身份或微信实际排版。');return 0
if __name__=='__main__':sys.exit(cli_error(main))
