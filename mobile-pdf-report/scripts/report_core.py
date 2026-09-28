"""Pure conversion, resource policy and output validation helpers."""
import html
import os
from html.parser import HTMLParser
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit
from urllib.request import url2pathname
import warnings

BASE_CSS = """
@page { size: WIDTH_MMmm HEIGHT_MMmm; margin: 8mm 7mm 9mm 7mm; }
* { box-sizing: border-box; }
html, body { margin:0; padding:0; }
body {
  font-family: "Noto Sans CJK SC", "WenQuanYi Zen Hei", sans-serif;
  color:#111827;
  font-size: 10.3pt;
  line-height: 1.62;
  text-align: justify;
  text-align-last: start;
}
h1, h2, h3 { font-family: "Noto Serif CJK SC", "Noto Sans CJK SC", serif; color:#0f172a; line-height:1.32; margin:0; }
h1 { font-size: 18pt; margin-top: 0; margin-bottom: 6mm; letter-spacing:.02em; }
h2 { font-size: 13.8pt; margin-top: 7mm; margin-bottom: 2.5mm; padding-bottom:1.2mm; border-bottom: .4mm solid #e5e7eb; }
h3 { font-size: 11.2pt; margin-top: 4mm; margin-bottom: 1.5mm; }
p { margin: 0 0 2.4mm 0; }
ul, ol { margin: 1.5mm 0 3mm 0; padding-left: 5.2mm; }
li { margin: .8mm 0; }
strong { font-weight: 700; }
.cover { min-height: 150mm; display:flex; flex-direction:column; justify-content:center; break-after: page; }
.kicker { font-size: 8.6pt; color:#64748b; letter-spacing:.12em; margin-bottom:3mm; }
.subtitle { font-size: 11pt; color:#334155; line-height:1.55; margin-bottom:8mm; }
.meta { border-top: .3mm solid #cbd5e1; padding-top:4mm; color:#475569; font-size:9.2pt; }
.callout { border-left: 1.2mm solid #334155; background:#f8fafc; padding:3mm; margin:3mm 0; break-inside: avoid; }
.warning { border-left-color:#b91c1c; background:#fff7f7; }
.good { border-left-color:#047857; background:#f0fdf4; }
.small { font-size:9pt; color:#475569; }
table { width:100%; border-collapse:collapse; margin:3mm 0; font-size:8.4pt; break-inside:auto; }
th, td { border:.25mm solid #d1d5db; padding:1.4mm 1.2mm; vertical-align:top; overflow-wrap:anywhere; }
th { background:#f1f5f9; font-weight:700; }
tr { break-inside: avoid; }
blockquote { border-left: 1.2mm solid #334155; background:#f8fafc; margin:3mm 0; padding:2.5mm 3mm; }
pre, code { font-family: "Noto Sans Mono CJK SC", monospace; overflow-wrap:anywhere; white-space:pre-wrap; }
hr { border:none; border-top:.3mm solid #e5e7eb; margin:5mm 0; }
"""


