#!/usr/bin/env python3
"""Prepare a bounded DOCX subset locally. Never claims full Word fidelity."""
import argparse
import hashlib
import html
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile
import xml.etree.ElementTree as ET

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL='http://schemas.openxmlformats.org/package/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
WP='http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
PIC='http://schemas.openxmlformats.org/drawingml/2006/picture'
MAX_ARCHIVE=30*1024*1024
MAX_TOTAL=100*1024*1024
MAX_MEMBER=20*1024*1024
MAX_MEMBERS=500

class Unsupported(ValueError):
    """Known boundary; message never contains document text or private paths."""

def q(ns,name):return '{'+ns+'}'+name
def sha(data):return hashlib.sha256(data).hexdigest()
def reject(detail):raise Unsupported(detail+'；请先人工转换为普通段落/内嵌 PNG 或 JPEG，再重试。')

def checked_path(value, must_exist):
    p=Path(value).absolute()
    if '..' in p.parts:raise Unsupported('路径不允许 ..')
    for part in (p,*p.parents):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(),'st_file_attributes',0)&0x400):
            raise Unsupported('路径含符号链接或重解析点')
    if must_exist and not p.is_file():raise Unsupported('输入文件不存在或不是文件')
    return p.resolve()

def member_name(name):
    if not name or '\\' in name or ':' in name or name.startswith('/') or '\x00' in name:
        raise Unsupported('ZIP 成员路径不安全')
    pieces=name.rstrip('/').split('/')
    if any(p in ('','.','..') for p in pieces):raise Unsupported('ZIP 成员路径越界')
    return '/'.join(pieces)

def xml(data):
    # Also catches UTF-16/32 ASCII declaration tokens before the XML parser.
    clean=data.replace(b'\x00',b'').lower()
    if b'<!doctype' in clean or b'<!entity' in clean:
        raise Unsupported('拒绝 DOCTYPE 或实体声明')
    try:return ET.fromstring(data)
    except ET.ParseError:raise Unsupported('XML 无法解析') from None

