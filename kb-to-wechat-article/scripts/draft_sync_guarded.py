#!/usr/bin/env python3
"""Explicit read or guarded in-place update; single-article drafts only."""
import argparse, sys, time, uuid
from safe_common import *
from draft_verify import metadata, verify_draft

def state_read(adir):
    p=local(adir,'sync/state.json',False)
    return read_json(p) if p.exists() else {'versions':[]}

def item_get(media_id,access):
    if not media_id: raise Blocked('请先指定草稿 ID 并拉回')
    d=api('draft/get',access,{'media_id':media_id})
    news=d.get('news_item')
    if not isinstance(news,list) or len(news)!=1 or not isinstance(news[0],dict):
        raise Blocked('仅支持单篇草稿')
    return news[0]

def snapshot(adir,label,markup):
    ident(label)
    rel='sync/from-backend/'+label+'-'+str(time.time_ns())+'-'+uuid.uuid4().hex+'.html'
    p=local(adir,rel,False); p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:f.write(markup)
    return rel

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    for cmd in ('pull','snapshot','status','update'):
        q=sub.add_parser(cmd); q.add_argument('--article-dir',required=True)
        if cmd in ('pull','snapshot'): q.add_argument('--media-id'); q.add_argument('--approve-read',action='store_true')
        if cmd=='snapshot': q.add_argument('--label',required=True)
        if cmd=='update': q.add_argument('--html',required=True,help='Path relative to article directory');q.add_argument('--approve-upload',action='store_true');q.add_argument('--dry-run',action='store_true')
    a=p.parse_args(); adir=root(a.article_dir)
    with lock(adir):
        state=state_read(adir)
        if a.cmd=='status':
            print('已记录草稿：'+str(bool(state.get('media_id')))+'；版本数：'+str(len(state.get('versions',[]))));return 0
        if a.cmd in ('pull','snapshot'):
            if not a.approve_read: raise Blocked('读取微信草稿需要 --approve-read；不会自动联网')
            label=ident(a.label) if a.cmd=='snapshot' else 'pull'
            media_id=a.media_id or state.get('media_id')
            current=item_get(media_id,token()); markup=current.get('content','')
            rel=snapshot(adir,label,markup)
            # Bind baseline to the specific draft, not to an old media ID.
            state.update(media_id=media_id,baseline=current,baseline_media_id=media_id)
            state.setdefault('versions',[]).append({'file':rel,'origin':a.cmd})
            state['versions']=state['versions'][-10:]
            write_json(adir,'sync/state.json',state)
            print('已拉回并保存本地快照；未修改微信草稿。');return 0
        rel=Path(a.html).as_posix()
        markup=check_html(adir,local(adir,rel).read_text(encoding='utf-8'))
        fields=metadata(local(adir,'article.md').read_text(encoding='utf-8'))
        approved(adir,['article.md','cover.png',rel])
        media_id=state.get('media_id'); baseline=state.get('baseline')
        if not media_id or state.get('baseline_media_id')!=media_id or not isinstance(baseline,dict):
            raise Blocked('缺少同一草稿的 pull 基线；先拉回、合并并重新确认')
        if local(adir,'sync/update-pending.json',False).exists():
            raise Blocked('上次更新结果未决；先核对原草稿及收据，不能自动重试')
        if a.dry_run or not a.approve_upload:
            print('本地检查通过；未读取微信、未上传，后台冲突尚未检查。');return 0
        access=token(); current=item_get(media_id,access)
        if current!=baseline:
            snapshot(adir,'conflict',current.get('content',''))
            raise Blocked('后台已变更，请先拉回并合并')
        write_json(adir,'sync/update-pending.json',{'media_id':media_id,'result':'outcome-unknown'})
        payload_html,thumb=prepare(adir,markup,access)
        # Recheck after uploads, immediately before update; API offers no atomic CAS.
        if item_get(media_id,access)!=baseline: raise Blocked('上传图片期间后台发生变化；保留未决记录')
        approved(adir,['article.md','cover.png',rel])
        payload={k:current[k] for k in ('need_open_comment','only_fans_can_comment','content_source_url','show_cover_pic','author','digest') if k in current}
        payload.update(fields,content=payload_html,thumb_media_id=thumb)
        api('draft/update',access,{'media_id':media_id,'index':0,'articles':payload})
        backend=item_get(media_id,access)
        verify=verify_draft({'news_item':[backend]},payload_html,fields)
        after=snapshot(adir,'after-update',backend.get('content',''))
        write_json(adir,'sync/update-receipt.json',dict(verify,media_id=media_id,snapshot=after))
        if not verify['basic_passed']: raise Blocked('原草稿基础回验失败；保留未决标记')
        state.update(baseline=backend)
        state.setdefault('versions',[]).append({'file':after,'origin':'update'});state['versions']=state['versions'][-10:]
        write_json(adir,'sync/state.json',state)
        local(adir,'sync/update-pending.json').unlink()
        print('已原地更新；基础回验通过，图片、封面身份和实际排版仍需人工核对。');return 0

if __name__=='__main__':sys.exit(cli_error(main))
