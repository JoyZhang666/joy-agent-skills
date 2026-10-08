#!/usr/bin/env python3
"""Opt-in local PDF page rasterization. Visual fallback, not editable/lossless Word."""
import argparse
import importlib.metadata
import json
import math
from pathlib import Path
import sys
from prepare import checked_path, Unsupported, sha

MAX_FILE_BYTES=30*1024*1024
MAX_PAGES=30
MAX_SIDE=8192
MAX_PAGE_PIXELS=16_000_000
MAX_TOTAL_PIXELS=100_000_000

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

def convert(input_path,article_dir,confirmed=False,dpi=144):
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
        checked_path(dest.parent,False);dest.mkdir(exist_ok=False)
        with (dest/'source.pdf').open('xb') as f:f.write(blob)
        (dest/'pages').mkdir()
        manifest={'schema_version':1,'status':'incomplete','mode':'visual_pages','source_sha256':sha(blob),'page_count':len(dimensions),'dpi':dpi,'pages':[],'renderer':{'pypdfium2':importlib.metadata.version('pypdfium2'),'Pillow':importlib.metadata.version('Pillow')},'limits':{'max_file_bytes':MAX_FILE_BYTES,'max_pages':MAX_PAGES,'max_side_pixels':MAX_SIDE,'max_page_pixels':MAX_PAGE_PIXELS,'max_total_pixels':MAX_TOTAL_PIXELS},'uploaded':False,'mobile_readability_verified':False,'limitations':['Raster page images are not editable text or lossless Word conversion','No automatic cropping or theme conversion','Dense/small text requires a mobile-width Word layout or larger font and a fresh PDF export','User must inspect every page and mobile preview before use']}
        with (dest/'manifest.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
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
            finally:
                if picture is not None:picture.close()
                if bitmap is not None:bitmap.close()
                page.close()
        markup='<div id="wenyan" data-mode="visual-pages">\n'+''.join('<p style="margin:0"><img src="'+p['file']+'" alt="第 '+str(p['page'])+' 页" style="display:block;width:100%;height:auto"></p>\n' for p in manifest['pages'])+'</div>\n'
        with (dest/'article.html').open('xb') as f:f.write(markup.encode('utf-8'))
        manifest.update(status='complete',article_html_sha256=sha(markup.encode('utf-8')))
        # Only replace our own just-created incomplete manifest after all pages succeed.
        temporary=dest/'manifest-complete.tmp'
        with temporary.open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
        temporary.replace(dest/'manifest.json')
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True);parser.add_argument('--article-dir',required=True)
    parser.add_argument('--confirm-local-export',action='store_true');parser.add_argument('--dpi',type=int,default=144)
    args=parser.parse_args()
    try:
        result=convert(args.input,args.article_dir,args.confirm_local_export,args.dpi)
        print('已离线生成 '+str(result['page_count'])+' 张整页图片；未裁剪、未套主题、未上传。')
        print('这是视觉保真图片替代，文字不可直接编辑，也不宣称无损。请逐页检查；手机上小字太密时，请改 Word 手机版宽度或字号，再导出 PDF。')
        return 0
    except Exception as exc:
        print('PDF 整页转图停止：'+(str(exc) if isinstance(exc,Unsupported) else type(exc).__name__)+'。输入未修改；若已产生目录，请勿将 incomplete 产物当作完成品。')
        print('操作说明见 references/word-fidelity.md；不会自动上传。')
        return 2

if __name__=='__main__':sys.exit(main())
