#!/usr/bin/env python3
"""Validate private endpoint JSON; TCP probing requires --probe. No address output."""
import argparse
import ipaddress
import json
import re
import socket
from pathlib import Path


class PrivateParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, 'Invalid arguments; use --help. Values omitted for privacy.\n')


def load_endpoints(path):
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('input too large')
    entries = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(entries, list) or not 1 <= len(entries) <= 50:
        raise ValueError('use batches of 1 to 50 endpoints')
    checked = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'host', 'port'}:
            raise ValueError('expected host and port only')
        host, port = entry['host'], entry['port']
        if not isinstance(host, str) or not 1 <= len(host) <= 253:
            raise ValueError('invalid host')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            labels = host.rstrip('.').split('.')
            if not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', s) for s in labels):
                raise ValueError('invalid host') from None
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('invalid port')
        checked.append((host, port))
    return checked


def probe_endpoints(entries):
    results = []
    for number, (host, port) in enumerate(entries, 1):
        try:
            with socket.create_connection((host, port), timeout=3):
                state = 'TCP_OPEN'
        except OSError:
            state = 'TCP_UNREACHABLE'
        results.append({'endpoint': number, 'state': state})
    return results


def main(argv=None):
    parser = PrivateParser(prog='diagnose-airport-server.py', description=__doc__, allow_abbrev=False)
    parser.add_argument('--input', required=True, type=Path, help='Private JSON: [{"host": "...", "port": 443}], max 50 entries')
    parser.add_argument('--probe', action='store_true', help='Connect only to endpoints you are authorized to test')
    args = parser.parse_args(argv)
    try:
        entries = load_endpoints(args.input)
        if args.probe:
            if any(h.lower().rstrip('.').endswith('.invalid') for h, _ in entries):
                raise ValueError('replace example hosts privately before probing')
            results = probe_endpoints(entries)
            print(json.dumps({'mode': 'probe', 'results': results}))
            return 0 if all(r['state'] == 'TCP_OPEN' for r in results) else 1
        print(json.dumps({'mode': 'validate-only', 'endpoints': len(entries), 'network_used': False}))
        return 0
    except (OSError, ValueError, TypeError, UnicodeError):
        print(json.dumps({'error': 'Input or operation failed; private details omitted'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
