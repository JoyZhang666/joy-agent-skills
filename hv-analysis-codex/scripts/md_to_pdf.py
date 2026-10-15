"""Restricted local Markdown to PDF; derived from KKKKhazix hv-analysis.

SPDX-License-Identifier: MIT
Copyright (c) 2026 数字生命卡兹克
Copyright (c) 2026 JoyZhang666
"""
import argparse
import base64
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit

# A4 layout, cover and palette adapted from the upstream MIT converter.
CSS = """@page {size:A4;margin:25mm 20mm 20mm;
 @bottom-center {content:counter(page);font-size:8pt;color:#5d6d7e}}
body {font-family:'Microsoft YaHei','SimSun',sans-serif;font-size:10.5pt;
 line-height:1.75;color:#2c3e50;overflow-wrap:anywhere}
.cover {break-after:page;text-align:center;padding-top:35%}
h1 {font-size:24pt;color:#1a5276} h2 {font-size:16pt;color:#1e8449}
h3 {font-size:12pt;color:#2e86c1} h4 {font-size:11pt;color:#5b2c6f}
h1,h2,h3,h4 {break-after:avoid} tr {break-inside:avoid}
table {width:100%;border-collapse:collapse;font-size:9pt;table-layout:fixed}
th {background:#1a5276;color:white} td,th {padding:5px;border:1px solid #bdc3c7}
tr:nth-child(even) {background:#f8f9fa} img {max-width:100%;height:auto}
blockquote {border-left:3px solid #1a5276;padding-left:12px;color:#5d6d7e}
pre {white-space:pre-wrap} a {color:#2e86c1}
"""
ALLOWED = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "hr", "br", "blockquote",
           "em", "strong", "ul", "ol", "li", "pre", "code", "table", "thead", "tbody",
           "tr", "td", "th", "a", "img", "del"}


def reject_links(path):
    for entry in (path, *path.parents):
        if entry.is_symlink() or (entry.exists() and getattr(entry.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Links and reparse points are not supported")


def prepare_assets(source, assets):
    allowed, total = {}, 0
    for asset in assets:
        raw = Path(asset).absolute()
        reject_links(raw)
        path = raw.resolve()
        if not path.is_relative_to(source.parent):
            raise ValueError("Assets must be inside the Markdown directory")
        size = path.stat().st_size
        total += size
        if size > 5 * 1024 * 1024 or total > 10 * 1024 * 1024:
            raise ValueError("Asset size limit exceeded")
        data = path.read_bytes()
        if path.suffix.lower() == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif path.suffix.lower() in (".jpg", ".jpeg") and data.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif path.suffix.lower() == ".webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            mime = "image/webp"
        else:
            raise ValueError("Only PNG, JPEG and WebP assets are supported")
        allowed[path] = "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")
    return allowed


class RestrictedHTML(HTMLParser):
    def __init__(self, source, assets):
        super().__init__(convert_charrefs=True)
        self.source, self.assets, self.output = source, assets, []

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED:
            raise ValueError("Unsupported HTML element; use restricted Markdown")
        attributes = dict(attrs)
        if any(k.lower().startswith("on") for k, _ in attrs):
            raise ValueError("Active HTML attributes are not supported")
        cleaned = []
        if tag == "a":
            href = attributes.get("href", "")
            parsed = urlsplit(href)
            if href.startswith("#") or parsed.scheme.lower() in ("http", "https"):
                cleaned.append(("href", href))
            elif parsed.scheme or parsed.netloc or "\\" in href:
                raise ValueError("Unsupported hyperlink scheme")
            # Keep relative document-link text without file navigation or reading.
        if tag == "img":
            src = attributes.get("src", "")
            parsed = urlsplit(src)
            if parsed.scheme or parsed.netloc or not src or "\\" in src:
                raise ValueError("Only explicitly allowed local images are supported")
            path = (self.source.parent / unquote(parsed.path)).resolve()
            if path not in self.assets:
                raise ValueError("Image was not included in --asset")
            cleaned.extend([("src", self.assets[path]), ("alt", attributes.get("alt", ""))])
        self.output.append("<" + tag + "".join(f' {k}="{escape(v, quote=True)}"' for k, v in cleaned) + ">")

    def handle_endtag(self, tag):
        if tag not in ALLOWED:
            raise ValueError("Unsupported HTML element")
        self.output.append("</" + tag + ">")

    def handle_data(self, data):
        self.output.append(escape(data))

    def handle_decl(self, decl):
        raise ValueError("Raw HTML declarations are not supported")


def build_html(source, title, author="", assets=()):
    source = Path(source).absolute()
    reject_links(source)
    source = source.resolve()
    if source.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Markdown exceeds 2 MiB limit")
    raw = source.read_text(encoding="utf-8-sig")
    # Raw HTML is outside the supported input contract, even if it appears harmless.
    if __import__("re").search(r"</?[A-Za-z][^>]*>|<!|<\?", raw):
        raise ValueError("Raw HTML is not supported")
    import markdown
    parser = RestrictedHTML(source, prepare_assets(source, assets))
    parser.feed(markdown.markdown(raw, extensions=["tables", "fenced_code"], output_format="html5"))
    parser.close()
    csp = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'none'; connect-src 'none'"
    return (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}">'
            f'<title>{escape(title)}</title><style>{CSS}</style></head><body>'
            f'<section class="cover"><h1>{escape(title)}</h1><p>横纵研究与商业尽调</p>'
            f'<p>{escape(author)}</p></section>' + "".join(parser.output) + "</body></html>")


