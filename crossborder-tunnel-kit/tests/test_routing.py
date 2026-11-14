"""Synthetic routing-policy regressions; no remote data or production credentials."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cdn
import edge_monitor
import routing
import subscription


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.values = dict(domain='edge.example.com', uuid='11111111-1111-4111-8111-111111111111',
                           ws_path='/' + 'a' * 32, xray_port=18443, warp_port=40000,
                           cdn_addresses=['104.16.0.1', '104.17.0.1'])
        self.data = {'domain': self.spec('domain', '+.domestic.example.com\n'),
                     'ip': self.spec('ip', '203.0.113.0/24\n')}

    def spec(self, name, content):
        path = self.root / (name + '.list')
        path.write_bytes(content.encode())
        return {'path': str(path), 'sha256': hashlib.sha256(content.encode()).hexdigest()}

    def routed(self, **extra):
        return dict(self.values, routing_profile='cn-direct', routing_data=self.data, **extra)

    def test_order_dns_identity_and_server_unchanged(self):
        original = cdn.configs(self.values)
        with patch.object(cdn, 'yaml_text', json.dumps):
            bundle = cdn.configs(self.routed())
        c = json.loads(bundle['tunnel-client.yaml'])
        self.assertLess(c['rules'].index('RULE-SET,cn-domain,DIRECT'), c['rules'].index('NETWORK,udp,REJECT'))
        self.assertEqual(c['rules'][-1], 'MATCH,SILICON')
        self.assertNotIn('RULE-SET,cn-ip,DIRECT,no-resolve', c['rules'])
        self.assertTrue(all(n['uuid'] == self.values['uuid'] and not n['skip-cert-verify'] for n in c['proxies']))
        self.assertEqual(c['dns']['nameserver-policy']['rule-set:cn-domain'], c['dns']['direct-nameserver'])
        self.assertEqual(c['dns']['nameserver-policy']['rule-set:overseas-domain'], c['dns']['nameserver'])
        self.assertIn('rule-set:cn-domain', c['dns']['fake-ip-filter'])
        for name in ('xray.json', 'caddy.json'):
            self.assertEqual(bundle[name], original[name])

    def test_google_play_exception_survives_domestic_match_and_edge_update(self):
        self.data['domain'] = self.spec('domain', '+.googleapis.cn\n+.domestic.example.com\n')
        values = self.routed()
        target = ['104.17.0.1', '104.18.0.1']
        old = cdn.configs(values)['tunnel-client.yaml'].encode()
        (self.root / 'current.yaml').write_bytes(old)
        expected = cdn.configs(dict(values, cdn_addresses=target))['tunnel-client.yaml'].encode()
        policy = dict(values=values, allowed_addresses=self.values['cdn_addresses'] + target)
        subscription.transact(self.root, policy, dict(op='publish',
            expected_sha256=subscription.digest(old), expected_new_sha256=subscription.digest(expected),
            addresses=target))
        self.assertEqual((self.root / 'current.yaml').read_bytes(), expected)
        with patch.object(cdn, 'yaml_text', json.dumps):
            c = json.loads(cdn.configs(dict(values, cdn_addresses=target))['tunnel-client.yaml'])
        for domain in ['googleapis.cn', 'xn--ngstr-lra8j.com']:
            self.assertIn('+.' + domain, c['rule-providers']['overseas-domain']['payload'])
            self.assertEqual(c['dns']['nameserver-policy']['+.' + domain],
                             ['https://1.1.1.1/dns-query#SILICON'])
        self.assertLess(c['rules'].index('AND,((NETWORK,tcp),(RULE-SET,overseas-domain)),SILICON'),
                        c['rules'].index('RULE-SET,cn-domain,DIRECT'))
        self.assertIn('DOMAIN-SUFFIX,baidu.com,DIRECT', c['rules'])
        self.assertNotIn('RULE-SET,cn-ip,DIRECT,no-resolve', c['rules'])

    def test_invalid_data_fails_closed(self):
        for kind, content in [('domain', '+.*\n'), ('domain', 'example.com,DIRECT\n'),
                              ('ip', '0.0.0.0/0\n'), ('ip', '::/0\n'), ('ip', 'not-an-ip\n'),
                              ('domain', '')]:
            with self.subTest(content=content):
                self.data = {'domain': self.spec('domain', '+.domestic.example.com\n'),
                             'ip': self.spec('ip', '203.0.113.0/24\n')}
                self.data[kind] = self.spec(kind, content)
                with self.assertRaises(ValueError):
                    cdn.configs(self.routed())

    def test_modified_snapshot_or_missing_pin_rejected(self):
        Path(self.data['domain']['path']).write_text('+.changed.example.com\n')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            cdn.configs(self.routed())
        del self.data['domain']['sha256']
        with self.assertRaises(ValueError):
            cdn.configs(self.routed())

    def test_unknown_profile_or_silent_options_rejected(self):
        for extra in [{'routing_profile': 'typo'}, {'routing_data': self.data}, {'direct_processes': ['app.exe']}]:
            with self.assertRaises(ValueError):
                cdn.configs(dict(self.values, **extra))

    def test_process_rules_explicit_and_validated(self):
        output = cdn.configs(self.routed(direct_processes=['verified-app.exe']))['tunnel-client.yaml']
        self.assertIn('PROCESS-NAME,verified-app.exe,DIRECT', output)
        for bad in ['*', 'app.exe,REJECT', 'C:/app.exe']:
            with self.assertRaises(ValueError):
                cdn.configs(self.routed(direct_processes=[bad]))

    def test_publisher_rejects_policy_drift_and_preserves_old(self):
        old = cdn.configs(self.values)['tunnel-client.yaml'].encode()
        (self.root / 'current.yaml').write_bytes(old)
        request = dict(op='publish', expected_sha256=subscription.digest(old),
                       expected_new_sha256=subscription.digest(old), addresses=self.values['cdn_addresses'])
        policy = dict(values=self.routed(), allowed_addresses=self.values['cdn_addresses'])
        with self.assertRaisesRegex(ValueError, 'differs'):
            subscription.transact(self.root, policy, request)
        self.assertEqual((self.root / 'current.yaml').read_bytes(), old)
        request['expected_new_sha256'] = subscription.digest(cdn.configs(self.routed())['tunnel-client.yaml'].encode())
        self.assertTrue(subscription.transact(self.root, policy, request)['changed'])
        self.assertEqual((self.root / 'previous.yaml').read_bytes(), old)

    def test_quality_and_safe_error_classification(self):
        sample = {'exit_code': 0, 'seconds': 0.2, 'http': '200', 'bytes': 5_000_000}
        p = {'a': {'small_requests': [dict(sample), dict(sample)], 'download_5mb': dict(sample)}}
        self.assertEqual(edge_monitor.quality({}, ['a']), 'not_measured')
        self.assertEqual(edge_monitor.quality(p, ['a']), 'bounded_samples_ok')
        self.assertEqual(edge_monitor.quality(p, ['a', 'b']), 'partially_measured')
        p['a']['small_requests'][0]['seconds'] = 4
        self.assertEqual(edge_monitor.quality(p, ['a']), 'small_request_latency_above_target')
        p['a']['download_5mb']['exit_code'] = 35
        self.assertEqual(edge_monitor.quality(p, ['a']), 'target_sample_failed')
        self.assertEqual(edge_monitor.error_code(ValueError('core changed; review new binary first')), 'core_pin_mismatch')
        self.assertNotIn('secret', edge_monitor.error_code(ValueError('secret-token')))


if __name__ == '__main__':
    unittest.main()
