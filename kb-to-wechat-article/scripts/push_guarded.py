#!/usr/bin/env python3
"""Create one WeChat draft from reviewed local HTML. Default: local checks only."""
import argparse, json, sys
from pathlib import Path
from draft_verify import metadata, verify_draft
from safe_common import *

def main():
    p=argparse.ArgumentParser()
    p.add_argument('adir'); p.add_argument('--theme',required=True)
    p.add_argument('--approve-upload',action='store_true')
    p.add_argument('--dry-run',action='store_true')
    p.add_argument('--css',help='Unsupported; render approved inline styles into the HTML first')
    a=p.parse_args()
    if a.css: raise Blocked('不支持外部 CSS；请先本地渲染并确认 HTML')
    theme=ident(a.theme); adir=root(a.adir)
    rel='previews/'+theme+'.html'
    with lock(adir):
        article=local(adir,'article.md').read_text(encoding='utf-8')
        fields=metadata(article)
        markup=check_html(adir,local(adir,rel).read_text(encoding='utf-8'))
        from PIL import Image
        with Image.open(local(adir,'cover.png')) as im:
            if im.format!='PNG' or abs(im.width/im.height-2.35)>=.02:
                raise Blocked('封面须为约 2.35:1 的 PNG')
            im.verify()
        approved(adir,['article.md','cover.png',rel],theme)
        if a.dry_run or not a.approve_upload:
            print('本地检查通过；未联网、未上传，不代表微信草稿验收。'); return 0
        receipt=local(adir,'push-receipt.json',False)
        if receipt.exists():
            raise Blocked('已有推送收据或未决记录；核对原草稿，不重新创建')
        # Persist intent BEFORE the first request. Ambiguous results never auto-retry.
        record={'result':'outcome-unknown','verification_complete':False}
        write_json(adir,'push-receipt.json',record)
        access=token()
        payload_html,thumb=prepare(adir,markup,access)
        approved(adir,['article.md','cover.png',rel],theme)
        result=api('draft/add',access,{'articles':[dict(fields,content=payload_html,thumb_media_id=thumb)]})
        media_id=result.get('media_id')
        if not media_id: raise Blocked('未获得草稿 ID，保持未决记录')
        record.update(media_id=media_id,result='pushed-unverified')
        write_json(adir,'push-receipt.json',record)
        response=api('draft/get',access,{'media_id':media_id})
        verify=verify_draft(response,payload_html,fields)
        record.update(verify,result='pushed-basic-verified' if verify['basic_passed'] else 'verify-failed')
        write_json(adir,'push-receipt.json',record)
        if not verify['basic_passed']: raise Blocked('原草稿基础回验失败；请勿重推')
        print('已保存微信草稿；基础回验通过，图片身份、封面身份和实际排版仍需人工核对。')
        return 0

if __name__=='__main__': sys.exit(cli_error(main))
