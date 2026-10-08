#!/usr/bin/env python3
"""Create a private 110 mm DOCX copy, never overwrite or export the original."""
import argparse
import io
import json
import re
import sys
import zipfile
from xml.dom import minidom
from prepare import W, WP, A, PIC, MAX_ARCHIVE, Unsupported, checked_path, package, sha

WIDTH_MM=110
MARGIN_MM=5
FONT_PT=18
TWIPS_PER_MM=1440/25.4
ORDER={
    'sectPr':'headerReference footerReference footnotePr endnotePr type pgSz pgMar paperSrc pgBorders lnNumType pgNumType cols formProt vAlign noEndnote titlePg textDirection bidi rtlGutter docGrid printerSettings sectPrChange'.split(),
    'pPr':'pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange'.split(),
    'rPr':'rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath rPrChange'.split(),
    'tblPr':'tblStyle tblpPr tblOverlap bidiVisual tblStyleRowBandSize tblStyleColBandSize tblW jc tblCellSpacing tblInd tblBorders shd tblLayout tblCellMar tblLook tblCaption tblDescription tblPrChange'.split(),
}


def direct(node, name):
    return [n for n in node.childNodes if n.nodeType==n.ELEMENT_NODE and n.namespaceURI==W and n.localName==name]


def element(document, parent, name, first=False):
    found=direct(parent,name)
    if len(found)>1:raise Unsupported('重复的排版属性，请在原编辑器中另存普通 DOCX 再试')
    if found:return found[0]
    node=document.createElementNS(W,'w:'+name)
    order=ORDER.get(parent.localName,[])
    following=next((n for n in parent.childNodes if n.nodeType==n.ELEMENT_NODE and n.namespaceURI==W and n.localName in order and name in order and order.index(n.localName)>order.index(name)),None)
    if following is not None:parent.insertBefore(node,following)
    elif first and parent.firstChild:parent.insertBefore(node,parent.firstChild)
    else:parent.appendChild(node)
    return node


def attrs(node, **values):
    for key,value in values.items():node.setAttributeNS(W,'w:'+key,str(value))


def integer(node, name, default):
    value=node.getAttributeNS(W,name)
    try:return int(value) if value else default
    except ValueError:raise Unsupported('排版尺寸不是有效整数，请在原编辑器重新保存') from None


