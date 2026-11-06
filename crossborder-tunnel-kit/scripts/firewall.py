#!/usr/bin/env python3
"""Build an owned nftables table from reviewed Cloudflare CIDR lists."""
import argparse
import ipaddress
from pathlib import Path


def rules(v4, v6):
    groups = []
    for version, text in [(4, v4), (6, v6)]:
        networks = [ipaddress.ip_network(line.strip()) for line in text.splitlines() if line.strip()]
        if not networks or any(n.version != version or n.prefixlen == 0 for n in networks):
            raise ValueError('invalid network list')
        groups.append(', '.join(str(n) for n in networks))
    return '''# Only this named table is replaced, atomically in one nft transaction.
add table inet crossborder_silicon
delete table inet crossborder_silicon
table inet crossborder_silicon {
 set cf4 { type ipv4_addr; flags interval; elements = { %s }; }
 set cf6 { type ipv6_addr; flags interval; elements = { %s }; }
 chain ingress {
  type filter hook input priority -5; policy accept;
  iifname "lo" tcp dport 443 accept
  tcp dport 443 ip saddr @cf4 counter accept
  tcp dport 443 ip6 saddr @cf6 counter accept
  tcp dport 443 counter drop
  udp dport 443 counter drop
 }
}
''' % tuple(groups)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ipv4', required=True)
    p.add_argument('--ipv6', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    data = rules(Path(a.ipv4).read_text(), Path(a.ipv6).read_text())
    with open(a.output, 'x', encoding='utf-8') as stream:
        stream.write(data)
