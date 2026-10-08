#!/usr/bin/env python3
"""Offline, bounded draft checks; never equates image presence with identity."""
import re
import json
from html.parser import HTMLParser
from urllib.parse import urlsplit

class Document(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.images = []
        self.hidden = 0
        self.feed(markup)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script'):
            self.hidden += 1
        if self.hidden:
            return
        attrs = dict(attrs)
        if tag == 'img':
            self.images.append(attrs.get('src') or attrs.get('data-src') or '')
        if tag in ('p', 'section', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'h4', 'blockquote'):
            self.text.append(' ')

    def handle_endtag(self, tag):
        if tag in ('style', 'script'):
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in ('p', 'section', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'blockquote'):
            self.text.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)

    def visible_text(self):
        return ' '.join(''.join(self.text).split())


def metadata(markdown):
    match = re.match(r'\A---\s*\n(.*?)\n---(?:\s*\n|$)', markdown, re.S)
    if not match:
        raise ValueError('missing frontmatter')
    fields = {}
    for name in ('title', 'author', 'digest'):
        found = re.search(r'^' + name + r':\s*(.*?)\s*$', match.group(1), re.M)
        if found:
            value = found.group(1)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = json.loads(value) if value[0] == '"' else value[1:-1].replace("''", "'")
            elif value in ('|', '>') or value.startswith(('&', '*', '!', '[', '{')):
                raise ValueError('unsupported frontmatter scalar; use a one-line quoted string')
            fields[name] = value
    if not fields.get('title') or not fields.get('author'):
        raise ValueError('missing expected title or author')
    return fields


def wechat_image(url):
    try:
        parsed = urlsplit(url)
        return (parsed.scheme in ('https', 'http')
                and parsed.hostname == 'mmbiz.qpic.cn'
                and not parsed.username and not parsed.password
                and parsed.port in (None, 80, 443))
    except ValueError:
        return False


def verify_draft(response, expected_html, expected_fields):
    news = response.get('news_item')
    if response.get('errcode') or not isinstance(news, list) or len(news) != 1 or not isinstance(news[0], dict):
        raise ValueError('draft/get did not return exactly one article')
    item = news[0]
    expected = Document(expected_html)
    actual = Document(item.get('content') or '')
    checks = {
        'title_equal': item.get('title') == expected_fields.get('title') and bool(expected_fields.get('title')),
        'author_equal': item.get('author') == expected_fields.get('author') and bool(expected_fields.get('author')),
        'body_text_equal': actual.visible_text() == expected.visible_text() and bool(expected.visible_text()),
        'image_count_equal': len(actual.images) == len(expected.images) and bool(expected.images),
        'image_hosts_valid': bool(actual.images) and all(wechat_image(u) for u in actual.images),
        'cover_present': bool(item.get('thumb_media_id')),
    }
    unchecked = ['body_image_identity', 'body_image_order', 'cover_identity', 'visual_layout']
    if 'digest' in expected_fields:
        checks['digest_equal'] = item.get('digest', '') == expected_fields['digest']
    else:
        unchecked.append('digest_equal')
    return {
        'checks': checks, 'basic_passed': all(checks.values()),
        'verification_scope': 'basic', 'verification_complete': False,
        'unchecked': unchecked, 'expected_img_count': len(expected.images),
        'actual_img_count': len(actual.images),
    }