def package(blob, additional_relationships=(), normalize_internal_targets=False):
    import io
    if len(blob)>MAX_ARCHIVE:raise Unsupported('DOCX 超过 30 MiB')
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            infos=archive.infolist()
            if len(infos)>MAX_MEMBERS:raise Unsupported('ZIP 成员数量超限')
            names=set();total=0;parts={}
            for info in infos:
                name=member_name(info.orig_filename)
                if name!=info.filename.rstrip('/'):raise Unsupported('ZIP 原始路径与规范路径不一致')
                if name.casefold() in names:raise Unsupported('ZIP 成员重复或大小写冲突')
                names.add(name.casefold())
                mode=(info.external_attr>>16)&0xffff
                if stat.S_ISLNK(mode) or info.flag_bits&1:raise Unsupported('ZIP 含链接或加密成员')
                if info.is_dir():continue
                total+=info.file_size
                if info.file_size>MAX_MEMBER or total>MAX_TOTAL or info.file_size>max(1,info.compress_size)*200:
                    raise Unsupported('ZIP 解压大小或压缩比超限')
                if 'vbaproject' in name.lower() or name.lower().endswith(('.bin','.exe','.dll')):
                    raise Unsupported('不支持宏或嵌入二进制对象')
                data=archive.read(info)
                if len(data)!=info.file_size:raise Unsupported('ZIP 成员大小不一致')
                parts[name]=data
    except (zipfile.BadZipFile,NotImplementedError,RuntimeError):
        raise Unsupported('无效或不支持的 DOCX 压缩包') from None
    required={'[Content_Types].xml','_rels/.rels','word/document.xml'}
    if not required.issubset(parts):raise Unsupported('缺少 DOCX 必需结构')
    parsed={name:xml(data) for name,data in parts.items() if name.endswith(('.xml','.rels'))}
    types=parsed['[Content_Types].xml']
    if types.tag!=q(CT,'Types'):raise Unsupported('无效内容类型清单')
    defaults={};overrides={}
    for node in types:
        content=node.get('ContentType','')
        if any(x in content.lower() for x in ('macro','vba','oleobject')):raise Unsupported('拒绝宏或嵌入对象内容类型')
        if node.tag==q(CT,'Default'):defaults[node.get('Extension','').lower()]=content
        elif node.tag==q(CT,'Override'):overrides[node.get('PartName','').lstrip('/')]=content
        else:raise Unsupported('未知内容类型节点')
    if overrides.get('word/document.xml')!='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml':
        raise Unsupported('只支持标准无宏 DOCX 正文')
    rels={}
    allowed={'officeDocument','core-properties','extended-properties','custom-properties','styles','settings','fontTable','theme','webSettings','image','numbering'}
    allowed.update(additional_relationships)
    for name,tree in parsed.items():
        if not name.endswith('.rels'):continue
        if tree.tag!=q(REL,'Relationships'):raise Unsupported('无效关系清单')
        source='' if name=='_rels/.rels' else name.split('/_rels/')[0]+'/'
        ids={}
        for node in tree:
            if node.tag!=q(REL,'Relationship'):raise Unsupported('未知关系节点')
            if node.get('TargetMode','Internal')!='Internal':raise Unsupported('拒绝外部关系')
            relationship_type=node.get('Type','')
            effect_style=('stylesWithEffects' in additional_relationships and relationship_type=='http://schemas.microsoft.com/office/2007/relationships/stylesWithEffects')
            if not relationship_type.startswith((R+'/',REL+'/metadata/')) and not effect_style:reject('不支持的关系命名空间')
            kind=relationship_type.rsplit('/',1)[-1]
            if kind not in allowed:reject('不支持的文档关系')
            target=node.get('Target','')
            if not target or target.startswith('/') or ':' in target or '\\' in target or '%' in target or '?' in target or '#' in target or (not normalize_internal_targets and '..' in target.split('/')):
                raise Unsupported('关系目标不安全')
            if normalize_internal_targets:
                import posixpath
                target=member_name(posixpath.normpath(source+target))
            else:target=member_name(source+target)
            if target not in parts:raise Unsupported('关系目标不存在')
            rid=node.get('Id','')
            if not rid or rid in ids:raise Unsupported('关系 ID 缺失或重复')
            ids[rid]=(kind,target)
        rels[name]=ids
    if not any(kind=='officeDocument' and target=='word/document.xml' for kind,target in rels['_rels/.rels'].values()):
        raise Unsupported('包入口未指向标准正文')
    def content_type(name):return overrides.get(name,defaults.get(PurePosixPath(name).suffix.lstrip('.').lower(),''))
    return parts,parsed,rels.get('word/_rels/document.xml.rels',{}),content_type

def bool_property(node):
    value=node.get(q(W,'val'),'true')
    if value in ('true','1','on'):return True
    if value in ('false','0','off'):return False
    reject('不支持的文本属性值')

