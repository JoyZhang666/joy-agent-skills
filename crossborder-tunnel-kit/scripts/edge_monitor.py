#!/usr/bin/env python3
"""Bounded client-side edge health checks and guarded subscription publication."""
import argparse
import datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from types import SimpleNamespace

import cdn
import probe
from subscription import atomic


def error_code(exc):
    """Only allowlisted classifications; never log private exception payloads."""
    message = str(exc)
    known = {'core changed; review new binary first': 'core_pin_mismatch',
             'restricted publisher unavailable': 'publisher_transport_failed',
             'publisher refused request': 'publisher_rejected',
             'publication readback mismatch; manual inspection required': 'publication_readback_failed',
             'routing snapshot integrity mismatch': 'rule_snapshot_mismatch'}
    if message in known:
        return known[message]
    if isinstance(exc, subprocess.TimeoutExpired):
        return 'probe_or_transport_timeout'
    if isinstance(exc, subprocess.CalledProcessError):
        return 'core_config_validation_failed'
    return 'local_validation_or_runtime_error'


def quality(performance, current):
    measured = [performance[a] for a in current if a in performance]
    if not measured:
        return 'not_measured'
    if len(measured) != len(current):
        return 'partially_measured'
    samples = [s for p in measured for s in p['small_requests'] + [p['download_5mb']]]
    if any(s['exit_code'] != 0 for s in samples):
        return 'target_sample_failed'
    if (any(s.get('http') not in ('200', '204') or s.get('seconds') is None for s in samples)
            or any(p['download_5mb'].get('bytes') != 5_000_000 for p in measured)):
        return 'target_sample_incomplete'
    if any(s['seconds'] > 3 for p in measured for s in p['small_requests']):
        return 'small_request_latency_above_target'
    return 'bounded_samples_ok'


def choose(current, candidates, results, streaks):
    updated = {}
    for address in candidates:
        old = streaks.get(address, 0)
        ok = results.get(address, False)
        updated[address] = min(old + 1, 10) if ok and old > 0 else (1 if ok else max(old - 1, -10) if old < 0 else -1)
    # Preserve order and healthy existing nodes; never churn on a faster single sample.
    if not any(updated[a] <= -2 for a in current):
        return current, updated
    healthy = [a for a in current if updated[a] >= 2]
    healthy += [a for a in candidates if a not in current and updated[a] >= 2]
    return (healthy[:2] if len(healthy) >= 2 else current), updated


