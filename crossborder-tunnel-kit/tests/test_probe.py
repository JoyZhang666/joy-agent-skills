"""Isolated probe safeguards; synthetic profiles only, no network."""
import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cdn
import probe


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.uuid = '11111111-1111-4111-8111-111111111111'
        self.profile = cdn.configs(dict(domain='edge.example.com', uuid=self.uuid,
            ws_path='/' + 'a' * 32, xray_port=18443, warp_port=40000,
            cdn_addresses=['104.16.0.1', '104.17.0.1']))['tunnel-client.yaml']

    def test_wrong_auth_changes_every_fallback_node(self):
        text = probe.isolated_text(self.profile, 28001, 28002, bad_auth=True)
        ids = re.findall(r'(?m)^    "uuid": "([a-f0-9-]+)"$', text)
        self.assertEqual(len(ids), 2)
        self.assertNotIn(self.uuid, text)
        self.assertIn('"mixed-port": 28001', text)
        self.assertIn('"127.0.0.1:28002"', text)

    def test_interface_binding_is_quoted_and_duplicate_rejected(self):
        interface = 'Wi-Fi "test"'
        text = probe.isolated_text(self.profile, 28001, 28002, interface=interface)
        self.assertEqual(text.splitlines()[0], '"interface-name": ' + json.dumps(interface))
        bound = '"interface-name": "WLAN"\n' + self.profile
        with self.assertRaises(ValueError):
            probe.isolated_text(bound, 28001, 28002, interface='Wi-Fi')

    def test_tun_enabled_profile_is_rejected(self):
        text = self.profile.replace('"tun":\n  "enable": false', '"tun":\n  "enable": true')
        with self.assertRaises(ValueError):
            probe.isolated_text(text, 28001, 28002)


if __name__ == '__main__':
    unittest.main()