def convert(blob):
    # Validate all archive/XML parts and relationships before any transformation.
    parts,parsed,_,_=package(blob,('header','footer','footnotes','endnotes','comments','commentsExtended','customXml','customXmlProps','thumbnail','stylesWithEffects'),normalize_internal_targets=True)
    review={'ins','del','moveFrom','moveTo','rPrChange','pPrChange','sectPrChange','tblPrChange','tblGridChange','trPrChange','tcPrChange','numberingChange','cellIns','cellDel','cellMerge','commentReference','commentRangeStart'}
    for name,tree in parsed.items():
        if 'comment' in name.lower() or any(n.tag.startswith('{'+W+'}') and n.tag.split('}',1)[1] in review for n in tree.iter()):
            raise Unsupported('有修订或批注；请在副本的“审阅”中决定接受/拒绝修改及批注处理，另存最终正文后重试。“无标记”仅隐藏，不等于处理完成')
        fields=''.join((n.text or '') if n.tag=='{'+W+'}instrText' else n.get('{'+W+'}instr','') for n in tree.iter())
        if re.search(r'DDEAUTO|DDE|INCLUDETEXT|INCLUDEPICTURE|DATABASE|LINK|MACROBUTTON',fields,re.I):
            raise Unsupported('包含可能访问外部资源或执行动作的域；请在可信原编辑器中核对并转换为静态内容后重试')
    document=minidom.parseString(parts['word/document.xml'])
    document.documentElement.setAttribute('xmlns:w',W)
    bodies=document.getElementsByTagNameNS(W,'body')
    if len(bodies)!=1:raise Unsupported('无效 DOCX 正文')
    body=bodies[0]
    sections=list(body.getElementsByTagNameNS(W,'sectPr'))
    if not sections:sections=[element(document,body,'sectPr')]
    for section in sections:
        size=element(document,section,'pgSz')
        # Keep page height, but normalize orientation and every section's width.
        attrs(size,w=round(WIDTH_MM*TWIPS_PER_MM),h=max(integer(size,'h',11339),round(100*TWIPS_PER_MM)),orient='portrait')
        margins=element(document,section,'pgMar')
        attrs(margins,left=round(MARGIN_MM*TWIPS_PER_MM),right=round(MARGIN_MM*TWIPS_PER_MM),gutter=0)
        for name in ('top','bottom','header','footer'):
            if not margins.hasAttributeNS(W,name):attrs(margins,**{name:round(5*TWIPS_PER_MM)})
        columns=element(document,section,'cols')
        for child in list(columns.childNodes):columns.removeChild(child)
        attrs(columns,num=1,equalWidth=1)
    paragraphs=list(body.getElementsByTagNameNS(W,'p'))
    for paragraph in paragraphs:
        properties=element(document,paragraph,'pPr',first=True)
        attrs(element(document,properties,'spacing'),line=360,lineRule='auto')
        attrs(element(document,properties,'snapToGrid'),val=0)
        # Paragraph mark also governs empty paragraphs and inherited text size.
        marks=element(document,properties,'rPr')
        for name in ('sz','szCs'):attrs(element(document,marks,name),val=FONT_PT*2)
    for run in body.getElementsByTagNameNS(W,'r'):
        properties=element(document,run,'rPr',first=True)
        for name in ('sz','szCs'):
            size=element(document,properties,name)
            attrs(size,val=max(FONT_PT*2,integer(size,'val',FONT_PT*2)))
    # Do not guess floating-object coordinates, split tables, or crop images.
    # Fixed-height table rows may clip enlarged text; let Word increase height.
    for height in body.getElementsByTagNameNS(W,'trHeight'):attrs(height,hRule='atLeast')
    for table in body.getElementsByTagNameNS(W,'tbl'):
        properties=element(document,table,'tblPr',first=True)
        attrs(element(document,properties,'tblW'),w=5000,type='pct')
        attrs(element(document,properties,'tblLayout'),type='autofit')
        # Scale existing column/cell preferences together; keep merged-cell structure.
        grids=direct(table,'tblGrid')
        cols=direct(grids[0],'gridCol') if grids else []
        total=sum(integer(c,'w',0) for c in cols)
        available=round((WIDTH_MM-2*MARGIN_MM)*TWIPS_PER_MM)
        if total>available:
            ratio=available/total
            for col in cols:attrs(col,w=max(1,round(integer(col,'w',0)*ratio)))
            for row in direct(table,'tr'):
                for cell in direct(row,'tc'):
                    for prop in direct(cell,'tcPr'):
                        for width in direct(prop,'tcW'):
                            if width.getAttributeNS(W,'type')=='dxa':attrs(width,w=max(1,round(integer(width,'w',0)*ratio)))
    # Fit plain inline pictures to the usable width without altering image bytes.
    for inline in body.getElementsByTagNameNS(WP,'inline'):
        extents=inline.getElementsByTagNameNS(WP,'extent')
        pictures=inline.getElementsByTagNameNS(PIC,'pic')
        if len(extents)!=1 or len(pictures)!=1:continue
        extent=extents[0]
        try:cx=int(extent.getAttribute('cx'));cy=int(extent.getAttribute('cy'))
        except ValueError:raise Unsupported('图片尺寸无效，请在原编辑器中重新插入图片') from None
        available=(WIDTH_MM-2*MARGIN_MM)*36000
        if cx>available and cy>0:
            scale=available/cx
            extent.setAttribute('cx',str(available));extent.setAttribute('cy',str(round(cy*scale)))
            for transform in pictures[0].getElementsByTagNameNS(A,'xfrm'):
                for size in transform.getElementsByTagNameNS(A,'ext'):
                    size.setAttribute('cx',str(available));size.setAttribute('cy',str(round(cy*scale)))
    before=[n.text for n in parsed['word/document.xml'].iter() if n.tag in ('{'+W+'}t','{'+W+'}instrText')]
    data=document.toxml(encoding='utf-8')
    from prepare import xml
    after=[n.text for n in xml(data).iter() if n.tag in ('{'+W+'}t','{'+W+'}instrText')]
    if before!=after:raise Unsupported('原文核对失败，未生成副本')
    parts['word/document.xml']=data
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,content in parts.items():archive.writestr(name,content)
    report={'schema_version':1,'status':'needs_editor_review','source_sha256':sha(blob),'mobile_docx_sha256':sha(output.getvalue()),'page_width_mm':WIDTH_MM,'side_margin_mm':MARGIN_MM,'body_font_pt':FONT_PT,'line_spacing':1.5,'section_count':len(sections),'paragraph_count':len(paragraphs),'text_preserved':True,'other_package_parts_unchanged':True,'visual_verified':False,'uploaded':False,'review_items':['在本机编辑器打开 mobile.docx，核对分页、字体、表格、图片和阅读顺序；副本不是原版面无损复刻','继承的标题字号可能变为 18 磅，显式设置的大字号、粗体和颜色保留；按原稿核对标题层级','宽表须在副本中拆成重复表头的小表；不得缩小字体硬塞；浮动图、文本框和公式须逐项查看','页眉页脚、脚注尾注的内容保留，字号及位置须在编辑器检查；图片内小字不能自动识别','确认后在原编辑器导出 mobile.pdf，再交给 pdf-pages.py；不自动启动 Office、下载字体或上传']}
    return output.getvalue(),report


