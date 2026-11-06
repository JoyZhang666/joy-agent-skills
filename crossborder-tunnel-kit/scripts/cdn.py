#!/usr/bin/env python3
"""Render a private VMess/WS/TLS bundle. Does not install or activate services."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import uuid

from render import yaml_text


def validate(values):
    if not isinstance(values, dict):
        raise ValueError('object required')
    domain = values['domain']
    if not isinstance(domain, str) or len(domain) > 253 or not re.fullmatch(
        r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', domain
    ):
        raise ValueError('domain required')
    if str(uuid.UUID(values['uuid'])) != values['uuid']:
        raise ValueError('canonical UUID required')
    if not re.fullmatch(r'/[a-f0-9]{32,64}', values['ws_path']):
        raise ValueError('random hex path required')
    for key in ('xray_port', 'warp_port'):
        if type(values[key]) is not int or not 1024 <= values[key] <= 65535:
            raise ValueError('unprivileged port required')
    if values['warp_port'] == values['xray_port']:
        raise ValueError('ports must differ')
    for key in ('cdn_addresses', 'bootstrap_dns'):
        if key not in values:
            continue
        entries = values[key]
        if not isinstance(entries, list) or not 1 <= len(entries) <= 4:
            raise ValueError('one to four entries required')
        if not all(isinstance(item, str) for item in entries) or len(set(entries)) != len(entries):
            raise ValueError('distinct string entries required')
        for entry in entries:
            if key == 'bootstrap_dns':
                match = re.fullmatch(r'https://([0-9.]+)/dns-query', entry)
                if not match:
                    raise ValueError('HTTPS IPv4 DoH endpoint required')
                entry = match[1]
            address = ipaddress.ip_address(entry)
            if address.version != 4 or not address.is_global or address.is_multicast:
                raise ValueError('public unicast IPv4 required')
    if 'subscription_path' in values:
        if not isinstance(values['subscription_path'], str) or not re.fullmatch(
                r'/s/[a-f0-9]{64}/client.yaml', values['subscription_path']):
            raise ValueError('random subscription path required')
    return values


def configs(values):
    v = validate(values)
    domain, path = v['domain'], v['ws_path']
    server = {
        'log': {'loglevel': 'warning'},
        'inbounds': [{'tag': 'cdn-in', 'listen': '127.0.0.1', 'port': v['xray_port'],
                      'protocol': 'vmess', 'settings': {'clients': [{'id': v['uuid'], 'alterId': 0}]},
                      'streamSettings': {'network': 'ws', 'security': 'none', 'wsSettings': {'path': path}}}],
        'outbounds': [
            {'tag': 'warp', 'protocol': 'socks', 'settings': {'servers': [{'address': '127.0.0.1', 'port': v['warp_port']}]}},
            {'tag': 'blocked', 'protocol': 'blackhole', 'settings': {}}],
        'routing': {'domainStrategy': 'AsIs', 'rules': [
            {'type': 'field', 'network': 'udp', 'outboundTag': 'blocked'},
            {'type': 'field', 'network': 'tcp', 'outboundTag': 'warp'}]}}
    client = {
        'mixed-port': 17890, 'allow-lan': False, 'bind-address': '127.0.0.1',
        'mode': 'rule', 'log-level': 'warning', 'ipv6': False,
        'tun': {'enable': False},
        'dns': {'enable': True, 'listen': '127.0.0.1:17853', 'ipv6': False,
                'enhanced-mode': 'fake-ip', 'fake-ip-range': '198.18.0.1/16',
                'respect-rules': True,
                'proxy-server-nameserver': v.get('bootstrap_dns', ['https://1.1.1.1/dns-query']),
                'nameserver': ['https://1.1.1.1/dns-query#SILICON']},
        'proxies': [{'name': 'SILICON-CDN-WARP', 'type': 'vmess', 'server': domain,
                     'port': 443, 'uuid': v['uuid'], 'alterId': 0, 'cipher': 'auto',
                     'udp': False, 'tls': True, 'skip-cert-verify': False,
                     'servername': domain, 'network': 'ws',
                     'ws-opts': {'path': path, 'headers': {'Host': domain}}}],
        'proxy-groups': [{'name': 'SILICON', 'type': 'select', 'proxies': ['SILICON-CDN-WARP']}],
        'rules': ['NETWORK,udp,REJECT', 'MATCH,SILICON']}
    if 'cdn_addresses' in v:
        base = client['proxies'][0]
        client['proxies'] = [dict(base, name='SILICON-CDN-WARP-' + chr(65 + i), server=address)
                             for i, address in enumerate(v['cdn_addresses'])]
        group = client['proxy-groups'][0]
        group['proxies'] = [node['name'] for node in client['proxies']]
        if len(client['proxies']) > 1:
            group.update(type='fallback', url='https://www.gstatic.com/generate_204', interval=60)
    caddy = {
        'admin': {'disabled': True},
        'apps': {
            'tls': {'certificates': {'load_files': [
                {'certificate': '/etc/crossborder-silicon/tls/fullchain.pem',
                 'key': '/etc/crossborder-silicon/tls/privkey.pem'}]}},
            'http': {'servers': {'silicon': {
                'listen': [':443'], 'protocols': ['h1', 'h2'],
                'automatic_https': {'disable': True}, 'tls_connection_policies': [{}],
                'routes': [
                    {'match': [{'host': [domain], 'path': [path],
                                'header': {'Upgrade': ['websocket']}}],
                     'handle': [{'handler': 'reverse_proxy', 'upstreams': [
                         {'dial': '127.0.0.1:' + str(v['xray_port'])}]}], 'terminal': True},
                    {'handle': [{'handler': 'static_response', 'status_code': 404}]}]}}}}}
    if 'subscription_path' in v:
        routes = caddy['apps']['http']['servers']['silicon']['routes']
        routes.insert(1, {
            'match': [{'host': [domain], 'path': [v['subscription_path']], 'method': ['GET', 'HEAD']}],
            'handle': [
                {'handler': 'headers', 'response': {'set': {
                    'Cache-Control': ['private, no-store, max-age=0'],
                    'Content-Type': ['text/yaml; charset=utf-8'],
                    'X-Content-Type-Options': ['nosniff'],
                    'Referrer-Policy': ['no-referrer'],
                    'Profile-Update-Interval': ['6']}}},
                {'handler': 'rewrite', 'uri': '/current.yaml'},
                {'handler': 'file_server', 'root': '/var/lib/crossborder-subscription'}],
            'terminal': True})
    return {'xray.json': json.dumps(server, indent=2) + '\n',
            'caddy.json': json.dumps(caddy, indent=2) + '\n',
            'tunnel-client.yaml': yaml_text(client)}


def read_values(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('symlink input')
    if os.name == 'posix' and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('private input required')
    return validate(json.loads(path.read_text(encoding='utf-8-sig')))


def export(values_path, output):
    bundle = configs(read_values(values_path))
    root = Path(output)
    # Exclusive directory creation preserves prior delivery and its UUID.
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, data in bundle.items():
        with os.fdopen(os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                       'w', encoding='utf-8', newline='\n') as stream:
            stream.write(data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--values', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    try:
        export(args.values, args.output)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print(json.dumps({'success': False, 'stage': 'render', 'error': 'Check private input, ports and destination; values omitted.'}))
        return 2
    print(json.dumps({'success': True, 'stage': 'render', 'native_validation': 'pending', 'deployment': 'not_started'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
