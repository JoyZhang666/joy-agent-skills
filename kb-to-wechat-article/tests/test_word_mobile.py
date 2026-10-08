"""Synthetic mobile-copy regressions; no Office automation or external requests."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile
import test_word_prepare as fixtures
from test_word_prepare import docx,prepare,PNG,drawing

SPEC=importlib.util.spec_from_file_location('word_mobile',Path(__file__).resolve().parents[1]/'tools/word-mode/mobile-copy.py')
mobile=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(mobile)


import unittest
class MobileTests(unittest.TestCase):
    setUp=fixtures.WordPrepareTests.setUp

    def test_text_media_equation_merge_and_namespace_preserved(self):
        body='<w:p><w:r><w:rPr><w:b/><w:color w:val="C00000"/><w:sz w:val="22"/></w:rPr><w:t>中文 123.45</w:t>'+drawing('x')+'</w:r></w:p><w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="6000"/><w:gridCol w:w="6000"/></w:tblGrid><w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/><w:tcW w:w="12000" w:type="dxa"/></w:tcPr><w:p><w:r><w:t>合并表格</w:t></w:r></w:p></w:tc></w:tr></w:tbl><w:p><m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:r><m:t>x</m:t></m:r></m:oMath></w:p><w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:left="1440" w:right="1440"/><w:cols w:num="2"/></w:sectPr>'
        blob=docx(body,{'x':('image.png',PNG)})
        result,report=mobile.convert(blob)
        with zipfile.ZipFile(io.BytesIO(blob)) as old,zipfile.ZipFile(io.BytesIO(result)) as new:
            self.assertEqual(set(old.namelist()),set(new.namelist()))
            for name in old.namelist():
                if name!='word/document.xml':self.assertEqual(old.read(name),new.read(name))
            tree=prepare.xml(new.read('word/document.xml'))
            text=''.join(n.text or '' for n in tree.iter() if n.tag==prepare.q(prepare.W,'t'))
            self.assertEqual(text,'中文 123.45合并表格')
            self.assertEqual(tree.find('.//'+prepare.q(prepare.W,'pgSz')).get(prepare.q(prepare.W,'w')),'6236')
            self.assertTrue(all(n.get(prepare.q(prepare.W,'val'))=='36' for n in tree.iter(prepare.q(prepare.W,'sz'))))
            self.assertEqual(tree.find('.//'+prepare.q(prepare.W,'gridSpan')).get(prepare.q(prepare.W,'val')),'2')
            self.assertIn(b'm:oMath',new.read('word/document.xml'))
        self.assertTrue(report['text_preserved']);self.assertFalse(report['visual_verified'])
    def test_existing_large_font_and_all_sections(self):
        blob=docx('<w:p><w:pPr><w:sectPr><w:pgSz w:w="20000" w:h="17000"/></w:sectPr></w:pPr><w:r><w:rPr><w:sz w:val="48"/></w:rPr><w:t>Heading</w:t></w:r></w:p><w:sectPr/>')
        out,report=mobile.convert(blob)
        with zipfile.ZipFile(io.BytesIO(out)) as archive:
            tree=prepare.xml(archive.read('word/document.xml'))
            self.assertTrue(all(n.get(prepare.q(prepare.W,'w'))=='6236' for n in tree.iter(prepare.q(prepare.W,'pgSz'))))
            self.assertEqual(tree.find('.//'+prepare.q(prepare.W,'r')+'/'+prepare.q(prepare.W,'rPr')+'/'+prepare.q(prepare.W,'sz')).get(prepare.q(prepare.W,'val')),'48')
        self.assertEqual(report['section_count'],2)
    def test_large_inline_image_fits_page_without_changing_bytes(self):
        markup=drawing('x').replace('cx="100" cy="100"','cx="7200000" cy="3600000"')
        result,_=mobile.convert(docx('<w:p><w:r>'+markup+'</w:r></w:p>',{'x':('image.png',PNG)}))
        with zipfile.ZipFile(io.BytesIO(result)) as archive:
            tree=prepare.xml(archive.read('word/document.xml'));extent=tree.find('.//'+prepare.q(prepare.WP,'extent'))
            self.assertEqual((extent.get('cx'),extent.get('cy')),('3600000','1800000'))
            self.assertEqual(archive.read('word/media/image.png'),PNG)
    def test_tracked_changes_stop_with_remedy(self):
        for markup in ('<w:ins/>','<w:del/>','<w:tblPrChange/>','<w:commentReference/>'):
            with self.subTest(markup=markup),self.assertRaisesRegex(mobile.Unsupported,'审阅'):mobile.convert(docx('<w:p>'+markup+'</w:p>'))
    def test_external_resource_and_zip_escape_rejected(self):
        rel='<Relationships xmlns="'+prepare.REL+'"><Relationship Id="x" Type="'+prepare.R+'/image" Target="https://example.invalid/x" TargetMode="External"/></Relationships>'
        with self.assertRaises(mobile.Unsupported):mobile.convert(docx('<w:p/>',rel_override=rel))
        with self.assertRaises(mobile.Unsupported):mobile.convert(docx('<w:p/>',extra={'../bad':b'x'}))
    def test_internal_parent_target_cannot_escape_package(self):
        rel='<Relationships xmlns="'+prepare.REL+'"><Relationship Id="x" Type="'+prepare.R+'/customXml" Target="../../outside.xml"/></Relationships>'
        with self.assertRaises(mobile.Unsupported):mobile.convert(docx('<w:p/>',rel_override=rel))
    def test_active_fields_rejected(self):
        for field in ('DDEAUTO','INCLUDETEXT','MACROBUTTON'):
            with self.subTest(field=field),self.assertRaisesRegex(mobile.Unsupported,'静态内容'):mobile.convert(docx('<w:p><w:r><w:instrText>'+field+' example.invalid</w:instrText></w:r></w:p>'))
    def test_confirmation_no_overwrite_and_original_unchanged(self):
        source=self.d/'原稿.docx';source.write_bytes(docx('<w:p><w:r><w:t>原文</w:t></w:r></w:p>'));before=source.read_bytes()
        with self.assertRaises(mobile.Unsupported):mobile.prepare(source,self.d/'out')
        result=mobile.prepare(source,self.d/'out',True)
        with self.assertRaises(mobile.Unsupported):mobile.prepare(source,self.d/'out',True)
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual((self.d/'out'/'source.docx').read_bytes(),before)
        self.assertEqual(result['status'],'needs_editor_review')
        self.assertNotIn(str(source),json.dumps(result))


if __name__=='__main__':unittest.main()
