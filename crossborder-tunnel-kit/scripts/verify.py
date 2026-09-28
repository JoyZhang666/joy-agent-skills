#!/usr/bin/env python3
"""Compare a file with one independently obtained, trusted SHA-256 digest."""
import argparse
import hashlib
import re
from pathlib import Path


def verify(path, expected):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        raise ValueError("expected digest must be 64 hex characters")
    with Path(path).open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        return digest.hexdigest() == expected.lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file")
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        ok = verify(args.file, args.sha256)
        print("MATCH (one expected digest)" if ok else "MISMATCH")
        return 0 if ok else 1
    except (OSError, ValueError):
        print("ERROR: missing file or invalid expected digest")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