class Converter:
    def __init__(self,parts,relationships,content_type):
        self.parts=parts;self.rels=relationships;self.content_type=content_type
        self.images=[];self.media={};self.image_names={}
    def image(self,drawing):
        allowed={q(W,'drawing'),*[q(WP,n) for n in ('inline','extent','effectExtent','docPr','cNvGraphicFramePr')],*[q(A,n) for n in ('graphic','graphicData','graphicFrameLocks','blip','stretch','fillRect','xfrm','off','ext','prstGeom','avLst')],*[q(PIC,n) for n in ('pic','nvPicPr','cNvPr','cNvPicPr','blipFill','spPr')]}
        for node in drawing.iter():
            if node.tag not in allowed:reject('不支持的图片结构（浮动、裁剪或特效）')
            if node.tag==q(A,'xfrm') and any(k in node.attrib for k in ('rot','flipH','flipV')):reject('不支持图片旋转或翻转')
            if node.tag==q(A,'prstGeom') and node.get('prst')!='rect':reject('不支持图片形状变换')
            if node.tag==q(A,'graphicData') and node.get('uri')!=PIC:reject('不支持的图形类型')
        inline=drawing.findall(q(WP,'inline'));blips=list(drawing.iter(q(A,'blip')))
        if len(inline)!=1 or len(blips)!=1 or len(list(drawing.iter(q(PIC,'pic'))))!=1:reject('只支持内嵌位图')
        rid=blips[0].get(q(R,'embed'))
        if blips[0].get(q(R,'link')) or rid not in self.rels or self.rels[rid][0]!='image':reject('图片引用无效')
        source=self.rels[rid][1];data=self.parts[source]
        suffix=PurePosixPath(source).suffix.lower()
        actual='image/png' if data.startswith(b'\x89PNG\r\n\x1a\n') and len(data)>=33 and data[12:16]==b'IHDR' and data[-8:-4]==b'IEND' else 'image/jpeg' if data.startswith(b'\xff\xd8\xff') and data.endswith(b'\xff\xd9') else None
        if not actual or self.content_type(source)!=actual or suffix not in ({'.png'} if actual=='image/png' else {'.jpg','.jpeg'}):
            reject('图片实际类型、扩展名或内容类型不一致')
        if source not in self.image_names:
            file='media/image'+str(len(self.images)+1).zfill(4)+('.png' if actual=='image/png' else '.jpg')
            self.image_names[source]=file;self.media[file]=data
            self.images.append({'file':file,'sha256':sha(data),'content_type':actual})
        file=self.image_names[source]
        props=drawing.find('.//'+q(WP,'docPr'))
        alt=(props.get('descr') or props.get('title') or '') if props is not None else ''
        return '<img src="'+file+'" data-source-image="'+file+'" alt="'+html.escape(alt,quote=True)+'">',file
    def run(self,node):
        emphasis=[];fragments=[];text=[];images=[]
        properties=node.findall(q(W,'rPr'))
        if len(properties)>1:reject('重复文本属性')
        if properties:
            for prop in properties[0]:
                if len(prop):reject('文本格式含未知嵌套结构')
                if prop.tag==q(W,'b'):
                    if bool_property(prop):emphasis.append('strong')
                elif prop.tag==q(W,'i'):
                    if bool_property(prop):emphasis.append('em')
                elif prop.tag==q(W,'u'):
                    val=prop.get(q(W,'val'),'single')
                    if val=='single':emphasis.append('u')
                    elif val not in ('none','0','false'):reject('不支持复杂下划线')
                else:reject('不支持的文本格式')
        for child in node:
            if child.tag==q(W,'rPr'):continue
            if child.tag==q(W,'t'):
                if len(child):reject('文字节点包含未知子元素')
                value=child.text or '';text.append(value);fragments.append(html.escape(value,quote=True))
            elif child.tag==q(W,'tab'):text.append('\t');fragments.append('&#9;')
            elif child.tag==q(W,'br'):
                if child.get(q(W,'type'),'textWrapping')!='textWrapping':reject('不支持分页或分栏符')
                text.append('\n');fragments.append('<br>')
            elif child.tag==q(W,'drawing'):
                markup,file=self.image(child);fragments.append(markup);images.append(file)
            else:reject('不支持的正文运行元素')
        markup=''.join(fragments)
        for tag in reversed(emphasis):markup='<'+tag+'>'+markup+'</'+tag+'>'
        return markup,''.join(text),images
    def paragraph(self,node,index):
        tag='p';align=None;properties=node.findall(q(W,'pPr'))
        if len(properties)>1:reject('重复段落属性')
        if properties:
            for prop in properties[0]:
                if len(prop):reject('段落属性含未知嵌套结构')
                if prop.tag==q(W,'pStyle'):
                    style=prop.get(q(W,'val'),'')
                    match=re.fullmatch(r'Heading([1-6])',style,re.I)
                    if match:tag='h'+match[1]
                    elif style not in ('Normal','BodyText'):reject('不支持自定义段落样式')
                elif prop.tag==q(W,'jc'):
                    align={'left':'left','right':'right','center':'center','both':'justify'}.get(prop.get(q(W,'val')))
                    if not align:reject('不支持的对齐方式')
                else:reject('不支持的段落格式（含列表）')
        fragments=[];texts=[];images=[]
        for child in node:
            if child.tag==q(W,'pPr'):continue
            if child.tag!=q(W,'r'):reject('不支持表格、域、链接、修订或其他正文结构')
            frag,text,imgs=self.run(child);fragments.append(frag);texts.append(text);images.extend(imgs)
        pid='p'+str(index).zfill(4)
        style='white-space:pre-wrap'+(';text-align:'+align if align else '')
        return '<'+tag+' data-pid="'+pid+'" style="'+style+'">'+''.join(fragments)+'</'+tag+'>',{'pid':pid,'tag':tag,'text':''.join(texts),'images':images}