def remote(settings, request):
    result = subprocess.run([settings['ssh'], '-F', settings['ssh_config'], 'crossborder-subscription'],
                            input=json.dumps(request).encode(), capture_output=True, timeout=35,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode:
        raise RuntimeError('restricted publisher unavailable')
    data = json.loads(result.stdout)
    if not data.get('success'):
        raise RuntimeError('publisher refused request')
    return data


def run(settings, state_path):
    candidates = settings['candidates']
    networks = [ipaddress.ip_network(n) for n in settings['reviewed_cdn_networks']]
    if not 2 <= len(candidates) <= 8 or len(set(candidates)) != len(candidates):
        raise ValueError('bounded distinct candidates required')
    if not all(any(ipaddress.ip_address(a) in n for n in networks) for a in candidates):
        raise ValueError('candidate outside reviewed provider ranges')
    if not settings['interface']:
        raise ValueError('physical interface required')
    if hashlib.sha256(Path(settings['mihomo']).read_bytes()).hexdigest() != settings['mihomo_sha256']:
        raise ValueError('core changed; review new binary first')
    state_path = Path(state_path)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    now = time.time()
    if now - state.get('checked_epoch', 0) < 300:
        return {'success': True, 'skipped': 'minimum sample spacing'}
    # Stale evidence may not combine with a new run to authorize publication.
    streaks = state.get('streaks', {}) if now - state.get('checked_epoch', 0) < 7200 else {}
    status = remote(settings, {'op': 'status'})
    if len(status['addresses']) != 2 or any(a not in candidates for a in status['addresses']):
        raise ValueError('published pool differs from reviewed candidates')
    values = cdn.read_values(settings['values_file'])
    results, timings, performance = {}, {}, {}
    for address in candidates:
        with tempfile.TemporaryDirectory(prefix='edge-check-', dir=state_path.parent) as directory:
            config = Path(directory)/'client.yaml'
            config.write_text(cdn.configs(dict(values, cdn_addresses=[address]))['tunnel-client.yaml'], encoding='utf-8', newline='\n')
            test = probe.probe(SimpleNamespace(config=str(config), mihomo=settings['mihomo'],
                                              curl=settings['curl'], interface=settings['interface'],
                                              performance=settings.get('performance', False)))
            results[address] = test['request_succeeded'] and test['warp_on']
            timings[address] = test['seconds']
            if 'performance' in test:
                performance[address] = test['performance']
    selected, streaks = choose(status['addresses'], candidates, results, streaks)
    record = {'success': True, 'checked_epoch': now, 'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'interface': settings['interface'], 'results': results, 'seconds': timings, 'streaks': streaks,
              'addresses_before': status['addresses'], 'addresses_after': status['addresses'], 'published': False,
              'performance': performance,
              'quality': quality(performance, status['addresses']),
              'health': 'ok' if all(results[a] for a in status['addresses']) else 'current_entry_unreachable'}
    if selected != status['addresses']:
        # Recheck complete rendered pool with native parser and a real request immediately before commit.
        with tempfile.TemporaryDirectory(prefix='pool-check-', dir=state_path.parent) as directory:
            config = Path(directory)/'client.yaml'
            config.write_text(cdn.configs(dict(values, cdn_addresses=selected))['tunnel-client.yaml'], encoding='utf-8', newline='\n')
            test = probe.probe(SimpleNamespace(config=str(config), mihomo=settings['mihomo'],
                                              curl=settings['curl'], interface=settings['interface']))
            if not (test['request_succeeded'] and test['warp_on']):
                record['publication_held'] = 'final pool check failed'
            else:
                expected = hashlib.sha256(config.read_bytes()).hexdigest()
                result = remote(settings, {'op': 'publish', 'expected_sha256': status['sha256'],
                                           'expected_new_sha256': expected, 'addresses': selected})
                after = remote(settings, {'op': 'status'})
                if result['sha256'] != expected or after['sha256'] != expected:
                    raise RuntimeError('publication readback mismatch; manual inspection required')
                record.update(published=True, addresses_after=selected, sha256=expected)
    atomic(state_path, json.dumps(record, indent=2).encode(), 0o600)
    atomic(state_path.with_name('last-result.json'), json.dumps(record, indent=2).encode(), 0o600)
    return record


def run_cycle(settings, state_path):
    """One routine check; retry unhealthy current entries once after five minutes."""
    result = run(settings, state_path)
    if (result.get('success') and not result.get('published') and
            any(result.get('results', {}).get(a) is False
                for a in result.get('addresses_before', []))):
        pending = dict(result, recheck_pending=True,
                       recheck_due_utc=datetime.datetime.fromtimestamp(
                           time.time() + 300, datetime.timezone.utc).isoformat())
        atomic(Path(state_path).with_name('last-result.json'),
               json.dumps(pending, indent=2).encode(), 0o600)
        # Hold the process lock; do not create an unbounded retry schedule.
        time.sleep(300)
        result = dict(run(settings, state_path), recheck_pending=False,
                      recheck_of_epoch=result['checked_epoch'])
        atomic(Path(state_path).with_name('last-result.json'),
               json.dumps(result, indent=2).encode(), 0o600)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', required=True)
    args = parser.parse_args()
    settings_path = Path(args.settings)
    lock_path = settings_path.with_suffix('.lock')
    with lock_path.open('a+b') as lock:
        try:
            if os.name == 'nt':
                import msvcrt
                lock.seek(0)
                if not lock.read(1):
                    lock.write(b'0'); lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            settings = json.loads(settings_path.read_text(encoding='utf-8-sig'))
            result = run_cycle(settings, settings_path.with_name('monitor-state.json'))
            print(json.dumps(result))
            return 0
        except Exception as exc:
            error = {'success': False, 'error_type': type(exc).__name__,
                     'error_code': error_code(exc),
                     'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     'message': 'No unverified pool published; inspect local protected settings and connectivity.'}
            atomic(settings_path.with_name('last-result.json'), json.dumps(error).encode(), 0o600)
            print(json.dumps(error))
            return 2


if __name__ == '__main__':
    raise SystemExit(main())
