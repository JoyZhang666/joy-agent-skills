"""Offline renderer regression tests using synthetic data only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("render", ROOT / "scripts/render.py")
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.template = self.root / "template.json"
        self.values = self.root / "values.json"
        self.secret = 'synthetic: "#\n---\nproxies: []\n测试🚀\u0085\u2028\u2029'
        self.template.write_text(json.dumps({"port": "{{PORT}}", "password": "{{PASSWORD}}",
                                             "enabled": False, "empty": [], "nested": [{"key": "value"}]}), encoding="utf-8")
        self.values.write_text(json.dumps({"PORT": 443, "PASSWORD": self.secret}), encoding="utf-8")
        os.chmod(self.values, 0o600)

    def test_json_remains_typed_and_lossless(self):
        target = self.root / "config.json"
        render.render(self.template, self.values, target)
        result = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(result["password"], self.secret)
        self.assertEqual(result["port"], 443)
        self.assertIs(result["enabled"], False)

    def test_yaml_escapes_secret_without_injecting_fields(self):
        target = self.root / "config.yaml"
        render.render(self.template, self.values, target)
        text = target.read_text(encoding="utf-8")
        password_lines = [line for line in text.splitlines() if line.startswith('"password": ')]
        self.assertEqual(len(password_lines), 1)
        self.assertEqual(json.loads(password_lines[0].split(": ", 1)[1]), self.secret)
        self.assertNotIn("\nproxies:", text)
        self.assertIn('"port": 443', text)
        self.assertIn('"enabled": false', text)
        self.assertNotIn("\ud83d", text)
        self.assertTrue(text.startswith('"port":'))

    def test_yml_extension_and_nested_collections(self):
        target = self.root / "config.YML"
        render.render(self.template, self.values, target)
        text = target.read_text(encoding="utf-8")
        self.assertIn('"empty": []', text)
        self.assertIn('"nested":\n  -\n    "key": "value"', text)

    def test_missing_parameter_creates_no_file(self):
        self.values.write_text("{}", encoding="utf-8")
        target = self.root / "missing.yaml"
        with self.assertRaises(KeyError):
            render.render(self.template, self.values, target)
        self.assertFalse(target.exists())

    def test_existing_file_is_preserved(self):
        target = self.root / "existing.yaml"
        target.write_text("existing", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            render.render(self.template, self.values, target)
        self.assertEqual(target.read_text(encoding="utf-8"), "existing")

    def test_cli_failure_does_not_echo_values(self):
        target = self.root / "existing.yaml"
        target.write_text("existing", encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/render.py"),
                                 str(self.template), "--values", str(self.values), "--output", str(target)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("synthetic", result.stdout + result.stderr)

    def test_chain_template_retains_security_and_no_external_rules(self):
        template = json.loads((ROOT / "examples/client-hy2-warp.template.json").read_text(encoding="utf-8"))
        proxies = {p["name"]: p for p in template["proxies"]}
        self.assertFalse(proxies["HY2"]["skip-cert-verify"])
        self.assertEqual(proxies["WARP-via-HY2"]["dialer-proxy"], "HY2")
        self.assertFalse(template["allow-lan"])
        self.assertFalse(template["tun"]["enable"])
        self.assertFalse(any(rule.startswith(("GEOSITE,", "GEOIP,", "RULE-SET,")) for rule in template["rules"]))
        for host in ("youtube.com", "google.com", "gstatic.com", "googlevideo.com"):
            self.assertIn("DOMAIN-SUFFIX," + host + ",GOOGLE", template["rules"])


if __name__ == "__main__":
    unittest.main()
