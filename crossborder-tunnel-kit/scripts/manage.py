#!/usr/bin/env python3
"""Manage one pre-provisioned silicon deployment; never edits shared services."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import cdn

ROOT = Path('/opt/crossborder/silicon')
UNITS = ('crossborder-silicon-xray.service', 'crossborder-silicon-caddy.service')


def run(argv):
    result = subprocess.run(argv, capture_output=True, timeout=35)
    if result.returncode:
        raise RuntimeError('command failed; inspect protected service logs')
    return result.stdout


def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(stream.read()).hexdigest()


def write_json(path, data):
    temp = path.with_suffix('.new')
    with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as stream:
        json.dump(data, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def binaries(values):
    entries = values['binaries']
    for name in ('xray', 'caddy'):
        entry = entries[name]
        path = Path(entry['path'])
        if not path.is_absolute() or path.is_symlink() or digest(path) != entry['sha256']:
            raise ValueError('binary pin mismatch')
    return entries


def current(root):
    link = root / 'current'
    if not link.is_symlink():
        if link.exists():
            raise ValueError('current is not an owned symlink')
        return None
    target = link.resolve(strict=True)
    if target.parent != (root / 'releases').resolve() or not target.is_dir():
        raise ValueError('current target outside owned releases')
    return target.name


def switch(root, revision):
    link = root / 'current'
    current(root)  # Refuse takeover of unexpected files or external links.
    if revision is None:
        if link.is_symlink():
            link.unlink()
        return
    if Path(revision).name != revision or not (root / 'releases' / revision).is_dir():
        raise ValueError('invalid revision')
    temporary = root / '.current-next'
    if temporary.exists() or temporary.is_symlink():
        raise ValueError('stale switch link needs inspection')
    temporary.symlink_to(root / 'releases' / revision, target_is_directory=True)
    os.replace(temporary, link)


def restart():
    run(['systemctl', 'restart', *UNITS])
    for unit in UNITS:
        run(['systemctl', 'is-active', '--quiet', unit])


def health():
    for unit in UNITS:
        run(['systemctl', 'is-active', '--quiet', unit])
    config = json.loads((ROOT/'current/caddy.json').read_text())
    domain = config['apps']['http']['servers']['silicon']['routes'][0]['match'][0]['host'][0]
    status = run(['curl', '-sS', '--noproxy', '*', '--resolve', f'{domain}:443:127.0.0.1',
                  '--retry', '5', '--retry-connrefused', '--retry-delay', '1', '--retry-max-time', '10',
                  '--connect-timeout', '5', '--max-time', '10', '-o', '/dev/null',
                  '-w', '%{http_code}', f'https://{domain}/'])
    if status != b'404':
        raise RuntimeError('local HTTPS origin check failed')
    response = run(['curl', '-fsS', '--socks5-hostname', '127.0.0.1:40000',
                    '--connect-timeout', '5', '--max-time', '15',
                    'https://www.cloudflare.com/cdn-cgi/trace'])
    if b'warp=on' not in response.splitlines():
        raise RuntimeError('WARP exit unavailable')


def recover(root, old, restart_fn=restart):
    switch(root, old)
    if old is None:
        run(['systemctl', 'stop', *UNITS])
    else:
        restart_fn()


def activate(root, revision, restart_fn=restart, health_fn=health):
    if (root / 'pending.json').exists():
        raise ValueError('pending transaction; use rollback first')
    old = current(root)
    if old == revision:
        health_fn()
        return False
    write_json(root / 'pending.json', {'previous': old, 'candidate': revision})
    try:
        switch(root, revision)
        restart_fn()
        health_fn()
    except Exception:
        recover(root, old, restart_fn)
        (root / 'pending.json').unlink()
        raise
    write_json(root / 'state.json', {'previous': old, 'current': revision})
    (root / 'pending.json').unlink()
    return True


def preflight(root):
    import pwd
    if os.geteuid() != 0:
        raise ValueError('root required for service lifecycle')
    account = pwd.getpwnam('crossborder-silicon')
    if not root.is_dir() or root.is_symlink() or root.stat().st_uid != 0:
        raise ValueError('owned deployment root required')
    for unit in UNITS:
        path = Path('/etc/systemd/system') / unit
        if not path.is_file() or path.is_symlink() or path.stat().st_uid != 0:
            raise ValueError('dedicated unit provisioning required')
        content = path.read_text()
        engine = 'xray' if 'xray' in unit else 'caddy'
        if ('User=crossborder-silicon' not in content or
                f'ExecStart={root}/current/{engine} ' not in content):
            raise ValueError('unexpected unit configuration')
    run(['systemctl', 'is-active', '--quiet', 'crossborder-silicon-firewall.service'])
    run(['nft', 'list', 'table', 'inet', 'crossborder_silicon'])
    return account.pw_gid


def stage(root, values, gid):
    if (root / 'releases').is_symlink():
        raise ValueError('release root must not be a symlink')
    sources = binaries(values)
    bundle = cdn.configs(values)
    material = json.dumps({'configs': bundle, 'pins': {k: v['sha256'] for k, v in sources.items()}}, sort_keys=True)
    revision = hashlib.sha256(material.encode()).hexdigest()[:24]
    destination = root / 'releases' / revision
    if destination.exists():
        # Detect drift before reusing immutable configuration or executable files.
        for name in ('xray.json', 'caddy.json'):
            if (destination / name).read_text() != bundle[name]:
                raise ValueError('release configuration drift')
        for name in ('xray', 'caddy'):
            if digest(destination / name) != sources[name]['sha256']:
                raise ValueError('release binary drift')
        return revision
    (root / 'releases').mkdir(exist_ok=True, mode=0o750)
    os.chown(root / 'releases', 0, gid)
    temp = Path(tempfile.mkdtemp(prefix='.stage-', dir=root / 'releases'))
    os.chown(temp, 0, gid)
    temp.chmod(0o750)
    try:
        for name in ('xray.json', 'caddy.json'):
            (temp / name).write_text(bundle[name])
            os.chown(temp / name, 0, gid)
            (temp / name).chmod(0o640)
        for name in ('xray', 'caddy'):
            shutil.copyfile(sources[name]['path'], temp / name)
            os.chown(temp / name, 0, gid)
            (temp / name).chmod(0o750)
            if digest(temp / name) != sources[name]['sha256']:
                raise ValueError('copy digest mismatch')
        run(['runuser', '-u', 'crossborder-silicon', '--', str(temp/'xray'), 'run', '-test', '-config', str(temp/'xray.json')])
        run(['runuser', '-u', 'crossborder-silicon', '--', str(temp/'caddy'), 'validate', '--config', str(temp/'caddy.json')])
        temp.rename(destination)
    finally:
        if temp.exists():
            shutil.rmtree(temp)  # Only the exclusive temporary directory created above.
    return revision


def plan(root, values):
    sources = binaries(values)
    bundle = cdn.configs(values)
    material = json.dumps({'configs': bundle, 'pins': {k: v['sha256'] for k, v in sources.items()}}, sort_keys=True)
    revision = hashlib.sha256(material.encode()).hexdigest()[:24]
    old = current(root)
    conflicts = []
    if (root/'pending.json').exists():
        conflicts.append('pending transaction requires rollback')
    if os.name != 'posix':
        conflicts.append('service preflight requires Linux')
    else:
        try:
            preflight(root)
        except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
            conflicts.append('dedicated account, owned units, root permissions or active firewall missing')
    changing = old != revision
    return {'changed': False, 'stage': 'plan', 'current_revision': old,
            'proposed_revision': revision, 'would_change': changing,
            'writes': ([f'releases/{revision}/{name}' for name in ('xray', 'caddy', 'xray.json', 'caddy.json')]
                       + ['current', 'pending.json', 'state.json']) if changing else [],
            'restart_units': list(UNITS) if changing else [],
            'conflicts': conflicts, 'local_service_prerequisites_verified': not conflicts,
            'pending_checks': ['native certificate validation', 'WARP exit', 'cloud ingress'],
            'limits': 'Cloud security group and end-to-end reachability require separate verification.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['plan', 'apply', 'status', 'check', 'export', 'rollback'])
    p.add_argument('--deployment', required=True)
    p.add_argument('--output')
    p.add_argument('--json', action='store_true', help='Results are always redacted JSON.')
    args = p.parse_args()
    try:
        values = cdn.read_values(args.deployment)
        if values['warp_port'] != 40000:
            raise ValueError('managed deployment requires WARP port 40000')
        if args.command == 'export':
            if not args.output:
                raise ValueError('output required')
            cdn.export(args.deployment, args.output)
            result = {'changed': True, 'stage': 'export'}
        elif args.command == 'plan':
            result = plan(ROOT, values)
        elif args.command == 'status':
            result = {'changed': False, 'current': current(ROOT), 'pending': (ROOT/'pending.json').exists()}
        else:
            if os.name != 'posix':
                raise ValueError('service operations require Linux')
            import fcntl
            gid = preflight(ROOT)
            with open(ROOT / 'manager.lock', 'a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if args.command == 'apply':
                    result = {'changed': activate(ROOT, stage(ROOT, values, gid)), 'stage': 'runtime-basic'}
                elif args.command == 'rollback':
                    journal = ROOT / ('pending.json' if (ROOT/'pending.json').exists() else 'state.json')
                    state = json.loads(journal.read_text())
                    recover(ROOT, state['previous'])
                    write_json(ROOT/'state.json', {'current': state['previous'], 'previous': state['previous']})
                    if (ROOT/'pending.json').exists():
                        (ROOT/'pending.json').unlink()
                    result = {'changed': True, 'stage': 'rollback'}
                else:
                    health()
                    result = {'changed': False, 'stage': 'runtime-basic'}
        print(json.dumps(dict(result, success=True, end_to_end='not_tested_by_this_command')))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        print(json.dumps({'success': False, 'stage': args.command, 'error': 'Inspect prerequisites, private input and protected logs; values omitted.'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
