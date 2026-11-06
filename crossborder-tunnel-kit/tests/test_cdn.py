"""Synthetic bundle safety and compatibility tests; no network or deployment."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cdn


class CdnTests(unittest.TestCase):
    def setUp(self):
        self.v = dict(domain='edge.example.com', uuid='11111111-1111-4111-8111-111111111111',
                      ws_path='/' + 'a' * 32, xray_port=18443, warp_port=40000)

    def test_no_direct_fallback_and_udp_blocked(self):
        server = json.loads(cdn.configs(self.v)['xray.json'])
        self.assertEqual([x['protocol'] for x in server['outbounds']], ['socks', 'blackhole'])
        self.assertEqual(server['routing']['rules'][0]['outboundTag'], 'blocked')
        self.assertEqual(server['inbounds'][0]['listen'], '127.0.0.1')

    def test_domain_injection_rejected(self):
        for domain in ['edge.example.com\n:80', '127.0.0.1', '*.example.com', 'x' * 64 + '.com']:
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                cdn.configs(dict(self.v, domain=domain))

    def test_ports_and_credentials_rejected(self):
        for patch in [{'xray_port': True}, {'warp_port': 443}, {'warp_port': 18443},
                      {'uuid': 'secret'}, {'ws_path': '/test*'}]:
            with self.subTest(patch=patch), self.assertRaises((ValueError, TypeError)):
                cdn.configs(dict(self.v, **patch))

    def test_client_group_tls_and_dns_route_present(self):
        client = cdn.configs(self.v)['tunnel-client.yaml']
        for field in ['"proxy-groups":', '"SILICON-CDN-WARP"',
                      '"skip-cert-verify": false', 'https://1.1.1.1/dns-query#SILICON',
                      '"NETWORK,udp,REJECT"']:
            self.assertIn(field, client)
        self.assertNotIn('DIRECT', client)

    def test_cdn_pool_preserves_origin_identity_and_server_configs(self):
        original = cdn.configs(self.v)
        values = dict(self.v, cdn_addresses=['104.16.0.1', '104.17.0.1'],
                      bootstrap_dns=['https://223.5.5.5/dns-query'])
        with patch.object(cdn, 'yaml_text', json.dumps):
            bundle = cdn.configs(values)
        client = json.loads(bundle['tunnel-client.yaml'])
        self.assertEqual([n['server'] for n in client['proxies']], values['cdn_addresses'])
        for node in client['proxies']:
            self.assertEqual(node['servername'], self.v['domain'])
            self.assertEqual(node['ws-opts']['headers']['Host'], self.v['domain'])
            self.assertEqual(node['uuid'], self.v['uuid'])
            self.assertFalse(node['skip-cert-verify'])
        self.assertEqual(client['proxy-groups'][0]['type'], 'fallback')
        self.assertEqual(client['proxy-groups'][0]['proxies'], [n['name'] for n in client['proxies']])
        self.assertEqual(client['dns']['proxy-server-nameserver'], values['bootstrap_dns'])
        self.assertEqual(client['dns']['nameserver'], ['https://1.1.1.1/dns-query#SILICON'])
        self.assertEqual(client['rules'], ['NETWORK,udp,REJECT', 'MATCH,SILICON'])
        for name in ('xray.json', 'caddy.json'):
            self.assertEqual(bundle[name], original[name])

    def test_bad_edge_addresses_and_bootstrap_routes_rejected(self):
        patches = [{'cdn_addresses': x} for x in [[], '104.16.0.1', [True],
                   ['127.0.0.1'], ['10.0.0.1'], ['169.254.1.1'], ['224.0.0.1'],
                   ['2606:4700::1'], ['edge.example.com'], ['104.16.0.1'] * 2,
                   ['104.16.0.' + str(i) for i in range(1, 6)]]]
        patches += [{'bootstrap_dns': x} for x in [[], ['http://1.1.1.1/dns-query'],
                    ['https://dns.example.com/dns-query'], ['https://1.1.1.1/dns-query#SILICON'],
                    ['https://127.0.0.1/dns-query']]]
        for change in patches:
            with self.subTest(change=change), self.assertRaises(ValueError):
                cdn.configs(dict(self.v, **change))

    def test_caddy_has_no_shared_admin_or_automatic_http(self):
        c = json.loads(cdn.configs(self.v)['caddy.json'])
        self.assertTrue(c['admin']['disabled'])
        s = c['apps']['http']['servers']['silicon']
        self.assertEqual(s['listen'], [':443'])
        self.assertEqual(s['protocols'], ['h1', 'h2'])
        self.assertTrue(s['automatic_https']['disable'])

    def test_invalid_input_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'values.json'
            p.write_text('{}', encoding='utf-8')
            p.chmod(0o600)
            with self.assertRaises(KeyError):
                cdn.export(p, Path(d) / 'out')
            self.assertFalse((Path(d) / 'out').exists())

    def test_export_never_overwrites_previous_delivery(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'values.json'
            p.write_text(json.dumps(self.v), encoding='utf-8')
            p.chmod(0o600)
            out = Path(d) / 'out'
            cdn.export(p, out)
            before = {f.name: f.read_bytes() for f in out.iterdir()}
            with self.assertRaises(FileExistsError):
                cdn.export(p, out)
            self.assertEqual(before, {f.name: f.read_bytes() for f in out.iterdir()})
            if os.name == 'posix':
                self.assertEqual(out.stat().st_mode & 0o777, 0o700)
                self.assertTrue(all(f.stat().st_mode & 0o777 == 0o600 for f in out.iterdir()))

    def test_cli_does_not_echo_invalid_secret(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'values.json'
            secret = 'synthetic-secret-do-not-echo'
            p.write_text(json.dumps(dict(self.v, uuid=secret)), encoding='utf-8')
            p.chmod(0o600)
            r = subprocess.run([sys.executable, '-B', cdn.__file__, '--values', str(p),
                                '--output', str(Path(d) / 'out')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertNotIn(secret, r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
