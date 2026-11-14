"""Domestic access profile; embedded, pinned data with no client download dependency."""
import hashlib
import ipaddress
import re
from pathlib import Path

PROFILE = 'cn-direct'
DOMESTIC = ['baidu.com', 'bdstatic.com', 'bdimg.com', 'bcebos.com',
            'oray.com', 'oray.net', 'orayimg.com', 'sunlogin.net',
            'qq.com', 'weixin.com', 'wechat.com', 'qpic.cn', 'qlogo.cn']
OVERSEAS = ['google.com', 'googleapis.com', 'gstatic.com', 'googlevideo.com',
            'youtube.com', 'ytimg.com', 'youtu.be', 'openai.com', 'chatgpt.com',
            'oaistatic.com', 'oaiusercontent.com', 'anthropic.com', 'claude.ai',
            'cloudflare.com', 'googleapis.cn', 'xn--ngstr-lra8j.com']


def snapshot(spec, kind):
    """Load operator-reviewed local data; no network or bundled third-party data."""
    if not isinstance(spec, dict) or set(spec) != {'path', 'sha256'}:
        raise ValueError('routing snapshot path and SHA-256 required')
    path = Path(spec['path'])
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError('absolute regular snapshot file required')
    if not isinstance(spec['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', spec['sha256']):
        raise ValueError('routing snapshot SHA-256 required')
    with path.open('rb') as stream:
        raw = stream.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError('routing snapshot too large')
    if hashlib.sha256(raw).hexdigest() != spec['sha256']:
        raise ValueError('routing snapshot integrity mismatch')
    lines = [line.strip() for line in raw.decode('utf-8').splitlines()
             if line.strip() and not line.startswith('#')]
    if not lines or len(lines) > 200_000:
        raise ValueError('routing snapshot line count invalid')
    if kind == 'ip':
        for line in lines:
            if ipaddress.ip_network(line).prefixlen == 0:
                raise ValueError('catch-all direct route forbidden')
    else:
        domain = r'(?:\+\.)?(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}'
        if any(len(line) > 255 or not re.fullmatch(domain, line) for line in lines):
            raise ValueError('invalid domain snapshot')
    return lines


def apply(client, values):
    data = values['routing_data']
    if not isinstance(data, dict) or set(data) != {'domain', 'ip'}:
        raise ValueError('domain and IP snapshots required')
    processes = values.get('direct_processes', [])
    if (not isinstance(processes, list) or len(processes) > 32 or
            any(not isinstance(p, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', p)
                for p in processes)):
        raise ValueError('verified process basenames required')
    client['rule-providers'] = {
        'cn-domain': {'type': 'inline', 'behavior': 'domain', 'payload': snapshot(data['domain'], 'domain')},
        'cn-ip': {'type': 'inline', 'behavior': 'ipcidr', 'payload': snapshot(data['ip'], 'ip')},
        'overseas-domain': {'type': 'inline', 'behavior': 'domain',
                            'payload': ['+.' + d for d in OVERSEAS]},
    }
    # Add process bypasses only after observing the executable on the target device.
    rules = ['PROCESS-NAME,' + p + ',DIRECT' for p in processes]
    for net in ['127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
                '169.254.0.0/16', '100.64.0.0/10']:
        rules.append('IP-CIDR,' + net + ',DIRECT,no-resolve')
    for net in ['::1/128', 'fc00::/7', 'fe80::/10']:
        rules.append('IP-CIDR6,' + net + ',DIRECT,no-resolve')
    rules += ['AND,((NETWORK,udp),(RULE-SET,overseas-domain)),REJECT',
              'AND,((NETWORK,tcp),(RULE-SET,overseas-domain)),SILICON']
    rules += ['DOMAIN-SUFFIX,' + d + ',DIRECT' for d in DOMESTIC]
    rules += ['RULE-SET,cn-domain,DIRECT',
              'NETWORK,udp,REJECT', 'MATCH,SILICON']
    client['rules'] = rules
    local_dns = ['https://223.5.5.5/dns-query#DIRECT', 'https://223.6.6.6/dns-query#DIRECT']
    remote_dns = ['https://1.1.1.1/dns-query#SILICON']
    client['dns'].update({
        'default-nameserver': ['223.5.5.5', '223.6.6.6'],
        'proxy-server-nameserver': local_dns,
        'direct-nameserver': local_dns,
        'direct-nameserver-follow-policy': False,
        'nameserver': remote_dns,
        'nameserver-policy': {'+.googleapis.cn': remote_dns,
                              '+.xn--ngstr-lra8j.com': remote_dns,
                              'rule-set:cn-domain': local_dns,
                              'rule-set:overseas-domain': remote_dns,
                              **{'+.' + d: local_dns for d in DOMESTIC}},
        'fake-ip-filter': ['*.lan', 'localhost', 'rule-set:cn-domain'] + ['+.' + d for d in DOMESTIC],
    })
    return client
