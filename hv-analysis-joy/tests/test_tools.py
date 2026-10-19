"""Synthetic regression tests. Run: python -B -m unittest discover -s tests -v"""
import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from aggregate import aggregate, normalize_sq
from md_to_pdf import build_html, render_pdf


class AggregationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "输入"
        self.inputs.mkdir()
        self.output = self.root / "新结果"

    def write_sq(self, name="sq1.json", **overrides):
        data = {"sq_id": "SQ1", "topic": "Synthetic", "summary": {"finding": "Unknown"},
                "data_points": [{"id": "D1", "field": "revenue", "value": 120000000,
                                 "unit": "CNY", "entity": "Synthetic Parent", "period": "2025"}],
                "sources": []}
        data.update(overrides)
        (self.inputs / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def test_structured_summary_preserves_raw_and_numeric_value(self):
        raw = self.write_sq()
        result = aggregate(self.inputs, self.output, ["SQ1"])
        self.assertEqual(result["raw_sq_data"]["sq1.json"], raw)
        self.assertEqual(result["sq_files"]["SQ1"]["data_points"][0]["value"], 120000000)
        self.assertEqual(result["fact_verification"], "not_performed")
        self.assertEqual(json.loads((self.output / "aggregation.json").read_text(encoding="utf-8")), result)

    def test_summary_null_list_and_legacy_fields(self):
        for value in (None, [], {"x": "y"}):
            sq = normalize_sq({"summary": value, "research_subject": "Legacy",
                               "data_points": [{"id": "SQ2-D1.1", "fact": "A claim", "confidence": "high"}]}, "sq2")
            self.assertEqual(sq["sq_id"], "SQ2")
            self.assertEqual(sq["topic"], "Legacy")
            self.assertEqual(sq["data_points"][0]["evidence_status"], "unreviewed")
            self.assertEqual(sq["data_points"][0]["reported_confidence"], "high")

    def test_partial_is_actual_plan_coverage(self):
        self.write_sq()
        result = aggregate(self.inputs, self.output, ["SQ1", "SQ2"])
        self.assertEqual(result["technical_status"], "partial")
        self.assertEqual(result["missing_sq"], ["SQ2"])

    def test_empty_data_is_missing(self):
        self.write_sq(data_points=[])
        self.assertEqual(aggregate(self.inputs, self.output, ["SQ1"])["missing_sq"], ["SQ1"])

    def test_same_origin_does_not_inflate_declared_origin_count(self):
        self.write_sq(sources=[{"url": "https://example.com/a", "origin_id": "A"},
                               {"url": "https://example.com/b", "origin_id": "A"}])
        result = aggregate(self.inputs, self.output, ["SQ1"])
        self.assertEqual(result["distinct_source_urls"], 2)
        self.assertEqual(result["declared_origin_count"], 1)
        self.assertEqual(result["source_independence"], "not_verified")

    def test_csv_formulas_are_escaped_but_raw_json_is_preserved(self):
        points = [{"id": "D1", "value": " =1+1"}, {"id": "D2", "value": -2.5}]
        self.write_sq(data_points=points)
        result = aggregate(self.inputs, self.output, ["SQ1"])
        with (self.output / "data.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["Value"], "' =1+1")
        self.assertEqual(rows[1]["Value"], "-2.5")
        self.assertEqual(result["raw_sq_data"]["sq1.json"]["data_points"], points)

    def test_existing_output_is_untouched(self):
        self.write_sq()
        self.output.mkdir()
        marker = self.output / "keep.txt"
        marker.write_text("keep")
        with self.assertRaises(FileExistsError):
            aggregate(self.inputs, self.output, ["SQ1"])
        self.assertEqual(marker.read_text(), "keep")

    def test_duplicate_sq_is_rejected_before_output(self):
        self.write_sq()
        self.write_sq("sq2.json")
        with self.assertRaises(ValueError):
            aggregate(self.inputs, self.output, ["SQ1"])
        self.assertFalse(self.output.exists())

    def test_duplicate_data_id_is_rejected(self):
        self.write_sq(data_points=[{"id": "D1"}, {"id": "D1"}])
        with self.assertRaises(ValueError):
            aggregate(self.inputs, self.output, ["SQ1"])

    def test_bad_json_and_no_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            aggregate(self.inputs, self.output, ["SQ1"])
        (self.inputs / "sq1.json").write_text("{")
        with self.assertRaises(ValueError):
            aggregate(self.inputs, self.output, ["SQ1"])
        self.assertFalse(self.output.exists())

    def test_cli_partial_exit_code(self):
        self.write_sq()
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/aggregate.py"),
                                 "--input-dir", str(self.inputs), "--output-dir", str(self.output),
                                 "--expected-sq", "SQ1", "SQ2"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["technical_status"], "partial")


@unittest.skipUnless(importlib.util.find_spec("markdown"), "Optional PDF dependency Markdown is absent")
class RestrictedMarkdownTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "input.md"

    def build(self, content, assets=()):
        self.source.write_text(content, encoding="utf-8")
        return build_html(self.source, '<Title & "quoted">', assets=assets)

    def test_markdown_and_escaped_title(self):
        html = self.build("# 中文标题\n\n| A | B |\n|---|---|\n| 1 | 2 |")
        self.assertIn("<table>", html)
        self.assertIn("&lt;Title &amp; &quot;quoted&quot;&gt;", html)
        self.assertIn("script-src &#x27;none&#x27;", html)

    def test_raw_html_is_rejected(self):
        for content in ('<script>alert(1)</script>', '<img src="x" onerror="alert(1)">', '<iframe src="x"></iframe>'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.build(content)

    def test_relative_document_links_keep_text_without_file_access(self):
        html = self.build("[本地证据](materials.md) 与 [父目录](../outside.md)")
        self.assertIn("<a>本地证据</a>", html)
        self.assertIn("<a>父目录</a>", html)
        self.assertNotIn('href="materials.md"', html)

    def test_remote_data_and_file_images_are_rejected(self):
        for src in ("https://example.com/a.png", "file:///etc/passwd", "data:image/png;base64,AAAA", "//example.com/a.png"):
            with self.subTest(src=src), self.assertRaises(ValueError):
                self.build(f"![x]({src})")

    def test_local_image_requires_explicit_asset(self):
        import base64
        asset = self.root / "dot.png"
        asset.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aJ1sAAAAASUVORK5CYII="))
        with self.assertRaises(ValueError):
            self.build("![dot](dot.png)")
        self.assertIn("data:image/png;base64,", self.build("![dot](dot.png)", [asset]))

    def test_asset_outside_source_directory_is_rejected(self):
        sub = self.root / "sub"
        sub.mkdir()
        self.source = sub / "input.md"
        outside = self.root / "outside.png"
        outside.write_bytes(b"\x89PNG\r\n\x1a\n")
        with self.assertRaises(ValueError):
            self.build("![x](../outside.png)", [outside])

    def test_javascript_and_file_links_are_rejected(self):
        for src in ("javascript:alert", "file:///etc/passwd"):
            with self.subTest(src=src), self.assertRaises(ValueError):
                self.build(f"[link]({src})")

    def test_pdf_output_no_overwrite(self):
        self.source.write_text("# Safe", encoding="utf-8")
        output = self.root / "existing.pdf"
        output.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            render_pdf(self.source, output, "Test")
        self.assertEqual(output.read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