def convert(blob):
    parts,parsed,rels,ctype=package(blob)
    document=parsed['word/document.xml']
    if document.tag!=q(W,'document') or len(document)!=1 or document[0].tag!=q(W,'body'):reject('不支持的文档根结构')
    for node in document.iter():
        if (node.tag!=q(W,'t') and (node.text or '').strip()) or (node.tail or '').strip():
            reject('正文含标准文字节点之外的游离文本')
    body=document[0];converter=Converter(parts,rels,ctype);chunks=[];paragraphs=[]
    for i,node in enumerate(body):
        if node.tag==q(W,'sectPr'):
            allowed={q(W,n) for n in ('pgSz','pgMar','cols','docGrid','type')}
            if i!=len(body)-1 or any(child.tag not in allowed or len(child) for child in node):reject('不支持页眉页脚或复杂节属性')
            for columns in node.findall(q(W,'cols')):
                if columns.get(q(W,'num'),'1')!='1' or columns.get(q(W,'equalWidth'),'true') not in ('true','1','on'):
                    reject('不支持多栏或自定义分栏版式，请选择 PDF 整页图片后备方案')
            continue
        if node.tag!=q(W,'p'):reject('不支持表格或其他正文元素')
        markup,record=converter.paragraph(node,len(paragraphs)+1);chunks.append(markup);paragraphs.append(record)
    if not paragraphs:reject('没有可处理段落')
    check={'schema_version':1,'source_sha256':sha(blob),'parser':'bounded-ooxml','paragraph_count':len(paragraphs),'images':converter.images,'support':{'paragraphs':True,'heading_levels':[1,2,3,4,5,6],'inline_png_jpeg':True,'preserve_image_bytes':True,'preserve_empty_paragraphs':True},'limitations':['Not full Word fidelity','Page layout, fonts and style inheritance are not reproduced','Only explicitly supported direct formatting is accepted']}
    markup='<div id="wenyan">\n'+'\n'.join(chunks)+'\n</div>\n'
    check['source_html_sha256']=sha(markup.encode('utf-8'))
    return markup,paragraphs,check,converter.media

def prepare(input_path,article_dir):
    source=checked_path(input_path,True);dest=checked_path(article_dir,False)
    if source.suffix.lower()!='.docx':raise Unsupported('输入必须为 .docx')
    if dest.exists():raise Unsupported('输出目录必须全新，不覆盖已有目录')
    if not dest.parent.is_dir():raise Unsupported('请先建立输出目录的父目录')
    if source.stat().st_size>MAX_ARCHIVE:raise Unsupported('DOCX 超过 30 MiB')
    blob=source.read_bytes();markup,paragraphs,check,media=convert(blob)
    # All validation precedes first write; exclusive mkdir prevents overwrite races.
    checked_path(dest.parent,False);dest.mkdir(exist_ok=False)
    files={'source.docx':blob,'source.html':markup.encode('utf-8'),'source-paragraphs.json':json.dumps(paragraphs,ensure_ascii=False,indent=2).encode('utf-8'),'source-check.json':json.dumps(check,ensure_ascii=False,indent=2).encode('utf-8'),**media}
    for name,data in files.items():
        path=dest/name;path.parent.mkdir(exist_ok=True)
        with path.open('xb') as f:f.write(data)
    return check

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True);parser.add_argument('--article-dir',required=True)
    args=parser.parse_args()
    try:
        check=prepare(args.input,args.article_dir)
        print('已建立本地原文与解析产物：'+str(check['paragraph_count'])+' 段、'+str(len(check['images']))+' 张图片；不代表 Word 全格式保真。')
        return 0
    except (Unsupported,OSError,ValueError) as exc:
        print('Word 建档停止：'+(str(exc) if isinstance(exc,Unsupported) else type(exc).__name__)+'。输入原文未修改。')
        print('保真后备方案见 references/word-fidelity.md：可在本机 Word 导出 PDF，由你确认后整页转图；不会自动改为图片。')
        return 2

if __name__=='__main__':sys.exit(main())
