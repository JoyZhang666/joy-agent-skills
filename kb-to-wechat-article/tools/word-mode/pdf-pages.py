#!/usr/bin/env python3
"""Opt-in local PDF page rasterization. Visual fallback, not editable/lossless Word."""
import argparse
import importlib.metadata
import json
import math
import ctypes
from pathlib import Path
import sys
from prepare import checked_path, Unsupported, sha

MAX_FILE_BYTES=30*1024*1024
MAX_PAGES=30
MAX_SIDE=8192
MAX_PAGE_PIXELS=16_000_000
MAX_TOTAL_PIXELS=100_000_000
VIEWPORTS=(320,390,430)
PREVIEW_MARGIN=16
MIN_TEXT_PX=16
MAX_TEXT_CHARS=200_000


def mobile_check(document):
    """Heuristic PDF checks, not OCR or visual acceptance; no article text logged."""
    import pypdfium2 as pdfium
    pages=[];total=0
    for index in range(len(document)):
        page=document[index];text=None
        try:
            w,h=page.get_size();width_mm=w*25.4/72
            if not 109<=width_mm<=111 or page.get_rotation()!=0:
                raise Unsupported('第 '+str(index+1)+' 页不是约 110 mm 的正向手机版；请在 Word 副本中设置 11 厘米宽、正文 18 磅后重新导出，不要缩放现成 A4 PDF')
            text=page.get_textpage();count=text.count_chars();total+=count
            if total>MAX_TEXT_CHARS:raise Unsupported('PDF 文字检查数量超限，请按章节拆分后再试')
            minimum=None;small=0;outside=0;unknown=0
            for i in range(count):
                code=pdfium.raw.FPDFText_GetUnicode(text.raw,i)
                if not code or chr(code).isspace():continue
                matrix=pdfium.raw.FS_MATRIX()
                ok=pdfium.raw.FPDFText_GetMatrix(text.raw,i,ctypes.byref(matrix))
                font=pdfium.raw.FPDFText_GetFontSize(text.raw,i)
                # Vertical text scale also catches a large-font A4 page shrunk into a small PDF.
                effective=font*math.hypot(matrix.c,matrix.d) if ok else 0
                if not math.isfinite(effective) or effective<=0:unknown+=1;continue
                px=effective*(min(VIEWPORTS)-2*PREVIEW_MARGIN)/w
                minimum=px if minimum is None else min(minimum,px)
                if px<MIN_TEXT_PX:small+=1
                left,bottom,right,top=text.get_charbox(i)
                if left < -1 or right > w+1 or bottom < -1 or top > h+1:outside+=1
            pages.append({'page':index+1,'width_mm':round(width_mm,2),'measurable_characters':count,'min_estimated_text_px_at_320':round(minimum,2) if minimum is not None else None,'small_characters':small,'out_of_page_characters':outside,'unknown_characters':unknown,'needs_review':minimum is None or small>0 or outside>0 or unknown>0})
        finally:
            if text is not None:text.close()
            page.close()
    return {'status':'needs_review' if any(p['needs_review'] for p in pages) else 'checks_passed','viewports':list(VIEWPORTS),'horizontal_padding_px':PREVIEW_MARGIN,'min_text_px':MIN_TEXT_PX,'pages':pages,'visual_verified':False,'limitations':['Font-size estimate covers extractable PDF text only, not image/outline text, formula details or overlap','Page width does not prove correct reflow; compare with source and check every table and picture','Local previews simulate display width; actual WeChat compression and device appearance need review']}

def sizes(document,dpi):
    if not 72<=dpi<=200:raise Unsupported('DPI 仅支持 72 至 200')
    count=len(document)
    if not 1<=count<=MAX_PAGES:raise Unsupported('PDF 页数必须为 1 至 30 页')
    result=[];total=0
    for index in range(count):
        page=document[index]
        try:w,h=page.get_size()
        finally:page.close()
        if not all(math.isfinite(x) and x>0 for x in (w,h)):raise Unsupported('页面尺寸无效')
        width,height=math.ceil(w*dpi/72),math.ceil(h*dpi/72)
        total+=width*height
        if max(width,height)>MAX_SIDE or width*height>MAX_PAGE_PIXELS or total>MAX_TOTAL_PIXELS:
            raise Unsupported('页面尺寸或总像素超过安全上限；请拆分文档或调整字号/页面宽度后重导出')
        result.append((width,height))
    return result