def fallback_markdown_to_html(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    in_ul = False
    in_ol = False
    in_code = False
    fence_marker, fence_length = None, 0
    code_buf: list[str] = []

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>"); in_ul = False
        if in_ol:
            out.append("</ol>"); in_ol = False

    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        return s

    for line in lines:
        raw = line.rstrip()
        fence = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if in_code:
            if (fence and fence.group(1)[0] == fence_marker
                    and len(fence.group(1)) >= fence_length
                    and not fence.group(2).strip()):
                out.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
                code_buf = []
                in_code = False
            else:
                code_buf.append(line)
            continue
        if fence and not (fence.group(1)[0] == "`" and "`" in fence.group(2)):
            close_lists()
            in_code = True
            fence_marker, fence_length = fence.group(1)[0], len(fence.group(1))
            continue
        if not raw.strip():
            close_lists(); continue
        m = re.match(r"^(#{1,3})\s+(.+)$", raw)
        if m:
            close_lists()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            continue
        if re.match(r"^[-*]\s+", raw):
            if not in_ul:
                close_lists(); out.append("<ul>"); in_ul = True
            out.append("<li>" + inline(re.sub(r"^[-*]\s+", "", raw)) + "</li>")
            continue
        if re.match(r"^\d+[.)]\s+", raw):
            if not in_ol:
                close_lists(); out.append("<ol>"); in_ol = True
            out.append("<li>" + inline(re.sub(r"^\d+[.)]\s+", "", raw)) + "</li>")
            continue
        close_lists()
        out.append("<p>" + inline(raw) + "</p>")
    close_lists()
    if in_code:
        out.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
        warnings.warn("Unclosed code fence completed; content preserved", UserWarning)
    return "\n".join(out)


def markdown_to_html(text: str) -> str:
    try:
        import markdown  # type: ignore
        return markdown.markdown(text, extensions=["tables", "fenced_code"])
    except ImportError:
        return fallback_markdown_to_html(text)


def wrap_html(title: str, body_html: str, width_mm: int, height_mm: int) -> str:
    css = BASE_CSS.replace("WIDTH_MM", str(width_mm)).replace("HEIGHT_MM", str(height_mm))
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\">
<title>{html.escape(title)}</title>
<style>{css}</style>
</head>
<body>
{body_html}
</body>
</html>
"""



class ReportError(ValueError):
    pass


class InputCheck(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.suppressed = 0
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        values = {key: (value or "") for key, value in attrs}
        if tag in {"base", "object", "embed", "iframe", "script", "svg", "form"}:
            raise ReportError("Unsupported active, embedded or vector content")
        if "attachment" in values.get("rel", "").lower().split():
            raise ReportError("PDF attachments are forbidden")
        if tag == "a" and values.get("href"):
            url = values["href"].strip()
            if not url.startswith("#") and urlsplit(url).scheme.lower() not in {"http", "https"}:
                raise ReportError("Only fragment and HTTP(S) document hyperlinks are supported")
        if tag in {"style", "head", "title"}:
            self.suppressed += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in {"style", "head", "title"}:
            self.suppressed = max(0, self.suppressed - 1)

    def handle_data(self, data):
        if not self.suppressed and data.strip():
            self.text_parts.append(data)


def check_html(text):
    parser = InputCheck()
    parser.feed(text)
    parser.close()
    return parser.text_parts


def local_path(value):
    raw = os.fspath(value)
    if raw.replace("\\", "/").startswith("//") or "\0" in raw or re.match(r"^[A-Za-z]+://", raw):
        raise ReportError("Network and device paths are forbidden")
    if ".." in Path(raw).parts:
        raise ReportError("Parent traversal in local paths is forbidden")
    path = Path(raw).absolute()  # Lexical expansion only; no filesystem access yet.
    if str(path).replace("\\", "/").startswith("//"):
        raise ReportError("Network paths are forbidden")
    if os.name == "nt":
        import ctypes
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(str(path.anchor))
        if drive_type not in {2, 3, 5, 6}:
            raise ReportError("Only local filesystem drives are supported")
    # Inspect from the local drive/root downward: checking a leaf first could
    # already follow an ancestor junction to a network share.
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            break
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ReportError("Linked paths or ancestors are forbidden")
    return path


class ResourcePolicy:
    """No default fetcher, HTTP client or fallback. Only explicit assets are read."""
    TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".webp": "image/webp", ".css": "text/css"}

    def __init__(self, assets_dir=None):
        self.root = None
        if assets_dir:
            raw_root = local_path(assets_dir)
            self.root = raw_root.resolve(strict=True)
        if self.root is not None and (not self.root.is_dir() or str(self.root).startswith(("\\\\", "//"))):
            raise ReportError("Assets must be a local directory")
        self.violations = []
        self.total = 0
        self.cache = {}

    def load(self, url):
        try:
            return self._load(url)
        except (OSError, ValueError, UnicodeError):
            self.violations.append("Resource refused")  # Do not log private URLs or paths.
            raise ReportError("Resource refused by policy") from None

    def _load(self, url):
        parsed = urlsplit(url)
        if self.root is None or parsed.scheme != "file" or parsed.netloc or parsed.query or parsed.fragment:
            raise ReportError("Only explicit local assets are supported")
        decoded = url2pathname(parsed.path)
        if decoded.startswith(("\\\\", "//")) or "\x00" in decoded:
            raise ReportError("UNC and device paths are forbidden")
        path = Path(decoded)
        relative = path.relative_to(self.root)  # No drive changes or unrelated root.
        if ".." in relative.parts or any(":" in part for part in relative.parts):
            raise ReportError("Traversal and alternate streams are forbidden")
        current = self.root
        for part in relative.parts:
            current = current / part
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ReportError("Linked resources are forbidden")
        resolved = path.resolve(strict=True)
        resolved.relative_to(self.root)
        if not resolved.is_file() or resolved.suffix.lower() not in self.TYPES:
            raise ReportError("Unsupported resource type")
        if resolved in self.cache:
            return self.cache[resolved]
        with resolved.open("rb") as f:
            data = f.read(5 * 1024 * 1024 + 1)
        self.total += len(data)
        if len(data) > 5 * 1024 * 1024 or self.total > 20 * 1024 * 1024:
            raise ReportError("Asset size budget exceeded")
        ext = resolved.suffix.lower()
        valid = (ext == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n")
                 or ext in {".jpg", ".jpeg"} and data.startswith(b"\xff\xd8\xff")
                 or ext == ".webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP")
        if ext == ".css":
            data.decode("utf-8-sig")
        elif not valid:
            raise ReportError("Image content does not match allowed format")
        result = (data, self.TYPES[ext])
        self.cache[resolved] = result
        return result


def page_css(width, height):
    if type(width) is not int or type(height) is not int or not 100 <= width <= 110 or not 100 <= height <= 500:
        raise ReportError("Width must be 100..110 mm; height must be 100..500 mm")
    return "@page { size: %dmm %dmm !important; }" % (width, height)


def prepare_html(text, suffix, title, width, height):
    page_css(width, height)
    if suffix.lower() in {".html", ".htm"}:
        document = text if re.search(r"<html\b", text, re.I) else wrap_html(title, text, width, height)
    else:
        document = wrap_html(title, markdown_to_html(text), width, height)
    expected = check_html(document)
    if not expected:
        raise ReportError("Report body must contain text")
    return document, expected


def output_paths(source, output, overwrite=False):
    source = local_path(source).resolve(strict=True)
    raw_output = local_path(output)
    if raw_output.is_symlink():
        raise ReportError("Output must not be a symlink")
    output = raw_output.resolve()
    if source == output or output.suffix.lower() != ".pdf":
        raise ReportError("Output must be a distinct PDF file")
    if output.exists() and (source.samefile(output) or not overwrite):
        raise ReportError("Existing output requires --overwrite and must not be the input")
    return source, output


def validate_pdf(path, width, height, expected):
    from pypdf import PdfReader
    reader = PdfReader(path)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 500:
        raise ReportError("Invalid PDF encryption or page count")
    if reader.attachments or reader.trailer["/Root"].get("/AF"):
        raise ReportError("PDF contains attachments")
    texts = []
    for page in reader.pages:
        if abs(float(page.mediabox.width) * 25.4 / 72 - width) > 0.25 or abs(float(page.mediabox.height) * 25.4 / 72 - height) > 0.25:
            raise ReportError("PDF page dimensions differ from requested dimensions")
        if page.get("/AF"):
            raise ReportError("Associated files are forbidden")
        for ref in page.get("/Annots", []):
            annot = ref.get_object()
            action = annot.get("/A", {})
            if hasattr(action, "get_object"):
                action = action.get_object()
            if annot.get("/Subtype") == "/FileAttachment" or action.get("/S") in {"/Launch", "/GoToR"}:
                raise ReportError("File attachment or launch action in PDF")
        texts.append(page.extract_text() or "")
    flattened = re.sub(r"\s+", "", "".join(texts))
    if not flattened or any(re.sub(r"\s+", "", chunk) not in flattened for chunk in expected):
        raise ReportError("PDF body text missing or not extractable")
    return {"pages": len(reader.pages), "text_verified": True, "attachments": 0,
            "width_mm": width, "height_mm": height}
