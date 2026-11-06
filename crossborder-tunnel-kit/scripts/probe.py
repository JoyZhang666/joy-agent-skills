#!/usr/bin/env python3
"""Test a generated CDN profile in an isolated Mihomo process, with TUN disabled."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
import uuid


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def isolated_text(text, port, dns_port, bad_auth=False, interface=None):
    if not re.search(r'(?m)^"tun":\r?\n  "enable": false\s*$', text):
        raise ValueError('Only generated TUN-disabled profiles are supported')
    for old, new in [('"mixed-port": 17890', f'"mixed-port": {port}'),
                     ('"127.0.0.1:17853"', f'"127.0.0.1:{dns_port}"')]:
        if text.count(old) != 1:
            raise ValueError('Unexpected generated profile layout')
        text = text.replace(old, new)
    if bad_auth:
        text, count = re.subn(r'(?m)^(    "uuid": )"[a-f0-9-]+"$',
                             lambda m: m[1] + json.dumps(str(uuid.uuid4())), text)
        if count < 1:
            raise ValueError('Expected generated VMess UUIDs')
    if interface is not None:
        if re.search(r'(?m)^(?:"interface-name"|interface-name):', text):
            raise ValueError('Profile already binds an interface; avoid conflicting overrides')
        text = '"interface-name": ' + json.dumps(interface) + '\n' + text
    return text


def probe(args, bad_auth=False):
    profile = Path(args.config)
    text = profile.read_text(encoding='utf-8-sig')
    port, dns_port = free_port(), free_port()
    while dns_port == port:
        dns_port = free_port()
    text = isolated_text(text, port, dns_port, bad_auth, getattr(args, 'interface', None))
    with tempfile.TemporaryDirectory(prefix='probe-', dir=profile.parent) as temporary:
        root = Path(temporary)
        path = root/'config.yaml'
        path.write_text(text, encoding='utf-8')
        path.chmod(0o600)
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        subprocess.run([args.mihomo, '-t', '-d', str(root), '-f', str(path)],
                       check=True, capture_output=True, timeout=30, creationflags=flags)
        with open(root/'runtime.log','wb') as log:
            process = subprocess.Popen([args.mihomo, '-d', str(root), '-f', str(path)],
                                       stdout=log, stderr=log, creationflags=flags)
            try:
                for attempt in range(30):
                    if process.poll() is not None:
                        raise RuntimeError('isolated core exited')
                    try:
                        with socket.create_connection(('127.0.0.1',port),timeout=.2):
                            break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError('isolated core did not listen')
                started = time.monotonic()
                r = subprocess.run([args.curl, '-fsS', '--proxy', f'socks5h://127.0.0.1:{port}',
                                    '--noproxy', '', '--connect-timeout','10','--max-time','40',
                                    'https://www.cloudflare.com/cdn-cgi/trace'],
                                   capture_output=True,text=True,timeout=45,creationflags=flags)
                trace = dict(line.split('=',1) for line in r.stdout.splitlines() if '=' in line)
                return {'request_succeeded':r.returncode==0,'warp_on':trace.get('warp')=='on',
                        'country':trace.get('loc'),'seconds':round(time.monotonic()-started,2)}
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--mihomo',required=True)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--curl',default='curl.exe' if os.name=='nt' else 'curl')
    parser.add_argument('--negative-auth',action='store_true')
    parser.add_argument('--interface', help='Physical outgoing interface for this isolated core only')
    args=parser.parse_args()
    try:
        if hashlib.sha256(Path(args.mihomo).read_bytes()).hexdigest()!=args.sha256.lower():
            raise ValueError('Mihomo pin mismatch')
        positive=probe(args)
        success=positive['request_succeeded'] and positive['warp_on']
        result={'success':success,'positive':positive,'gui_tun_playback':'not_tested',
                'egress_interface':args.interface or 'system_routes_may_include_existing_vpn'}
        if success and args.negative_auth:
            result['wrong_uuid_denied']=not probe(args,True)['request_succeeded']
            result['success']=success and result['wrong_uuid_denied']
        print(json.dumps(result))
        return 0 if result['success'] else 1
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError):
        print(json.dumps({'success':False,'error':'Check private profile, binary pin and network; values omitted.'}))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
