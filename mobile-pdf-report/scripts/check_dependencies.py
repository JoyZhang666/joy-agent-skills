#!/usr/bin/env python3
"""Probe actual Python imports in a bounded child; never install dependencies."""
import json
import subprocess
import sys

PROBE = """import importlib.metadata
import weasyprint
import pypdf
from weasyprint import HTML, CSS
from weasyprint.urls import URLFetcher, URLFetcherResponse, FatalURLFetchingError
assert importlib.metadata.version('weasyprint') == '70.0'
"""


def probe(run=subprocess.run):
    try:
        result = run([sys.executable, "-I", "-c", PROBE], stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, timeout=20)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main():
    ready = probe()
    print(json.dumps({"status": "ready" if ready else "not-ready",
        "required": ["WeasyPrint 70.0 Python API and native dependencies", "pypdf"],
        "optional": ["Python Markdown", "pdfinfo", "fc-list"],
        "rendering_verified": False, "sandbox_verified": False,
        "note": "A successful dependency probe is not a PDF acceptance test."}))
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
