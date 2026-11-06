#!/usr/bin/env python3
"""Restricted SSH subscription publisher. No HTTP writes or general shell commands."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import cdn


def atomic(path, data, mode=0o640):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.next-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode) if hasattr(os, 'fchmod') else None
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def transact(root, policy, request):
    """Caller holds lock. Only server-owned identity and reviewed addresses may be used."""
    root = Path(root)
    current = root / 'current.yaml'
    payload = current.read_bytes() if current.exists() else b''
    if request == {'op': 'status'}:
        # Current addresses are derived from actual immutable rendering, not a separate state file.
        import re
        return {'success': True, 'sha256': digest(payload),
                'addresses': re.findall(r'^    "server": "([0-9.]+)"$', payload.decode(), re.M)}
    required = {'op', 'expected_sha256', 'addresses'}
    if set(request) not in (required, required | {'expected_new_sha256'}) or request['op'] != 'publish':
        raise ValueError('unsupported request')
    addresses = request['addresses']
    if (not isinstance(addresses, list) or len(addresses) != 2 or
            not all(isinstance(a, str) and a in policy['allowed_addresses'] for a in addresses) or
            len(set(addresses)) != 2):
        raise ValueError('two reviewed distinct addresses required')
    if request['expected_sha256'] != digest(payload):
        raise ValueError('stale publication')
    values = dict(policy['values'], cdn_addresses=addresses)
    new = cdn.configs(values)['tunnel-client.yaml'].encode()
    # New monitors bind publication to the exact payload they just probed.
    # Retain the earlier manual-publisher request shape for staged upgrades.
    if 'expected_new_sha256' in request and request['expected_new_sha256'] != digest(new):
        raise ValueError('probed configuration differs from server policy')
    if new != payload:
        if payload:
            atomic(root/'previous.yaml', payload)
        atomic(current, new)
    return {'success': True, 'changed': new != payload, 'sha256': digest(new), 'addresses': addresses}


def main():
    # These paths are installer-owned; SSH callers cannot supply paths or shell commands.
    root = Path('/var/lib/crossborder-subscription')
    try:
        import fcntl
        raw = sys.stdin.buffer.read(8193)
        if len(raw) > 8192:
            raise ValueError('request too large')
        policy = json.loads(Path('/etc/crossborder-subscription/policy.json').read_text())
        with (root/'publish.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = transact(root, policy, json.loads(raw))
        print(json.dumps(result))
        return 0
    except Exception:
        print(json.dumps({'success': False, 'error': 'publication rejected; inspect private state'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
