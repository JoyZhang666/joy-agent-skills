#!/usr/bin/env python3
"""Explicit read-only metrics fetch. Unknown/unattributable fields stay null."""
import argparse,datetime as dt,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from safe_common import Blocked,root,write_json,token,request,cli_error,lock
from urllib.parse import quote
ENDPOINTS={'getarticlesummary','getarticletotal'}
def normalize(raw,article_id,title='',public_url='',publish_time=None):
    result=dict(article_id=article_id,title=title,public_url=public_url,publish_time=publish_time,collected_at=dt.datetime.now(dt.timezone.utc).isoformat(),raw_source='wechat_api',read_count=None,like_count=None,share_count=None,favorite_count=None,comment_count=None,completion_rate=None,source_breakdown={})
    # Different endpoint definitions/periods must never be combined or maximized.
    matches=[r for r in raw.get('getarticlesummary',{}).get('list',[]) if isinstance(r,dict) and r.get('msgid')==article_id]
    if len(matches)==1:
        row=matches[0]
        for dest,src in [('read_count','int_page_read_count'),('share_count','share_count'),('favorite_count','add_to_fav_count')]:
            value=row.get(src)
            if type(value) is int and value>=0:result[dest]=value
        result['metric_scope']='one matching summary row; no account-wide or cumulative totals'
    else:result['metric_scope']='unknown: no unique article summary row'
    return result
def main():
    p=argparse.ArgumentParser()
    for key in ('article-dir','begin-date','end-date','article-id'):p.add_argument('--'+key,required=True)
    for key in ('title','public-url','publish-time'):p.add_argument('--'+key,default='')
    p.add_argument('--endpoints',default='getarticlesummary');p.add_argument('--approve-read',action='store_true')
    a=p.parse_args();adir=root(a.article_dir)
    if not a.approve_read:raise Blocked('读取公众号统计需 --approve-read；也可手工提供统计')
    endpoints=a.endpoints.split(',')
    if not endpoints or any(e not in ENDPOINTS for e in endpoints):raise Blocked('仅支持文章 summary/total；不读取全账号汇总')
    begin=dt.date.fromisoformat(a.begin_date);end=dt.date.fromisoformat(a.end_date)
    if begin!=end:raise Blocked('当前只接受单日统计，避免把不同时间范围混合')
    if not a.article_id.strip():raise Blocked('必须提供微信文章 msgid，不能仅凭标题归属数据')
    with lock(adir):
        access=token();raw={}
        for endpoint in endpoints:
            data=request('https://api.weixin.qq.com/datacube/'+endpoint+'?access_token='+quote(access,safe=''),json.dumps({'begin_date':a.begin_date,'end_date':a.end_date}).encode('utf-8'),{'Content-Type':'application/json'})
            if not isinstance(data.get('list'),list):raise Blocked('API 未返回有效统计列表')
            # Keep only this article; never store unrelated authors/articles.
            data={'list':[r for r in data['list'] if isinstance(r,dict) and r.get('msgid')==a.article_id]}
            raw[endpoint]=data
            write_json(adir,'feedback/metrics-raw-'+endpoint+'-'+str(time.time_ns())+'.json',data)
        norm=normalize(raw,a.article_id,a.title,a.public_url,a.publish_time)
        write_json(adir,'feedback/metrics-normalized.json',norm)
        print('读取完成；无法唯一归属的指标保持未知。');return 0
if __name__=='__main__':sys.exit(cli_error(main))
