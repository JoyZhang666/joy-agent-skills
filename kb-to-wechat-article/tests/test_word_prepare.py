"""Synthetic OOXML only; network disabled in-process, not OS isolation."""
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC=importlib.util.spec_from_file_location('word_prepare',Path(__file__).resolve().parents[1]/'tools/word-mode/prepare.py')
prepare=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(prepare)
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lZkAAAAASUVORK5CYII=')
W=prepare.W;R=prepare.R;A=prepare.A;WP=prepare.WP;PIC=prepare.PIC

def drawing(rid):
    return '<w:drawing><wp:inline><wp:extent cx="100" cy="100"/><wp:docPr id="1" name="synthetic"/><a:graphic><a:graphicData uri="'+PIC+'"><pic:pic><pic:nvPicPr><pic:cNvPr id="1" name="synthetic"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="'+rid+'"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="100" cy="100"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing>'

def docx(body,images=None,extra=None,rel_override=None):
    images=images or {}
    types='<Types xmlns="'+prepare.CT+'"><Default Extension="png" ContentType="image/png"/><Default Extension="jpg" ContentType="image/jpeg"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    rootrels='<Relationships xmlns="'+prepare.REL+'"><Relationship Id="doc" Type="'+R+'/officeDocument" Target="word/document.xml"/></Relationships>'
    rels='<Relationships xmlns="'+prepare.REL+'">'+''.join('<Relationship Id="'+rid+'" Type="'+R+'/image" Target="media/'+name+'"/>' for rid,(name,data) in images.items())+'</Relationships>'
    document='<w:document xmlns:w="'+W+'" xmlns:r="'+R+'" xmlns:a="'+A+'" xmlns:wp="'+WP+'" xmlns:pic="'+PIC+'"><w:body>'+body+'</w:body></w:document>'
    files={'[Content_Types].xml':types.encode(),'_rels/.rels':rootrels.encode(),'word/document.xml':document.encode(),'word/_rels/document.xml.rels':(rel_override or rels).encode()}
    files.update({'word/media/'+name:data for name,data in images.values()});files.update(extra or {})
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    return stream.getvalue()

