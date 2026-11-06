"""No-owned-domain rendering: credentials and certificates are synthetic."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import render


class PinnedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.values = {'SERVER_HOST': '192.0.2.10', 'HY2_UDP_PORT': 443,
                       'HY2_PASSWORD': 'synthetic-only', 'TLS_CERT_SHA256': 'ab' * 32}
        self.template = ROOT / 'examples/client-hy2-pinned.template.json'

    def generate(self, suffix='.json'):
        source = self.path / 'values.json'
        source.write_text(json.dumps(self.values), encoding='utf-8')
        os.chmod(source, 0o600)
        target = self.path / ('client' + suffix)
        render.render(self.template, source, target)
        return target

    def test_no_owned_domain_required(self):
        node = json.loads(self.generate().read_text())['proxies'][0]
        self.assertEqual(node['server'], self.values['SERVER_HOST'])
        self.assertEqual(node['sni'], 'tunnel.invalid')
        self.assertEqual(node['fingerprint'], self.values['TLS_CERT_SHA256'])
        self.assertIs(node['skip-cert-verify'], False)

    def test_no_owned_domain_yaml(self):
        text = self.generate('.yaml').read_text()
        self.assertIn('"proxy-groups":', text)
        self.assertIn('"fingerprint": "' + 'ab' * 32 + '"', text)
        self.assertNotIn('{{', text)

    def test_missing_pin_creates_no_file(self):
        del self.values['TLS_CERT_SHA256']
        with self.assertRaises(KeyError):
            self.generate()
        self.assertFalse((self.path / 'client.json').exists())

    def test_invalid_pins_create_no_file(self):
        for pin in ('', 'ab' * 31, 'zz' * 32, 'chrome', 123):
            with self.subTest(pin_type=type(pin).__name__):
                self.values['TLS_CERT_SHA256'] = pin
                with self.assertRaises(ValueError):
                    self.generate()
                self.assertFalse((self.path / 'client.json').exists())

    def test_pin_cannot_enable_insecure_mode(self):
        template = json.loads(self.template.read_text())
        template['proxies'][0]['skip-cert-verify'] = True
        self.template = self.path / 'template.json'
        self.template.write_text(json.dumps(template))
        with self.assertRaises(ValueError):
            self.generate()
        self.assertFalse((self.path / 'client.json').exists())


if __name__ == '__main__':
    unittest.main()
