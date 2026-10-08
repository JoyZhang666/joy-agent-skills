"""Actual rendering of synthetic PDFs; app-level network guards, not OS isolation."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/word-mode'))
SPEC=importlib.util.spec_from_file_location('word_pdf_pages',ROOT/'tools/word-mode/pdf-pages.py')
pdf=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(pdf)

def synthetic_pdf(pages=2,width=110*72/25.4,height=400,font=18):
    """Minimal complete PDF with selectable text, a vector table and RGB image."""
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    pixels=bytes([255,0,0,0,128,255,0,180,0,255,200,0]);image=zlib.compress(pixels)
    objects.append(b'<< /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length '+str(len(image)).encode()+b' >>\nstream\n'+image+b'\nendstream')
    kids=[]
    for i in range(pages):
        page_id=len(objects)+1;content_id=page_id+1;kids.append(str(page_id)+' 0 R')
        objects.append(('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 '+str(width)+' '+str(height)+'] /Resources << /Font << /F1 3 0 R >> /XObject << /Im1 4 0 R >> >> /Contents '+str(content_id)+' 0 R >>').encode())
        content=('BT /F1 18 Tf 25 360 Td (Synthetic page '+str(i+1)+') Tj ET\n'
                 'BT /F1 11 Tf 25 330 Td (Text, table and embedded picture) Tj ET\n'
                 '0 0 0 RG 1 w 25 215 250 90 re S 25 245 m 275 245 l S 25 275 m 275 275 l S 150 215 m 150 305 l S\n'
                 'BT /F1 12 Tf 35 285 Td (Item) Tj 130 0 Td (Value) Tj ET\n'
                 'BT /F1 12 Tf 35 255 Td (Alpha) Tj 130 0 Td (10) Tj ET\n'
                 'BT /F1 12 Tf 35 225 Td (Beta) Tj 130 0 Td (20) Tj ET\n'
                 'q 100 0 0 100 25 80 cm /Im1 Do Q\n'
                 'BT /F1 10 Tf 25 40 Td (No real personal information) Tj ET').encode()
        import re
        content=re.sub(rb'/F1 \d+ Tf',('/F1 '+str(font)+' Tf').encode(),content)
        objects.append(b'<< /Length '+str(len(content)).encode()+b' >>\nstream\n'+content+b'\nendstream')
    objects[1]=('<< /Type /Pages /Count '+str(pages)+' /Kids ['+' '.join(kids)+'] >>').encode()
    output=bytearray(b'%PDF-1.4\n');offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(output));output.extend(str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n')
    xref=len(output);output.extend(('xref\n0 '+str(len(objects)+1)+'\n0000000000 65535 f \n').encode())
    for off in offsets[1:]:output.extend(f'{off:010d} 00000 n \n'.encode())
    output.extend(('trailer\n<< /Size '+str(len(objects)+1)+' /Root 1 0 R >>\nstartxref\n'+str(xref)+'\n%%EOF\n').encode())
    return bytes(output)

class PDFPagesTests(unittest.TestCase):
    def setUp(self):
        self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ,{},clear=True))
        self.stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')))
        self.stack.enter_context(patch('socket.create_connection',side_effect=AssertionError('network forbidden')))
        self.d=Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='pdf-pages-synthetic-')))
        self.source=self.d/'synthetic.pdf';self.source.write_bytes(synthetic_pdf())
    def test_actual_render_text_table_image_and_page_order(self):
        from PIL import Image,ImageStat
        import pypdfium2
        dest=self.d/'article';before=self.source.read_bytes()
        result=pdf.convert(self.source,dest,True,dpi=144)
        self.assertEqual(result['status'],'complete');self.assertEqual(result['page_count'],2)
        self.assertEqual(result['source_sha256'],pdf.sha(before));self.assertFalse(result['uploaded'])
        self.assertEqual(self.source.read_bytes(),before);self.assertEqual((dest/'source.pdf').read_bytes(),before)
        with pypdfium2.PdfDocument(before) as doc:
            page=doc[0];textpage=page.get_textpage()
            try:self.assertIn('Synthetic page 1',textpage.get_text_range())
            finally:textpage.close();page.close()
        for i,item in enumerate(result['pages'],1):
            self.assertEqual(item['page'],i);self.assertEqual(item['file'],f'pages/page-{i:04d}.png')
            path=dest/item['file'];self.assertEqual(item['sha256'],pdf.sha(path.read_bytes()))
            with Image.open(path) as image:
                self.assertEqual(image.size,(624,800));self.assertGreater(max(ImageStat.Stat(image).stddev),10)
                # Embedded square has red and blue quadrants, not merely a blank bitmap.
                self.assertGreater(image.getpixel((75,465))[0],200)
                self.assertGreater(image.getpixel((175,465))[2],200)
        html=(dest/'article.html').read_text(encoding='utf-8')
        self.assertLess(html.index('page-0001.png'),html.index('page-0002.png'))
        self.assertEqual(result['article_html_sha256'],pdf.sha((dest/'article.html').read_bytes()))
    def test_confirmation_required(self):
        with self.assertRaises(pdf.Unsupported):pdf.convert(self.source,self.d/'article')
        self.assertFalse((self.d/'article').exists())
    def test_default_dpi_and_all_mobile_previews(self):
        from PIL import Image
        result=pdf.convert(self.source,self.d/'article',True)
        self.assertEqual(result['dpi'],200)
        self.assertEqual(len(result['preview_images']),6)
        for preview in result['preview_images']:
            with Image.open(self.d/'article'/preview['file']) as image:self.assertEqual(image.width,preview['viewport'])
        self.assertFalse(result['mobile_readability_verified'])
        self.assertTrue((self.d/'article'/'preview.html').is_file())
    def test_a4_width_rejected_before_writing(self):
        self.source.write_bytes(synthetic_pdf(width=210*72/25.4))
        with self.assertRaisesRegex(pdf.Unsupported,'110 mm'):pdf.convert(self.source,self.d/'article',True)
        self.assertFalse((self.d/'article').exists())
    def test_small_text_flag_and_nonzero_cli(self):
        self.source.write_bytes(synthetic_pdf(font=10))
        output=io.StringIO()
        with patch.object(sys,'argv',['test','--input',str(self.source),'--article-dir',str(self.d/'article'),'--confirm-local-export']),contextlib.redirect_stdout(output):self.assertEqual(pdf.main(),2)
        report=json.loads((self.d/'article'/'mobile-check.json').read_text())
        self.assertEqual(report['status'],'needs_review')
        self.assertGreater(report['pages'][0]['small_characters'],0)
        self.assertNotIn('Synthetic page',json.dumps(report))
    def test_image_only_and_rotated_pages_not_silently_passed(self):
        import pypdfium2
        with patch.object(pypdfium2.PdfTextPage,'count_chars',return_value=0):
            result=pdf.convert(self.source,self.d/'image-only',True)
            self.assertEqual(result['mobile_check']['status'],'needs_review')
        with patch.object(pypdfium2.PdfPage,'get_rotation',return_value=90),self.assertRaises(pdf.Unsupported):pdf.convert(self.source,self.d/'rotated',True)
    def test_font_scaling_matrix_is_checked(self):
        import pypdfium2
        def matrix(_,__,ptr):
            ptr._obj.a=0.5;ptr._obj.d=0.5;return 1
        with patch.object(pypdfium2.raw,'FPDFText_GetMatrix',side_effect=matrix):
            result=pdf.convert(self.source,self.d/'scaled',True)
            self.assertGreater(result['mobile_check']['pages'][0]['small_characters'],0)
    def test_measurement_work_is_bounded(self):
        with patch.object(pdf,'MAX_TEXT_CHARS',1),self.assertRaises(pdf.Unsupported):pdf.convert(self.source,self.d/'too-many',True)
        self.assertFalse((self.d/'too-many').exists())
    def test_output_no_overwrite(self):
        dest=self.d/'article';dest.mkdir();(dest/'keep').write_text('keep')
        with self.assertRaises(pdf.Unsupported):pdf.convert(self.source,dest,True)
        self.assertEqual((dest/'keep').read_text(),'keep')
    def test_page_limit(self):
        self.source.write_bytes(synthetic_pdf(pages=31))
        with self.assertRaises(pdf.Unsupported):pdf.convert(self.source,self.d/'article',True)
        self.assertFalse((self.d/'article').exists())
    def test_dimensions_and_dpi_limits(self):
        self.source.write_bytes(synthetic_pdf(pages=1,width=10000))
        with self.assertRaises(pdf.Unsupported):pdf.convert(self.source,self.d/'article',True)
        self.source.write_bytes(synthetic_pdf())
        with self.assertRaises(pdf.Unsupported):pdf.convert(self.source,self.d/'article',True,dpi=300)
    def test_total_pixels_limit(self):
        self.source.write_bytes(synthetic_pdf(pages=30,width=1200,height=1200))
        with self.assertRaises(pdf.Unsupported):pdf.convert(self.source,self.d/'article',True)
        self.assertFalse((self.d/'article').exists())
    def test_file_size_limit(self):
        with patch.object(pdf,'MAX_FILE_BYTES',5),self.assertRaises(pdf.Unsupported):pdf.convert(self.source,self.d/'article',True)
    def test_encrypted_flag_rejected(self):
        import pypdfium2
        with patch.object(pypdfium2.raw,'FPDF_GetSecurityHandlerRevision',return_value=4),self.assertRaises(pdf.Unsupported):pdf.convert(self.source,self.d/'article',True)
        self.assertFalse((self.d/'article').exists())
    def test_actual_encrypted_pdf_rejected(self):
        try:from pypdf import PdfReader,PdfWriter
        except ImportError:self.skipTest('pypdf absent: synthetic encryption fixture unavailable')
        for password in ('','synthetic-password'):
            with self.subTest(password_empty=not password):
                writer=PdfWriter();reader=PdfReader(io.BytesIO(synthetic_pdf()))
                for page in reader.pages:writer.add_page(page)
                writer.encrypt(user_password=password,owner_password='synthetic-owner')
                with self.source.open('wb') as stream:writer.write(stream)
                with self.assertRaises(pdf.Unsupported):pdf.convert(self.source,self.d/'article',True)
                self.assertFalse((self.d/'article').exists())
    def test_forms_rejected(self):
        import pypdfium2
        with patch.object(pypdfium2.raw,'FPDF_GetFormType',return_value=1),self.assertRaises(pdf.Unsupported):pdf.convert(self.source,self.d/'article',True)
    def test_reparse_rejected(self):
        from types import SimpleNamespace
        original=Path.lstat
        def fake(path,*args,**kwargs):return SimpleNamespace(st_file_attributes=0x400) if path==self.source else original(path,*args,**kwargs)
        with patch.object(Path,'is_symlink',return_value=False),patch.object(Path,'lstat',fake),self.assertRaises(pdf.Unsupported):pdf.convert(self.source,self.d/'article',True)
    def test_invalid_pdf_and_safe_error(self):
        self.source.write_bytes(b'not pdf')
        with self.assertRaises(pdf.Unsupported):pdf.convert(self.source,self.d/'article',True)
        output=io.StringIO()
        with patch.object(sys,'argv',['test','--input',str(self.source),'--article-dir',str(self.d/'article'),'--confirm-local-export']),contextlib.redirect_stdout(output):self.assertEqual(pdf.main(),2)
        self.assertNotIn(str(self.source),output.getvalue())

if __name__=='__main__':unittest.main()