def convert(input_path,article_dir,confirmed=False,dpi=200):
    if not confirmed:raise Unsupported('请先在本机 Word 导出 PDF 并确认页面，再使用 --confirm-local-export')
    source=checked_path(input_path,True);dest=checked_path(article_dir,False)
    if source.suffix.lower()!='.pdf':raise Unsupported('输入必须为本机导出的 PDF')
    if dest.exists():raise Unsupported('输出目录必须全新，不覆盖已有目录')
    if not dest.parent.is_dir():raise Unsupported('请先建立输出目录的父目录')
    if source.stat().st_size>MAX_FILE_BYTES:raise Unsupported('PDF 超过 30 MiB')
    blob=source.read_bytes()
    if len(blob)>MAX_FILE_BYTES or not blob.startswith(b'%PDF-'):raise Unsupported('无效或过大的 PDF 文件')
    import pypdfium2 as pdfium
    from PIL import Image
    try:document=pdfium.PdfDocument(blob)
    except Exception:raise Unsupported('PDF 无法读取，可能加密、损坏或不受支持；请重新从本机 Word 导出') from None
    with document:
        if pdfium.raw.FPDF_GetSecurityHandlerRevision(document.raw)>=0:raise Unsupported('拒绝加密 PDF；请提供确认可转换的未加密本机导出文件')
        if pdfium.raw.FPDF_GetFormType(document.raw)!=0:raise Unsupported('不支持交互表单或 XFA；请先本机导出静态 PDF 并检查内容')
        dimensions=sizes(document,dpi)
        readability=mobile_check(document)
        checked_path(dest.parent,False);dest.mkdir(exist_ok=False)
        with (dest/'source.pdf').open('xb') as f:f.write(blob)
        (dest/'pages').mkdir()
        (dest/'previews').mkdir()
        manifest={'schema_version':1,'status':'incomplete','mode':'visual_pages','source_sha256':sha(blob),'page_count':len(dimensions),'dpi':dpi,'pages':[],'renderer':{'pypdfium2':importlib.metadata.version('pypdfium2'),'Pillow':importlib.metadata.version('Pillow')},'limits':{'max_file_bytes':MAX_FILE_BYTES,'max_pages':MAX_PAGES,'max_side_pixels':MAX_SIDE,'max_page_pixels':MAX_PAGE_PIXELS,'max_total_pixels':MAX_TOTAL_PIXELS},'uploaded':False,'mobile_readability_verified':False,'limitations':['Raster page images are not editable text or lossless Word conversion','No automatic cropping or theme conversion','Dense/small text requires a mobile-width Word layout or larger font and a fresh PDF export','User must inspect every page and mobile preview before use']}
        with (dest/'manifest.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
        manifest['schema_version']=2
        manifest['mobile_check']=readability
        manifest['preview_images']=[]
        for index,(width,height) in enumerate(dimensions):
            page=document[index];bitmap=None;picture=None
            try:
                bitmap=page.render(scale=dpi/72,crop=(0,0,0,0),may_draw_forms=False,draw_annots=True,limit_image_cache=True)
                picture=bitmap.to_pil().convert('RGB')
                if picture.size!=(width,height):raise Unsupported('渲染尺寸与预检不一致')
                file='pages/page-'+str(index+1).zfill(4)+'.png';path=dest/file
                with path.open('xb') as f:picture.save(f,format='PNG')
                # Verify the emitted file is readable; this is not a visual acceptance claim.
                with Image.open(path) as check:check.verify()
                manifest['pages'].append({'page':index+1,'file':file,'width':width,'height':height,'sha256':sha(path.read_bytes())})
                for viewport in VIEWPORTS:
                    inner=viewport-2*PREVIEW_MARGIN
                    scaled=picture.resize((inner,max(1,round(height*inner/width))),Image.Resampling.LANCZOS)
                    canvas=Image.new('RGB',(viewport,scaled.height+2*PREVIEW_MARGIN),'white')
                    try:
                        canvas.paste(scaled,(PREVIEW_MARGIN,PREVIEW_MARGIN))
                        preview='previews/page-'+str(index+1).zfill(4)+'-'+str(viewport)+'.png'
                        with (dest/preview).open('xb') as f:canvas.save(f,format='PNG')
                        manifest['preview_images'].append({'page':index+1,'viewport':viewport,'file':preview,'sha256':sha((dest/preview).read_bytes())})
                    finally:scaled.close();canvas.close()
            finally:
                if picture is not None:picture.close()
                if bitmap is not None:bitmap.close()
                page.close()
        markup='<div id="wenyan" data-mode="visual-pages">\n'+''.join('<p style="margin:0"><img src="'+p['file']+'" alt="第 '+str(p['page'])+' 页" style="display:block;width:100%;height:auto"></p>\n' for p in manifest['pages'])+'</div>\n'
        with (dest/'article.html').open('xb') as f:f.write(markup.encode('utf-8'))
        preview_page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\'; style-src \'unsafe-inline\'; base-uri \'none\'"><title>手机版页图预览</title><style>body{margin:0;padding:16px;background:white}img{display:block;width:100%;height:auto}p{margin:0}</style></head><body>'+markup+'</body></html>'
        with (dest/'preview.html').open('xb') as f:f.write(preview_page.encode('utf-8'))
        with (dest/'mobile-check.json').open('x',encoding='utf-8') as f:json.dump(readability,f,ensure_ascii=False,indent=2)
        manifest['preview_html_sha256']=sha(preview_page.encode('utf-8'))
        manifest.update(status='complete',article_html_sha256=sha(markup.encode('utf-8')))
        # Only replace our own just-created incomplete manifest after all pages succeed.
        temporary=dest/'manifest-complete.tmp'
        with temporary.open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
        temporary.replace(dest/'manifest.json')
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True);parser.add_argument('--article-dir',required=True)
    parser.add_argument('--confirm-local-export',action='store_true');parser.add_argument('--dpi',type=int,default=200)
    args=parser.parse_args()
    try:
        result=convert(args.input,args.article_dir,args.confirm_local_export,args.dpi)
        print('已离线生成 '+str(result['page_count'])+' 张整页图片；未裁剪、未套主题、未上传。')
        print('已生成 320/390/430 像素预览。图片中文字不可编辑；complete 仅指生成完成，仍须手机目检。')
        if result['mobile_check']['status']=='needs_review':
            print('发现小字、边缘文字或无法测量的页面：查看 mobile-check.json 页码和 previews；回 Word 副本加大字号、拆宽表并重导出。禁止将本结果当成可读性验收通过。')
            return 2
        return 0
    except Exception as exc:
        print('PDF 整页转图停止：'+(str(exc) if isinstance(exc,Unsupported) else type(exc).__name__)+'。输入未修改；若已产生目录，请勿将 incomplete 产物当作完成品。')
        print('操作说明见 references/word-fidelity.md；不会自动上传。')
        return 2

if __name__=='__main__':sys.exit(main())
