#!/usr/bin/env python3
"""Conservative local text scan. Findings contain locations/categories, never values."""
import argparse
import ipaddress
import json
import os
import re
import stat
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{\{[A-Z][A-Z0-9_]*\}\}")
KEY_PATTERN = r"(?:(?:[A-Za-z0-9]+[_-])*(?:password|passwd|private[_-]?key|token|api[_-]?key|secret|uuid|short[_-]?id|authorization|auth)|id)"
SENSITIVE = re.compile(r'''(?ix)(?<![\w-])["']?(''' + KEY_PATTERN + r''')["']?\s*[:=]\s*("[^"\n]*"|'[^'\n]*'|[^\s,\n]+)''')
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
IPV6 = re.compile(r"(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:.]*(?![\w:])")
SAFE_NETS = tuple(ipaddress.ip_network(n) for n in (
    "127.0.0.0/8", "0.0.0.0/32", "192.0.2.0/24", "198.51.100.0/24",
    "203.0.113.0/24", "::1/128", "::/128", "2001:db8::/32"))
SAFE_DNS = {"1.1.1.1", "1.0.0.1", "8.8.8.8", "9.9.9.9"}


def placeholder(value):
    return PLACEHOLDER_RE.fullmatch(value.strip().strip('"\'')) is not None


def inspect_text(text, runtime=False):
    findings = set()
    if not runtime:
        # Across-line values and prefixed environment variables are common in real configs.
        for match in SENSITIVE.finditer(text):
            value = match.group(2).strip('"\'')
            if value not in ("{", "[") and not placeholder(value):
                findings.add((text[:match.start()].count("\n") + 1, "sensitive-assignment"))
        # Decode JSON escapes before examining key/value pairs too.
        try:
            document = json.loads(text)
        except ValueError:
            document = None
        def inspect_json(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if re.fullmatch(KEY_PATTERN, key, re.I) and not isinstance(value, (dict, list)) and not placeholder(str(value)):
                        findings.add((1, "json-sensitive-value"))
                    inspect_json(value)
            elif isinstance(obj, list):
                for value in obj:
                    inspect_json(value)
        inspect_json(document)
        for match in re.finditer(r'"shortIds"\s*:\s*\[([^\]]*)\]', text, re.S):
            values = re.findall(r'"([^"\n]*)"', match.group(1))
            if not values or any(not placeholder(v) for v in values):
                findings.add((text[:match.start()].count("\n") + 1, "sensitive-assignment"))
    for number, line in enumerate(text.splitlines(), 1):
        if runtime:
            if "{{" in line or "}}" in line:
                findings.add((number, "unresolved-placeholder"))
            continue
        if re.search(r"-{5}BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-{5}", line):
            findings.add((number, "private-key-block"))
        if re.search(r"[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@", line, re.I):
            findings.add((number, "url-credentials"))
        if re.search(r"\b(?:ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b", line):
            findings.add((number, "credential-pattern"))
        for match in list(IPV4.finditer(line)) + list(IPV6.finditer(line)):
            try:
                address = ipaddress.ip_address(match.group())
            except ValueError:
                continue
            if str(address) not in SAFE_DNS and not any(
                address.version == net.version and address in net for net in SAFE_NETS
            ):
                findings.add((number, "address-review"))
        if re.search(r"[A-Za-z]:[\\/](?:Users|Codex)[\\/]|/home/[A-Za-z0-9][^\s/]*", line):
            findings.add((number, "personal-path"))
        if re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", line):
            findings.add((number, "email-review"))
    return sorted(findings)


def scan(path, runtime=False):
    root = Path(path)
    def walk(item):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("symbolic link or Windows reparse point")
        if stat.S_ISDIR(info.st_mode):
            # pathlib.rglob may suppress directory enumeration errors. Never skip them.
            with os.scandir(item) as entries:
                children = sorted(entry.name for entry in entries)
            for name in children:
                yield from walk(item / name)
        elif stat.S_ISREG(info.st_mode):
            yield item
        else:
            raise ValueError("non-regular file")
    results, count = [], 0
    for item in walk(root):
        count += 1
        raw = item.read_bytes()
        if b"\x00" in raw:
            raise ValueError("binary input")
        content = raw.decode("utf-8-sig", errors="strict")
        for line, category in inspect_text(content, runtime):
            results.append({"file": item.name if root.is_file() else item.relative_to(root).as_posix(),
                            "line": line, "category": category})
    if not count:
        raise ValueError("no files")
    return {"files": count, "findings": results, "mode": "runtime" if runtime else "public"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--runtime", action="store_true", help="Only check unresolved placeholders; not a leak scan")
    args = parser.parse_args()
    try:
        result = scan(args.path, args.runtime)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result["findings"] else 0
    except (OSError, UnicodeError, ValueError):
        print('{"status":"ERROR","reason":"target unreadable, unsafe, empty or non-text"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
