"""Bounded local files and explicit, fixed-host WeChat access. No credential discovery."""
import contextlib
import hashlib
import html
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import sys
from html.parser import HTMLParser
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

class Blocked(ValueError):
    pass

def ident(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', value) or value.upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
        raise Blocked('名称仅允许英文字母、数字、下划线和连字符')
    return value

def root(path):
    p = Path(path).absolute()
    for q in (p, *p.parents):
        if q.is_symlink() or (q.exists() and getattr(q.lstat(), 'st_file_attributes', 0) & 0x400):
            raise Blocked('不支持链接或重解析目录')
    if not p.is_dir():
        raise Blocked('文章目录不存在')
    return p.resolve()

def local(adir, relative, exists=True):
    adir = root(adir)
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts or ':' in str(relative):
        raise Blocked('只允许文章目录内相对路径')
    p = adir / rel
    for q in (p, *p.parents):
        if q == adir.parent:
            break
        if q.is_symlink() or (q.exists() and getattr(q.lstat(), 'st_file_attributes', 0) & 0x400):
            raise Blocked('不支持链接或重解析文件')
    if not p.resolve().is_relative_to(adir):
        raise Blocked('路径越出文章目录')
    if exists and not p.is_file():
        raise Blocked('缺少文章文件：' + str(relative))
    return p

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write_json(adir, rel, data):
    p = local(adir, rel, False)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('x', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(p)
    finally:
        if tmp.exists(): tmp.unlink()

@contextlib.contextmanager
def lock(adir):
    p = local(adir, '.wechat-operation.lock', False)
    try:
        f = p.open('x', encoding='utf-8')
    except FileExistsError:
        raise Blocked('此目录已有操作锁；先核对上次操作结果，不自动重试')
    try:
        with f: f.write(str(os.getpid()))
        yield
    finally:
        p.unlink()

def approved(adir, paths, theme=None):
    state = read_json(local(adir, 'workflow-state.json'))
    required = ('topic_confirmed','outline_confirmed','article_finalized','humanizer_passed','quality_gate_passed','cover_confirmed','theme_confirmed','upload_confirmed')
    if any(state.get(k) is not True for k in required) or state.get('delivery_mode') != 'wechat_draft':
        raise Blocked('须先由用户确认当前文章、封面、排版及草稿上传，并记录 workflow-state.json')
    if theme and state.get('selected_theme') != theme:
        raise Blocked('主题与用户确认记录不一致')
    hashes = state.get('confirmed_artifacts', {})
    for rel in paths:
        if hashes.get(rel) != sha(local(adir, rel)):
            raise Blocked('文件已变化或尚未确认：' + rel)
    return state

class SafeHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []
    def handle_starttag(self, tag, attrs):
        if tag not in {'p','section','div','span','strong','b','em','i','u','s','del','br','hr','h1','h2','h3','h4','h5','h6','ul','ol','li','blockquote','pre','code','table','thead','tbody','tr','th','td','img','a'}:
            raise Blocked('HTML 含不支持的标签；仅接受正文片段')
        if len({name for name, _ in attrs}) != len(attrs):
            raise Blocked('不支持重复 HTML 属性')
        for name, value in attrs:
            value = value or ''
            if name.startswith('on') or name in {'srcset','background','poster','action','formaction','data-src'}:
                raise Blocked('HTML 含活动或隐式资源属性')
            if name == 'style' and (re.search(r'url\s*\(|@import|expression\s*\(',value,re.I) or '\\' in value):
                raise Blocked('CSS 不得包含外部资源或表达式')
            if name == 'href' and value and not (value.startswith('https://') or value.startswith('#')):
                raise Blocked('链接只支持 HTTPS 或文内锚点')
            if name == 'src' and tag != 'img':
                raise Blocked('不支持隐式资源')
        if tag == 'img': self.images.append(dict(attrs).get('src',''))

def check_html(adir, markup):
    p = SafeHTML(); p.feed(markup); p.close()
    if p.images != ['cover.png']:
        raise Blocked('当前自动上传仅支持一张本地 cover.png；远程图片、多图和其他资源均不上传')
    if len(re.findall(r'<img\b[^>]*\ssrc\s*=\s*([\"\'])cover\.png\1', markup, re.I)) != 1:
        raise Blocked('图片 src 必须以单或双引号写成 cover.png，不支持实体或无引号写法')
    local(adir, 'cover.png')
    from draft_verify import Document
    from deliverable_scan import scan_text
    if not Document(markup).visible_text() or scan_text(markup):
        raise Blocked('正文为空或存在未渲染 Markdown')
    return markup

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Blocked('拒绝重定向')

def request(url, body=None, headers=None):
    if urllib.parse.urlsplit(url).hostname != 'api.weixin.qq.com':
        raise Blocked('只允许微信官方 API')
    if any(value for key, value in urllib.request.getproxies().items() if key.lower() != 'no'):
        raise Blocked('检测到代理配置；请核对执行主机网络和微信 IP 白名单。不会自动绕过或更改代理')
    req = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        # Proxy presence is blocked above; never silently bypass a configured proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(req, timeout=30) as response:
            data = json.load(response)
    except Exception:
        raise Blocked('微信请求失败，结果可能未知；不回显 URL、凭据或响应正文') from None
    if not isinstance(data, dict):
        raise Blocked('微信 API 未返回对象')
    code=data.get('errcode',0)
    if code:
        category={40164:'执行主机 IP 不在白名单',40013:'AppID 无效',40125:'AppSecret 无效',40001:'凭据或令牌失效',42001:'令牌过期',48001:'接口权限不足'}.get(code,'API 未成功')
        safe_code=str(code) if type(code) is int else 'unknown'
        raise Blocked('微信错误 '+safe_code+'：'+category+'；不回显响应正文')
    return data

def token():
    appid = os.environ.get('WECHAT_APP_ID')
    secret = os.environ.get('WECHAT_APP_SECRET')
    if not appid or not secret:
        raise Blocked('当前进程缺少 WECHAT_APP_ID / WECHAT_APP_SECRET；不会读取其他应用配置')
    query = urllib.parse.urlencode({'grant_type':'client_credential','appid':appid,'secret':secret})
    data = request('https://api.weixin.qq.com/cgi-bin/token?' + query)
    if not data.get('access_token'): raise Blocked('微信未返回访问令牌')
    return data['access_token']

def api(endpoint, access_token, data):
    if endpoint not in {'draft/get','draft/add','draft/update'}: raise Blocked('不支持的 API')
    return request('https://api.weixin.qq.com/cgi-bin/' + endpoint + '?access_token=' + urllib.parse.quote(access_token, safe=''), json.dumps(data,ensure_ascii=False).encode('utf-8'), {'Content-Type':'application/json'})

def upload_cover(adir, access_token, material=False):
    cover = local(adir, 'cover.png')
    if cover.stat().st_size > 10 * 1024 * 1024:
        raise Blocked('封面超过 10 MiB，请先压缩并重新确认')
    from PIL import Image
    with Image.open(cover) as im:
        if im.format != 'PNG' or abs(im.width/im.height-2.35) >= .02: raise Blocked('封面须为约 2.35:1 的 PNG')
        im.verify()
    boundary = 'WechatSkill' + uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="media"; filename="cover.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + cover.read_bytes() + f'\r\n--{boundary}--\r\n'.encode())
    endpoint = 'material/add_material?type=image&' if material else 'media/uploadimg?'
    return request('https://api.weixin.qq.com/cgi-bin/' + endpoint + 'access_token=' + urllib.parse.quote(access_token,safe=''), body, {'Content-Type':'multipart/form-data; boundary='+boundary})

def prepare(adir, markup, access_token):
    image = upload_cover(adir, access_token).get('url','')
    from draft_verify import wechat_image
    if not wechat_image(image): raise Blocked('微信图片地址无效')
    thumb = upload_cover(adir, access_token, True).get('media_id')
    if not thumb: raise Blocked('微信未返回封面素材 ID')
    markup, changed = re.subn(r'(<img\b[^>]*\ssrc\s*=\s*)([\"\'])cover\.png\2',lambda m:m[1]+'"'+html.escape(image,quote=True)+'"',markup,flags=re.I)
    if changed != 1: raise Blocked('图片地址替换失败；不会写入草稿')
    return markup, thumb

def cli_error(func):
    try:
        return func()
    except Exception as exc:
        print('操作已停止：' + (str(exc) if isinstance(exc, Blocked) else type(exc).__name__) + '。未确认成功时请勿重复上传。')
        return 2