def prepare(input_path,article_dir,confirmed=False):
    if not confirmed:raise Unsupported('请先确认只在副本中改成 110 mm、18 磅的单栏手机版；原稿不会改动')
    source=checked_path(input_path,True);dest=checked_path(article_dir,False)
    if source.suffix.lower()!='.docx':raise Unsupported('请用原编辑器另存真正的 .docx，不要只改后缀')
    if dest.exists() or not dest.parent.is_dir():raise Unsupported('父目录需已存在，输出目录必须全新')
    if source.stat().st_size>MAX_ARCHIVE:raise Unsupported('DOCX 超过 30 MiB，请在副本按章节拆分')
    blob=source.read_bytes();mobile,report=convert(blob)
    checked_path(dest.parent,False);dest.mkdir(exist_ok=False)
    files={'source.docx':blob,'mobile.docx':mobile,'mobile-layout.json':(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8')}
    for name,data in files.items():
        with (dest/name).open('xb') as stream:stream.write(data)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True);parser.add_argument('--article-dir',required=True)
    parser.add_argument('--confirm-mobile-copy',action='store_true')
    args=parser.parse_args()
    try:
        prepare(args.input,args.article_dir,args.confirm_mobile_copy)
        print('已生成独立 mobile.docx：110 mm、左右各 5 mm、正文至少 18 磅、1.5 倍行距。原稿未改，尚未视觉验收。')
        print('下一步：打开副本核对宽表、浮动图、分页，再导出 mobile.pdf。具体步骤见 references/word-fidelity.md。')
        return 0
    except Exception as exc:
        print('手机版副本未完成：'+(str(exc) if isinstance(exc,Unsupported) else type(exc).__name__)+'。未覆盖原稿；失败目录不作为交付。')
        print('仍可按 references/word-fidelity.md 在原编辑器中另存副本，手动设置 11 厘米宽度、18 磅正文后导出。')
        return 2


if __name__=='__main__':sys.exit(main())
