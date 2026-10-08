"""Synthetic local tests. Network stubs and empty credentials, not OS isolation."""
import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(BASE/'scripts'),str(BASE/'tools')]

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ,{},clear=True))
        self.stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')))
        self.stack.enter_context(patch('socket.create_connection',side_effect=AssertionError('network forbidden')))
        self.tmp=self.stack.enter_context(tempfile.TemporaryDirectory(prefix='wechat-synthetic-'))
        self.d=Path(self.tmp)/'article';self.d.mkdir()
        self.common=importlib.import_module('safe_common')
    def run_cli(self,module,args):
        with patch.object(sys,'argv',['test',*args]),contextlib.redirect_stdout(io.StringIO()):
            return module.main()
    def article(self):
        try:from PIL import Image
        except ImportError:self.skipTest('Pillow absent: PNG-dependent test not executed')
        Image.new('RGB',(470,200),'white').save(self.d/'cover.png')
        (self.d/'article.md').write_text('---\ntitle: "测试文章"\nauthor: "测试作者"\n---\n测试正文',encoding='utf-8')
        (self.d/'previews').mkdir()
        (self.d/'previews/test.html').write_text('<p><img src="cover.png" alt="封面"></p><p>测试正文</p>',encoding='utf-8')
        state={k:True for k in ('topic_confirmed','outline_confirmed','article_finalized','humanizer_passed','quality_gate_passed','cover_confirmed','theme_confirmed','upload_confirmed')}
        state.update(delivery_mode='wechat_draft',selected_theme='test',confirmed_artifacts={rel:self.common.sha(self.d/rel) for rel in ('article.md','cover.png','previews/test.html')})
        (self.d/'workflow-state.json').write_text(json.dumps(state),encoding='utf-8')
    def test_identifier_traversal_and_reserved(self):
        for x in ('../escape','C:\\escape','../','CON','NUL','/tmp/file','a/b'):
            with self.subTest(x=x),self.assertRaises(self.common.Blocked):self.common.ident(x)
    def test_local_paths_are_bounded(self):
        for x in ('../escape','C:\\escape','/escape'):
            with self.subTest(x=x),self.assertRaises(self.common.Blocked):self.common.local(self.d,x,False)
    def test_links_rejected(self):
        dest=Path(self.tmp)/'outside';dest.write_text('private',encoding='utf-8')
        try:(self.d/'link').symlink_to(dest)
        except OSError:self.skipTest('OS does not permit creating test symlink')
        with self.assertRaises(self.common.Blocked):self.common.local(self.d,'link')
    def test_lock_exclusion(self):
        with self.common.lock(self.d):
            with self.assertRaises(self.common.Blocked):
                with self.common.lock(self.d):pass
        self.assertFalse((self.d/'.wechat-operation.lock').exists())
    def test_scanner_rejects_empty_and_markdown(self):
        scan=importlib.import_module('deliverable_scan')
        self.assertTrue(scan.scan_text(''));self.assertTrue(scan.scan_text('<p>**残留**</p>'))
        self.assertFalse(scan.scan_text('<p>正常<strong>加粗</strong></p>'))
        self.assertNotEqual(self.run_cli(scan,[str(self.d/'missing.md')]),0)
    def test_resources_blocked(self):
        (self.d/'cover.png').write_bytes(b'fake')
        for s in ('<img src="https://example.com/x"><p>文</p>','<img src="../secret"><p>文</p>','<img src="cover.png"><script>x</script>','<img src="cover.png"><p style="background:url(../x)">文</p>','<img src="cover.png"><img src="cover.png"><p>文</p>'):
            with self.subTest(s=s),self.assertRaises(self.common.Blocked):self.common.check_html(self.d,s)
    def test_confirmation_hash_changes_block(self):
        self.article();(self.d/'article.md').write_text('changed',encoding='utf-8')
        with self.assertRaises(self.common.Blocked):self.common.approved(self.d,['article.md'])
    def test_no_cache_or_credentials_discovery(self):
        with patch.object(Path,'home',side_effect=AssertionError('no home lookup')):
            with self.assertRaises(self.common.Blocked):self.common.token()
    def test_default_push_is_offline(self):
        self.article();push=importlib.import_module('push_guarded')
        with patch.object(push,'token',side_effect=AssertionError('no token')):
            self.assertEqual(self.run_cli(push,[str(self.d),'--theme','test']),0)
        self.assertFalse((self.d/'push-receipt.json').exists())
    def test_missing_pillow_blocks_push(self):
        self.article();push=importlib.import_module('push_guarded')
        with patch.dict(sys.modules,{'PIL':None}),self.assertRaises(ImportError):
            self.run_cli(push,[str(self.d),'--theme','test'])
    def test_ambiguous_publish_cannot_repeat(self):
        self.article();push=importlib.import_module('push_guarded')
        with patch.object(push,'token',return_value='synthetic'),patch.object(push,'prepare',return_value=('<p>测试正文</p>','synthetic-thumb')),patch.object(push,'api',side_effect=self.common.Blocked('unknown')) as api:
            with self.assertRaises(self.common.Blocked):self.run_cli(push,[str(self.d),'--theme','test','--approve-upload'])
            self.assertEqual(api.call_count,1)
            with self.assertRaises(self.common.Blocked):self.run_cli(push,[str(self.d),'--theme','test','--approve-upload'])
            self.assertEqual(api.call_count,1)
        self.assertEqual(json.loads((self.d/'push-receipt.json').read_text())['result'],'outcome-unknown')
    def test_receipt_survives_verify_failure(self):
        self.article();push=importlib.import_module('push_guarded')
        with patch.object(push,'token',return_value='synthetic'),patch.object(push,'prepare',return_value=('<p>测试正文</p>','synthetic-thumb')),patch.object(push,'api',side_effect=[{'media_id':'synthetic-id'},self.common.Blocked('read failed')]):
            with self.assertRaises(self.common.Blocked):self.run_cli(push,[str(self.d),'--theme','test','--approve-upload'])
        self.assertEqual(json.loads((self.d/'push-receipt.json').read_text())['media_id'],'synthetic-id')
    def test_update_needs_baseline(self):
        self.article();sync=importlib.import_module('draft_sync_guarded')
        with patch.object(sync,'token',side_effect=AssertionError('must block before network')),self.assertRaises(self.common.Blocked):
            self.run_cli(sync,['update','--article-dir',str(self.d),'--html','previews/test.html','--approve-upload'])
    def test_read_requires_explicit_consent(self):
        sync=importlib.import_module('draft_sync_guarded')
        with patch.object(sync,'token',side_effect=AssertionError('no read')),self.assertRaises(self.common.Blocked):
            self.run_cli(sync,['pull','--article-dir',str(self.d),'--media-id','fake'])
    def test_multi_article_read_blocked(self):
        sync=importlib.import_module('draft_sync_guarded')
        with patch.object(sync,'api',return_value={'news_item':[{},{}]}),self.assertRaises(self.common.Blocked):sync.item_get('fake','synthetic')
    def test_conflict_blocks_update(self):
        self.article();sync=importlib.import_module('draft_sync_guarded')
        self.common.write_json(self.d,'sync/state.json',{'media_id':'fake','baseline_media_id':'fake','baseline':{'content':'old'}})
        with patch.object(sync,'token',return_value='synthetic'),patch.object(sync,'item_get',return_value={'content':'new'}),patch.object(sync,'prepare',side_effect=AssertionError('no upload')),self.assertRaises(self.common.Blocked):
            self.run_cli(sync,['update','--article-dir',str(self.d),'--html','previews/test.html','--approve-upload'])
    def test_metrics_exact_attribution(self):
        mod=importlib.import_module('wechat_metrics_fetcher')
        raw={'getarticlesummary':{'list':[{'msgid':'A','int_page_read_count':7},{'msgid':'B','int_page_read_count':999}]},'getbizsummary':{'list':[{'cumulate_user':100000}]}}
        self.assertEqual(mod.normalize(raw,'A')['read_count'],7)
        self.assertIsNone(mod.normalize(raw,'missing')['read_count'])
        raw['getarticlesummary']['list'].append({'msgid':'A','int_page_read_count':8})
        self.assertIsNone(mod.normalize(raw,'A')['read_count'])
    def test_metrics_no_implicit_network(self):
        mod=importlib.import_module('wechat_metrics_fetcher')
        with patch.object(mod,'token',side_effect=AssertionError('no read')),self.assertRaises(self.common.Blocked):self.run_cli(mod,['--article-dir',str(self.d),'--begin-date','2026-01-01','--end-date','2026-01-01','--article-id','fake'])
    def test_verification_is_limited(self):
        mod=importlib.import_module('draft_verify')
        result=mod.verify_draft({'news_item':[{'title':'测试','author':'测试作者','content':'<img src="https://mmbiz.qpic.cn/fake"><p>文</p>','thumb_media_id':'fake'}]},'<img src="cover.png"><p>文</p>',{'title':'测试','author':'测试作者'})
        self.assertTrue(result['basic_passed']);self.assertFalse(result['verification_complete']);self.assertIn('cover_identity',result['unchecked'])
    def test_quoted_metadata(self):
        mod=importlib.import_module('draft_verify')
        fields=mod.metadata('---\ntitle: "测试\\\"标题"\nauthor: 作者\n---\n文')
        self.assertEqual(fields['title'],'测试"标题')
    def test_scheduler_naive_time_beijing(self):
        mod=importlib.import_module('feedback_scheduler')
        self.assertEqual(mod.parse_time('2026-01-01T09:00:00').utcoffset().total_seconds(),28800)
    def test_normalize_skips_code_and_is_idempotent(self):
        mod=importlib.import_module('md_bold_normalize')
        text='**中文。**后文\n```\n**示例。**后\n```\n'
        result,_=mod.normalize(text)
        self.assertIn('**中文**。后文',result);self.assertIn('**示例。**后',result)
        self.assertEqual(mod.normalize(result)[0],result)
    def test_secret_safe_error(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):self.common.cli_error(lambda:(_ for _ in ()).throw(RuntimeError('secret=SYNTHETIC_SECRET')))
        self.assertNotIn('SYNTHETIC_SECRET',output.getvalue())
    def test_proxy_is_blocked(self):
        with patch('urllib.request.getproxies',return_value={'https':'http://private-proxy'}),self.assertRaises(self.common.Blocked):
            self.common.request('https://api.weixin.qq.com/cgi-bin/token')
    def test_unsupported_image_spellings_blocked(self):
        (self.d/'cover.png').write_bytes(b'fake')
        for tag in ('<img src=cover.png>','<img src="cover.png" src="cover.png">','<img src="cover&#46;png">'):
            with self.subTest(tag=tag),self.assertRaises(self.common.Blocked):self.common.check_html(self.d,tag+'<p>文</p>')
    def test_connection_check_no_implicit_network(self):
        mod=importlib.import_module('check_connection')
        with patch.object(mod,'token',side_effect=AssertionError('must not connect')),self.assertRaises(self.common.Blocked):self.run_cli(mod,[])
        with patch.object(mod,'token',return_value='SYNTHETIC_SECRET') as token:
            output=io.StringIO()
            with patch.object(sys,'argv',['test','--approve-read']),contextlib.redirect_stdout(output):self.assertEqual(mod.main(),0)
            self.assertEqual(token.call_count,1);self.assertNotIn('SYNTHETIC_SECRET',output.getvalue())
    def test_prepare_replaces_actual_source(self):
        markup='<img src="cover.png" data-other-src="cover.png"><p>文</p>'
        with patch.object(self.common,'upload_cover',side_effect=[{'url':'https://mmbiz.qpic.cn/synthetic'},{'media_id':'synthetic'}]):
            rendered,_=self.common.prepare(self.d,markup,'synthetic')
        self.assertIn('src="https://mmbiz.qpic.cn/synthetic"',rendered)
        self.assertIn('data-other-src="cover.png"',rendered)
    def test_safe_wechat_error_code(self):
        fake=contextlib.nullcontext(io.StringIO('{"errcode":40164,"errmsg":"SYNTHETIC_SECRET"}'))
        opener=unittest.mock.Mock();opener.open.return_value=fake
        with patch('urllib.request.getproxies',return_value={}),patch('urllib.request.build_opener',return_value=opener):
            with self.assertRaises(self.common.Blocked) as raised:self.common.request('https://api.weixin.qq.com/cgi-bin/token')
        self.assertIn('40164',str(raised.exception));self.assertNotIn('SYNTHETIC_SECRET',str(raised.exception))
    def test_reparse_attribute_blocks_local_file(self):
        from types import SimpleNamespace
        target=self.d/'synthetic-link';target.write_text('synthetic',encoding='utf-8')
        original=Path.lstat
        def fake_stat(path,*args,**kwargs):
            if path==target:return SimpleNamespace(st_file_attributes=0x400)
            return original(path,*args,**kwargs)
        with patch.object(Path,'is_symlink',return_value=False),patch.object(Path,'lstat',fake_stat),self.assertRaises(self.common.Blocked):
            self.common.local(self.d,'synthetic-link')
    def test_quality_gate_accepts_normal_title_and_version(self):
        try:mod=importlib.import_module('post_publish_quality_gate')
        except ImportError:self.skipTest('lxml absent: quality gate test not executed')
        text='<h1>产品更新</h1><p>产品 v2.0 支持新的功能。</p><img src="cover.png"><p style="border-top:1px solid">AI Agent：一个技术术语。</p>'
        issues,_=mod.audit(mod.html.fragment_fromstring(text,create_parent='div'),text,'产品更新')
        self.assertEqual(issues,[])
    def test_quality_gate_empty_fails(self):
        try:mod=importlib.import_module('post_publish_quality_gate')
        except ImportError:self.skipTest('lxml absent: quality gate test not executed')
        path=self.d/'empty.html';path.write_text('',encoding='utf-8')
        self.assertEqual(self.run_cli(mod,['--html',str(path),'--title','普通标题']),1)

if __name__=='__main__':unittest.main()
