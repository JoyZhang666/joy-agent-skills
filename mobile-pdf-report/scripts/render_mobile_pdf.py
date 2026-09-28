#!/usr/bin/env python3
"""Render through a restricted fetcher; validate before publishing the output file."""
import argparse
import importlib.metadata
import json
import logging
import multiprocessing
import os
from pathlib import Path
import queue
import tempfile

from report_core import (ReportError, ResourcePolicy, output_paths,
                         page_css, prepare_html, validate_pdf)


class RenderErrors(logging.Handler):
    """Record only error presence; never retain paths or diagnostic message text."""
    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.failed = False

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            self.failed = True


def render_worker(document, expected, assets_dir, width, height, target, results):
    # Defense in depth, not an OS sandbox. Caller must isolate untrusted rendering.
    keep = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL", "FONTCONFIG_PATH", "FONTCONFIG_FILE", "WEASYPRINT_DLL_DIRECTORIES", "DYLD_FALLBACK_LIBRARY_PATH"}
    clean = {k: v for k, v in os.environ.items() if k.upper() in keep}
    os.environ.clear()
    os.environ.update(clean)
    try:
        if os.name != "nt":
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
            resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        errors = RenderErrors()
        for name in ("weasyprint", "pypdf"):
            logger = logging.getLogger(name)
            logger.handlers = [errors] if name == "weasyprint" else [logging.NullHandler()]
            logger.setLevel(logging.ERROR)
            logger.propagate = False  # Do not print private diagnostic paths.
        from weasyprint import HTML, CSS
        from weasyprint.urls import URLFetcher, URLFetcherResponse, FatalURLFetchingError
        if importlib.metadata.version("weasyprint") != "70.0":
            raise ReportError("This release requires the verified WeasyPrint 70.0 API")

        policy = ResourcePolicy(assets_dir)

        class LocalFetcher(URLFetcher):
            def fetch(self, url, headers=None):
                try:
                    data, mime = policy.load(url)
                except ReportError:
                    raise FatalURLFetchingError("Resource refused by policy") from None
                return URLFetcherResponse(url, body=data, headers={"Content-Type": mime})

        fetcher = LocalFetcher(allowed_protocols=("file",), allow_redirects=False, fail_on_errors=True)
        base_url = policy.root.as_uri() + "/" if policy.root else "file:///__no_assets__/"
        report = HTML(string=document, base_url=base_url, url_fetcher=fetcher)
        css = CSS(string=page_css(width, height), url_fetcher=fetcher)
        rendered = report.render(stylesheets=[css], presentational_hints=False, pdf_forms=False)
        if (errors.failed or policy.violations or rendered.metadata.attachments
                or any(link[0] == "attachment" for page in rendered.pages for link in page.links)):
            raise ReportError("Embedded attachment or rejected resource")
        rendered.metadata.authors = []
        rendered.metadata.custom = {}
        rendered.metadata.generator = "mobile-pdf-report"
        rendered.write_pdf(target, attachments=[], custom_metadata=False, pdf_forms=False)
        if errors.failed or policy.violations:
            raise ReportError("A resource was refused")
        result = validate_pdf(target, width, height, expected)
        results.put({"ok": True, "validation": result})
    except Exception:
        # Public failures must not print source text, private filesystem paths or URLs.
        results.put({"ok": False, "error": "Rendering or PDF validation failed; no output committed"})


def bounded_worker(document, expected, assets_dir, width, height, target, timeout=60):
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    process = context.Process(target=render_worker,
        args=(document, expected, assets_dir, width, height, str(target), results))
    process.start()
    try:
        process.join(timeout)
        if process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join()
            raise ReportError("Rendering time limit exceeded")
        try:
            result = results.get(timeout=2)
        except queue.Empty:
            raise ReportError("Rendering worker did not return a valid result") from None
        if process.exitcode != 0 or not result.get("ok"):
            raise ReportError("Rendering or PDF validation failed")
        return result["validation"]
    finally:
        results.close()
        results.join_thread()


def render(source, output, title="调查报告", width=105, height=180, assets_dir=None, overwrite=False):
    source, output = output_paths(source, output, overwrite)
    if source.stat().st_size > 2 * 1024 * 1024:
        raise ReportError("Input exceeds 2 MiB")
    text = source.read_text(encoding="utf-8-sig")
    document, expected = prepare_html(text, source.suffix, title, width, height)
    assets = ResourcePolicy(assets_dir).root
    # The original input is never used as an intermediate output.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mobile-pdf-", dir=output.parent) as temporary:
        staged = Path(temporary) / "report.pdf"
        result = bounded_worker(document, expected, str(assets) if assets else None, width, height, staged)
        output_paths(source, output, overwrite)  # Detect newly created destination.
        if overwrite:
            os.replace(staged, output)
        else:
            # An atomic hard-link creation cannot overwrite a racing destination.
            os.link(staged, output)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input")
    p.add_argument("--output", "-o", required=True)
    p.add_argument("--title", default="调查报告")
    p.add_argument("--width-mm", type=int, default=105)
    p.add_argument("--height-mm", type=int, default=180)
    p.add_argument("--assets-dir")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args()
    try:
        result = render(args.input, args.output, args.title, args.width_mm, args.height_mm,
                        args.assets_dir, args.overwrite)
        print(json.dumps({"status": "success", "validation": result}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, ImportError):
        print(json.dumps({"status": "failed", "reason": "Input, dependencies, resource policy or output validation failed; original files preserved."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
