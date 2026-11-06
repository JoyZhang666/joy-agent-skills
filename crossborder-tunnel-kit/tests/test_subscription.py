"""Guarded publication and health hysteresis using synthetic identities only."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import time
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import cdn
import edge_monitor
import subscription


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.addresses = ['104.16.0.1', '104.17.0.1', '104.18.0.1', '104.19.0.1']
        self.values = dict(domain='edge.example.com', uuid='11111111-1111-4111-8111-111111111111',
                           ws_path='/'+'a'*32, xray_port=18443, warp_port=40000)
        self.policy = dict(values=self.values, allowed_addresses=self.addresses)

    def test_subscription_route_exact_and_private_without_changing_xray(self):
        base = cdn.configs(self.values)
        path = '/s/'+'b'*64+'/client.yaml'
        new = cdn.configs(dict(self.values, subscription_path=path))
        self.assertEqual(base['xray.json'], new['xray.json'])
        self.assertEqual(base['tunnel-client.yaml'], new['tunnel-client.yaml'])
        routes = json.loads(new['caddy.json'])['apps']['http']['servers']['silicon']['routes']
        self.assertEqual(routes[0], json.loads(base['caddy.json'])['apps']['http']['servers']['silicon']['routes'][0])
        self.assertEqual(routes[1]['match'][0]['path'], [path])
        self.assertEqual(routes[1]['match'][0]['method'], ['GET', 'HEAD'])
        self.assertIn('no-store', routes[1]['handle'][0]['response']['set']['Cache-Control'][0])
        self.assertNotIn('browse', routes[1]['handle'][2])
        for invalid in ['/s/*', '/s/../client.yaml', '/s/'+'a'*64+'/client.yaml?x=1']:
            with self.assertRaises(ValueError):
                cdn.configs(dict(self.values, subscription_path=invalid))

    def test_publication_cas_previous_and_fixed_identity(self):
        with tempfile.TemporaryDirectory() as d:
            status = subscription.transact(d, self.policy, {'op':'status'})
            first = subscription.transact(d, self.policy, dict(op='publish', expected_sha256=status['sha256'], addresses=self.addresses[:2]))
            payload = (Path(d)/'current.yaml').read_bytes()
            self.assertEqual(first['sha256'], hashlib.sha256(payload).hexdigest())
            with self.assertRaises(ValueError):
                subscription.transact(d, self.policy, dict(op='publish', expected_sha256=status['sha256'], addresses=self.addresses[2:]))
            subscription.transact(d, self.policy, dict(op='publish', expected_sha256=first['sha256'], addresses=self.addresses[2:]))
            self.assertEqual((Path(d)/'previous.yaml').read_bytes(), payload)
            self.assertIn(self.values['uuid'], (Path(d)/'current.yaml').read_text())
            self.assertEqual(subscription.transact(d, self.policy, {'op':'status'})['addresses'], self.addresses[2:])

    def test_publisher_rejects_unreviewed_addresses_and_extra_input(self):
        with tempfile.TemporaryDirectory() as d:
            sha = hashlib.sha256(b'').hexdigest()
            for addresses in [['127.0.0.1', self.addresses[0]], [self.addresses[0]]*2, self.addresses[:1]]:
                with self.assertRaises(ValueError):
                    subscription.transact(d, self.policy, dict(op='publish', expected_sha256=sha, addresses=addresses))
            with self.assertRaises(ValueError):
                subscription.transact(d, self.policy, dict(op='publish', expected_sha256=sha, addresses=self.addresses[:2], values=self.values))
            self.assertFalse((Path(d)/'current.yaml').exists())

    def test_policy_drift_rejected_before_current_or_previous_change(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            root.joinpath('current.yaml').write_bytes(b'known-working')
            root.joinpath('previous.yaml').write_bytes(b'previous-working')
            expected = hashlib.sha256(cdn.configs(dict(self.values, cdn_addresses=self.addresses[:2]))
                                      ['tunnel-client.yaml'].encode()).hexdigest()
            policy = dict(self.policy, values=dict(self.values, bootstrap_dns=['https://1.0.0.1/dns-query']))
            request = dict(op='publish', expected_sha256=hashlib.sha256(b'known-working').hexdigest(),
                           expected_new_sha256=expected, addresses=self.addresses[:2])
            with self.assertRaises(ValueError):
                subscription.transact(root, policy, request)
            self.assertEqual(root.joinpath('current.yaml').read_bytes(), b'known-working')
            self.assertEqual(root.joinpath('previous.yaml').read_bytes(), b'previous-working')
            accepted = subscription.transact(root, self.policy, request)
            self.assertEqual(accepted['sha256'], expected)
            self.assertEqual(root.joinpath('previous.yaml').read_bytes(), b'known-working')

    def test_single_failure_does_not_replace_and_two_failures_do(self):
        result = dict(zip(self.addresses, [False, True, True, True]))
        current, streaks = edge_monitor.choose(self.addresses[:2], self.addresses, result, {})
        self.assertEqual(current, self.addresses[:2])
        current, _ = edge_monitor.choose(current, self.addresses, result, streaks)
        self.assertEqual(current, self.addresses[1:3])

    def test_all_down_preserves_last_known_and_no_speed_churn(self):
        for results in [dict.fromkeys(self.addresses, False), dict.fromkeys(self.addresses, True)]:
            current, streaks = edge_monitor.choose(self.addresses[:2], self.addresses, results, {})
            current, _ = edge_monitor.choose(current, self.addresses, results, streaks)
            self.assertEqual(current, self.addresses[:2])

    def test_insufficient_replacements_preserve_both_entries(self):
        results = dict(zip(self.addresses, [False, False, True, False]))
        current, streaks = edge_monitor.choose(self.addresses[:2], self.addresses, results, {})
        current, _ = edge_monitor.choose(current, self.addresses, results, streaks)
        self.assertEqual(current, self.addresses[:2])

    def test_monitor_rechecks_pool_then_commits_and_reads_back(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            values = root/'values.json'
            values.write_text(json.dumps(self.values)); values.chmod(0o600)
            binary = root/'core'; binary.write_bytes(b'fixture')
            state = root/'state.json'
            state.write_text(json.dumps({'checked_epoch':time.time()-600,
                'streaks':dict(zip(self.addresses,[-1,1,1,1]))}))
            settings = dict(candidates=self.addresses, reviewed_cdn_networks=['104.16.0.0/13'],
                interface='fixture-physical', mihomo=str(binary), curl='fixture-curl', values_file=str(values),
                mihomo_sha256=hashlib.sha256(b'fixture').hexdigest())
            target = self.addresses[1:3]
            wanted = hashlib.sha256(cdn.configs(dict(self.values,cdn_addresses=target))['tunnel-client.yaml'].encode()).hexdigest()
            before = dict(success=True, sha256='0'*64, addresses=self.addresses[:2])
            after = dict(success=True, sha256=wanted, addresses=target)
            tests = [dict(request_succeeded=ok,warp_on=ok,seconds=1) for ok in [False,True,True,True,True]]
            with patch.object(edge_monitor,'remote',side_effect=[before,after,after]) as remote, \
                    patch.object(edge_monitor.probe,'probe',side_effect=tests) as check:
                result=edge_monitor.run(settings,state)
            self.assertTrue(result['published'])
            self.assertEqual(check.call_count,5)
            self.assertEqual(remote.call_args_list[1].args[1]['expected_sha256'],before['sha256'])
            self.assertEqual(remote.call_args_list[1].args[1]['expected_new_sha256'], wanted)
            self.assertEqual(json.loads(state.read_text())['addresses_after'],target)

    def test_changed_core_is_rejected_before_any_network_or_publication(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); binary=root/'core'; binary.write_bytes(b'changed')
            settings=dict(candidates=self.addresses,reviewed_cdn_networks=['104.16.0.0/13'],
                interface='fixture',mihomo=str(binary),mihomo_sha256='0'*64)
            with patch.object(edge_monitor,'remote') as remote, self.assertRaises(ValueError):
                edge_monitor.run(settings,root/'state.json')
            remote.assert_not_called()

    def test_48h_old_samples_cannot_publish_until_fresh_five_minute_recheck(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            values = root/'values.json'
            values.write_text(json.dumps(self.values)); values.chmod(0o600)
            binary = root/'core'; binary.write_bytes(b'fixture')
            state = root/'state.json'
            clock = [time.time()]
            state.write_text(json.dumps({'checked_epoch': clock[0]-48*3600,
                'streaks': dict(zip(self.addresses, [-5,5,5,5]))}))
            settings = dict(candidates=self.addresses, reviewed_cdn_networks=['104.16.0.0/13'],
                interface='fixture-physical', mihomo=str(binary), curl='fixture-curl',
                values_file=str(values), mihomo_sha256=hashlib.sha256(b'fixture').hexdigest())
            target = self.addresses[1:3]
            wanted = hashlib.sha256(cdn.configs(dict(self.values, cdn_addresses=target))['tunnel-client.yaml'].encode()).hexdigest()
            before = dict(success=True, sha256='0'*64, addresses=self.addresses[:2])
            after = dict(success=True, sha256=wanted, addresses=target)
            probes = [dict(request_succeeded=ok, warp_on=ok, seconds=1)
                      for ok in [False,True,True,True, False,True,True,True, True]]

            def advance(seconds):
                self.assertEqual(seconds, 300)
                self.assertEqual(remote.call_count, 1)  # Only status, no premature publish.
                self.assertEqual(json.loads(state.read_text())['streaks'][self.addresses[0]], -1)
                pending = json.loads((root/'last-result.json').read_text())
                self.assertTrue(pending['recheck_pending'])
                clock[0] += seconds

            with patch.object(edge_monitor, 'remote', side_effect=[before,before,after,after]) as remote, \
                    patch.object(edge_monitor.probe, 'probe', side_effect=probes) as probe, \
                    patch.object(edge_monitor.time, 'time', side_effect=lambda:clock[0]), \
                    patch.object(edge_monitor.time, 'sleep', side_effect=advance) as sleep:
                result = edge_monitor.run_cycle(settings, state)
            self.assertTrue(result['published'])
            self.assertFalse(result['recheck_pending'])
            self.assertEqual(probe.call_count, 9)
            sleep.assert_called_once_with(300)
            self.assertEqual(json.loads(state.read_text())['addresses_after'], target)

    def test_healthy_current_entries_skip_recheck_even_if_spare_failed(self):
        records = [dict(success=True, published=False, addresses_before=self.addresses[:2],
                        results=dict(zip(self.addresses,[True,True,False,False]))),
                   dict(success=True, skipped='minimum sample spacing'),
                   dict(success=True, published=True, addresses_before=self.addresses[:2],
                        results=dict(zip(self.addresses,[False,True,True,True])))]
        for record in records:
            with self.subTest(record=record), patch.object(edge_monitor, 'run', return_value=record) as run, \
                    patch.object(edge_monitor.time, 'sleep') as sleep:
                self.assertEqual(edge_monitor.run_cycle({}, 'unused'), record)
                run.assert_called_once(); sleep.assert_not_called()

    def test_persistent_failure_rechecks_once_then_stops(self):
        with tempfile.TemporaryDirectory() as d:
            record = dict(success=True, published=False, checked_epoch=1000,
                          addresses_before=self.addresses[:2], results=dict.fromkeys(self.addresses, False))
            with patch.object(edge_monitor, 'run', return_value=record) as run, \
                    patch.object(edge_monitor.time, 'sleep') as sleep:
                result = edge_monitor.run_cycle({}, Path(d)/'state.json')
            self.assertEqual(run.call_count, 2)
            sleep.assert_called_once_with(300)
            self.assertFalse(result['published'])
            self.assertFalse(result['recheck_pending'])


if __name__ == '__main__':
    unittest.main()