class WordPrepareTests(unittest.TestCase):
    def setUp(self):
        self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ,{},clear=True))
        self.stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')))
        self.stack.enter_context(patch('socket.create_connection',side_effect=AssertionError('network forbidden')))
        self.d=Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='word-synthetic-')))
    def test_chinese_whitespace_emphasis_breaks_and_image_order(self):
        body='<w:p><w:pPr><w:pStyle w:val="Heading2"/><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/><w:i/><w:u w:val="single"/></w:rPr><w:t xml:space="preserve"> 中文 &amp; &lt;文字&gt;  </w:t><w:tab/><w:t>尾部</w:t><w:br/>'+drawing('image1')+'<w:t>图片之后</w:t></w:r></w:p><w:p/>'
        blob=docx(body,{'image1':('one.png',PNG)})
        source=self.d/'input.docx';source.write_bytes(blob);dest=self.d/'article'
        prepare.prepare(source,dest)
        records=json.loads((dest/'source-paragraphs.json').read_text(encoding='utf-8'))
        self.assertEqual(records[0]['text'],' 中文 & <文字>  \t尾部\n图片之后')
        self.assertEqual(records[0]['tag'],'h2');self.assertEqual(records[1]['text'],'')
        markup=(dest/'source.html').read_text(encoding='utf-8')
        self.assertIn('id="wenyan"',markup);self.assertIn('data-pid="p0001"',markup)
        self.assertIn('<strong><em><u>',markup);self.assertIn('&lt;文字&gt;',markup)
        self.assertLess(markup.index('<img'),markup.index('图片之后'));self.assertIn('<p data-pid="p0002"',markup)
        self.assertEqual((dest/'media/image0001.png').read_bytes(),PNG)
        self.assertEqual(source.read_bytes(),blob);self.assertEqual((dest/'source.docx').read_bytes(),blob)
        check=json.loads((dest/'source-check.json').read_text(encoding='utf-8'))
        self.assertEqual(check['source_sha256'],hashlib.sha256(blob).hexdigest())
        self.assertEqual(check['source_html_sha256'],hashlib.sha256((dest/'source.html').read_bytes()).hexdigest())
        self.assertIn('<p data-pid="p0002" style="white-space:pre-wrap"></p>',markup)
        self.assertEqual(check['images'][0]['sha256'],hashlib.sha256(PNG).hexdigest())
    def test_multiple_images_order_and_duplicate_reference(self):
        body='<w:p><w:r>'+drawing('b')+drawing('a')+drawing('b')+'</w:r></w:p>'
        _,records,check,media=prepare.convert(docx(body,{'a':('a.png',PNG),'b':('b.png',PNG)}))
        self.assertEqual(records[0]['images'],['media/image0001.png','media/image0002.png','media/image0001.png'])
        self.assertEqual(len(check['images']),2);self.assertEqual(len(media),2)
    def test_fake_extension_rejected(self):
        blob=docx('<w:p><w:r>'+drawing('x')+'</w:r></w:p>',{'x':('fake.jpg',PNG)})
        with self.assertRaises(prepare.Unsupported):prepare.convert(blob)
    def test_unknown_body_and_run_structures_rejected(self):
        for body in ('<w:tbl/>','<w:p>游离文字</w:p>','<w:p><w:hyperlink/></w:p>','<w:p><w:r><w:fldChar/></w:r></w:p>','<w:p><w:ins/></w:p>','<w:p><w:pPr><w:numPr/></w:pPr></w:p>','<w:p><w:r><w:footnoteReference/></w:r></w:p>'):
            with self.subTest(body=body),self.assertRaises(prepare.Unsupported):prepare.convert(docx(body))
    def test_external_relation_rejected(self):
        rel='<Relationships xmlns="'+prepare.REL+'"><Relationship Id="x" Type="'+R+'/image" Target="https://example.invalid/private" TargetMode="External"/></Relationships>'
        with self.assertRaises(prepare.Unsupported):prepare.convert(docx('<w:p/>',rel_override=rel))
    def test_doctype_rejected_in_unused_part(self):
        for payload in (b'<!DOCTYPE x [<!ENTITY x "bad">]><x/>','<!DOCTYPE x><x/>'.encode('utf-16')):
            with self.subTest(payload=payload),self.assertRaises(prepare.Unsupported):prepare.convert(docx('<w:p/>',extra={'docProps/custom.xml':payload}))
    def test_zip_traversal_and_macro_rejected(self):
        for name in ('../escape.txt','/escape.txt','word\\escape.txt','word/vbaProject.bin'):
            # ZipInfo normalizes Windows separators during fixture construction;
            # replace equal-length stored names in both headers to test raw ZIP input.
            blob=docx('<w:p/>',extra={name:b'not executable'})
            if '\\' in name:blob=blob.replace(name.replace('\\','/').encode(),name.encode())
            with self.subTest(name=name),self.assertRaises(prepare.Unsupported):prepare.convert(blob)
    def test_zip_compression_bomb_rejected(self):
        with self.assertRaises(prepare.Unsupported):prepare.convert(docx('<w:p/>',extra={'bomb.txt':b'0'*1000000}))
    def test_no_overwrite(self):
        source=self.d/'input.docx';source.write_bytes(docx('<w:p/>'))
        dest=self.d/'existing';dest.mkdir();(dest/'keep').write_text('keep')
        with self.assertRaises(prepare.Unsupported):prepare.prepare(source,dest)
        self.assertEqual((dest/'keep').read_text(),'keep');self.assertFalse((dest/'source.docx').exists())
    def test_failure_does_not_create_output(self):
        source=self.d/'input.docx';source.write_bytes(docx('<w:tbl/>'));before=source.read_bytes()
        with self.assertRaises(prepare.Unsupported):prepare.prepare(source,self.d/'article')
        self.assertFalse((self.d/'article').exists());self.assertEqual(source.read_bytes(),before)
    def test_simulated_reparse_rejected(self):
        from types import SimpleNamespace
        source=self.d/'input.docx';source.write_bytes(docx('<w:p/>'))
        original=Path.lstat
        def fake(path,*args,**kwargs):
            return SimpleNamespace(st_file_attributes=0x400) if path==source else original(path,*args,**kwargs)
        with patch.object(Path,'is_symlink',return_value=False),patch.object(Path,'lstat',fake),self.assertRaises(prepare.Unsupported):prepare.checked_path(source,True)
    def test_multicolumn_and_custom_columns_rejected(self):
        for columns in ('<w:cols w:num="2"/>','<w:cols w:num="1" w:equalWidth="0"/>','<w:cols><w:col w:w="3000"/><w:col w:w="3000"/></w:cols>'):
            with self.subTest(columns=columns),self.assertRaises(prepare.Unsupported):
                prepare.convert(docx('<w:p><w:r><w:t>正文</w:t></w:r></w:p><w:sectPr>'+columns+'</w:sectPr>'))
        for columns in ('<w:cols/>','<w:cols w:num="1" w:space="720"/>'):
            with self.subTest(single_column=columns):
                _,records,_,_=prepare.convert(docx('<w:p><w:r><w:t>正文</w:t></w:r></w:p><w:sectPr>'+columns+'</w:sectPr>'))
                self.assertEqual(records[0]['text'],'正文')

if __name__=='__main__':unittest.main()
