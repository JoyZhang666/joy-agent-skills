#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Post-publish/back-loop HTML quality gate for WeChat drafts."""
import argparse
import re
import sys
from pathlib import Path
from lxml import html

MD_PATTERNS = [
    ("bold", re.compile(r"\*\*[^*]+\*\*")),
    ("heading", re.compile(r"(?m)^\s*#{1,6}\s+")),
    ("fence", re.compile(r"```")),
    ("strike", re.compile(r"~~[^~]+~~")),
]

def parse(path):
    raw = Path(path).read_text(encoding="utf-8")
    return raw, html.fragment_fromstring(raw, create_parent='div')

def norm_text(doc):
    return "\n".join(x.strip() for x in doc.text_content().splitlines() if x.strip())

def count(doc, tag):
    return len(doc.xpath(".//" + tag))

def audit(doc, raw, title):
    issues = []
    if not norm_text(doc):
        issues.append('正文为空')
    lists = doc.xpath(".//ol|.//ul")
    empty_li = doc.xpath(".//li[not(normalize-space(translate(string(.), '\u00a0', ' ')))]")
    if empty_li:
        issues.append(f"空列表项={len(empty_li)}")
    non_li_children = sum(len(x.xpath("./*[not(self::li)]")) for x in lists)
    if non_li_children:
        issues.append(f"列表直属非li节点={non_li_children}")
    imgs = doc.xpath(".//img")
    for img in imgs:
        if not (img.get('src') or img.get('data-src') or '').strip():
            issues.append('图片缺少资源地址')
    visible = norm_text(doc)
    for name, pattern in MD_PATTERNS:
        if pattern.search(visible):
            issues.append(f"Markdown残留:{name}")
    p_nodes = doc.xpath(".//p")
    bordered = sum("border-top" in (p.get("style") or "") for p in p_nodes)
    return issues, {
        "ol": count(doc, "ol"), "ul": count(doc, "ul"), "li": count(doc, "li"),
        "h1": count(doc, "h1"), "h2": count(doc, "h2"), "img": count(doc, "img"),
        "empty_li": len(empty_li), "paragraph_border_top": bordered,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--baseline")
    args = ap.parse_args()
    raw, doc = parse(args.html)
    issues, stats = audit(doc, raw, args.title)
    if args.baseline:
        _, base = parse(args.baseline)
        for tag in ("h1", "h2", "ol", "ul", "li"):
            if count(base, tag) != count(doc, tag):
                issues.append(f"{tag}数量变化:{count(base, tag)}->{count(doc, tag)}")
        if norm_text(base) != norm_text(doc):
            issues.append("正文纯文本与提交基线不一致")
    print("stats=" + repr(stats))
    if issues:
        print("FAIL " + "；".join(issues))
        return 1
    print("PASS 本地 HTML 规则检查通过；图片身份、封面身份和实际排版未核验")
    return 0

if __name__ == "__main__":
    sys.exit(main())
