#!/usr/bin/env python3
"""Certbot deploy hook: validate and atomically switch only this service's TLS pair."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess

BASE = Path('/etc/crossborder-silicon')
CURRENT = Path('/opt/crossborder/silicon/current')
UNIT = 'crossborder-silicon-caddy.service'


def run(args):
    return subprocess.run(args, check=True, capture_output=True, timeout=30).stdout


def replace_link(target):
    temporary = BASE / '.tls-next'
    temporary.symlink_to(target, target_is_directory=True)
    os.replace(temporary, BASE / 'tls')


def deploy():
    if os.geteuid() != 0:
        raise ValueError('root required')
    source = os.environ.get('RENEWED_LINEAGE')
    if source:
        lineage = Path(source)
    else:
        # Reconcile a previously renewed certificate even after a failed deploy hook.
        domain = json.loads((BASE/'credentials/deployment.json').read_text())['domain']
        if not isinstance(domain, str) or Path(domain).name != domain or domain in ('.', '..'):
            raise ValueError('invalid certificate name')
        lineage = BASE/'acme/live'/domain
    if lineage.parent != BASE / 'acme/live':
        raise ValueError('unexpected certificate lineage')
    cert, key = lineage/'fullchain.pem', lineage/'privkey.pem'
    for path in (cert, key):
        if not path.resolve().is_relative_to(BASE/'acme/archive'):
            raise ValueError('unexpected certificate source')
    run(['openssl', 'x509', '-in', str(cert), '-checkend', '86400', '-noout'])
    if run(['openssl','x509','-in',str(cert),'-pubkey','-noout']) != run(['openssl','pkey','-in',str(key),'-pubout']):
        raise ValueError('certificate key mismatch')
    store = BASE/'tls-revisions'
    old = (BASE/'tls').resolve(strict=True)
    if not (BASE/'tls').is_symlink() or old.parent != store:
        raise ValueError('TLS revision storage must be provisioned first')
    gid = pwd.getpwnam('crossborder-silicon').pw_gid
    target = store/hashlib.sha256(cert.read_bytes()).hexdigest()
    if not target.exists():
        target.mkdir(mode=0o750)
        os.chown(target, 0, gid)
        for source, name in ((cert,'fullchain.pem'),(key,'privkey.pem')):
            with os.fdopen(os.open(target/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o640),'wb') as f:
                f.write(source.read_bytes())
            os.chown(target/name,0,gid)
    if (target/'fullchain.pem').read_bytes() != cert.read_bytes() or (target/'privkey.pem').read_bytes() != key.read_bytes():
        raise ValueError('certificate revision drift')
    active = subprocess.run(['systemctl','is-active','--quiet',UNIT]).returncode == 0
    changed = old != target
    if changed:
        replace_link(target)
    try:
        run(['runuser','-u','crossborder-silicon','--',str(CURRENT/'caddy'),'validate','--config',str(CURRENT/'caddy.json')])
        if active and changed:
            run(['systemctl','restart',UNIT])
            run(['systemctl','is-active','--quiet',UNIT])
    except Exception:
        if changed:
            replace_link(old)
            if active:
                run(['systemctl','restart',UNIT])
        raise
    print(json.dumps({'certificate_validated':True,'changed':changed,'restarted':active and changed}))


def main():
    import fcntl
    with open(CURRENT.parent/'manager.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (CURRENT.parent/'pending.json').exists():
            raise ValueError('deployment recovery required before certificate switch')
        deploy()


if __name__ == '__main__':
    main()
