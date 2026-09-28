#!/usr/bin/env python3
"""Render JSON templates from a protected JSON values file; never echo values."""
import argparse
import json
import os
import re
import stat
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")


def expand(obj, values):
    if isinstance(obj, dict):
        return {key: expand(value, values) for key, value in obj.items()}
    if isinstance(obj, list):
        return [expand(value, values) for value in obj]
    if not isinstance(obj, str):
        return obj
    match = PLACEHOLDER_RE.fullmatch(obj)
    if match:
        result = values[match.group(1)]
        if not isinstance(result, (str, int, list)) or isinstance(result, bool) or result == "":
            raise ValueError("invalid replacement type")
        return result
    return PLACEHOLDER_RE.sub(lambda m: str(values[m.group(1)]), obj)


def render(template, values_path, output):
    template, values_path, output = map(Path, (template, values_path, output))
    if values_path.is_symlink() or output.parent.is_symlink():
        raise ValueError("symlink")
    if os.name == "posix" and stat.S_IMODE(values_path.stat().st_mode) & 0o077:
        raise ValueError("values file must be owner-only")
    # Windows requires a user-private directory ACL, checked by the operator.
    values = json.loads(values_path.read_text(encoding="utf-8-sig"))
    result = expand(json.loads(template.read_text(encoding="utf-8-sig")), values)
    data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if "{{" in data or "}}" in data:
        raise ValueError("unresolved placeholder")
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template")
    parser.add_argument("--values", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        render(args.template, args.values, args.output)
        print("Created protected configuration; values omitted. Native schema check still required.")
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print("ERROR: rendering failed; check input types, permissions, placeholders and output existence.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