def render_pdf(source, output, title, author="", assets=(), browser_path=None):
    source, output = Path(source).absolute(), Path(output).absolute()
    reject_links(output.parent)
    output = output.resolve()
    html_path = output.with_suffix(".html")
    if output.suffix.lower() != ".pdf" or output == source.resolve() or html_path == source.resolve():
        raise ValueError("Choose a distinct .pdf output path")
    if output.exists() or html_path.exists():
        raise FileExistsError("Output exists; choose a new filename")
    document = build_html(source, title, author, assets)
    output.parent.mkdir(parents=True, exist_ok=True)
    with html_path.open("x", encoding="utf-8") as handle:
        handle.write(document)
    from playwright.sync_api import Error as BrowserError, sync_playwright
    blocked = []
    with sync_playwright() as pw:
        options = {"headless": True, "chromium_sandbox": True,
                   "args": ["--disable-background-networking"]}
        if browser_path:
            options["executable_path"] = str(Path(browser_path).resolve())
        elif sys.platform == "win32":
            options["channel"] = "msedge"
        try:
            browser = pw.chromium.launch(**options)
        except BrowserError:
            raise RuntimeError("Browser launch failed; check browser installation and execution permissions") from None
        try:
            context = browser.new_context(java_script_enabled=False, offline=True, service_workers="block")
            def deny(route):
                blocked.append(route.request.resource_type)
                route.abort()
            context.route("**/*", deny)
            page = context.new_page()
            page.set_content(document, wait_until="load", timeout=30000)
            page.evaluate("document.fonts.ready")
            if not page.evaluate("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)"):
                raise ValueError("Image decode failed")
            if blocked:
                raise ValueError("Unexpected resource request blocked")
            page.pdf(path=str(output), format="A4", print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()
    return {"html_created": True, "pdf_created": True, "network_requests_blocked": len(blocked),
            "scope": "generated_not_visual_or_business_acceptance"}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", default="横纵研究报告")
    parser.add_argument("--author", default="")
    parser.add_argument("--asset", action="append", default=[], type=Path)
    parser.add_argument("--browser-path", type=Path)
    args = parser.parse_args()
    try:
        result = render_pdf(args.input, args.output, args.title, args.author, args.asset, args.browser_path)
    except (ValueError, OSError, ImportError, RuntimeError) as exc:
        parser.exit(1, f"PDF conversion failed: {type(exc).__name__}; check supported input and dependencies.\n")
    import json
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
