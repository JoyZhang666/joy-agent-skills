"""Parse a fully synthetic cn-direct delivery with the pinned official Mihomo core.

Run in the CI network namespace. No live endpoints or production values used.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cdn


def check(core):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        data = {}
        for name, content in [('domain', '+.domestic.example.com\n'), ('ip', '203.0.113.0/24\n')]:
            path = root / (name + '.list')
            path.write_bytes(content.encode())
            data[name] = {'path': str(path), 'sha256': hashlib.sha256(content.encode()).hexdigest()}
        values = dict(domain='edge.example.com', uuid='11111111-1111-4111-8111-111111111111',
                      ws_path='/' + 'a' * 32, xray_port=18443, warp_port=40000,
                      routing_profile='cn-direct', routing_data=data,
                      cdn_addresses=['104.16.0.1', '104.17.0.1'])
        config = root / 'client.yaml'
        config.write_text(cdn.configs(values)['tunnel-client.yaml'], encoding='utf-8')
        subprocess.run([str(core), '-t', '-d', str(root), '-f', str(config)], check=True, timeout=30)
    print('Synthetic cn-direct YAML parsed by pinned Mihomo; no live application claim.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', required=True, type=Path)
    args = parser.parse_args()
    check(args.artifacts / 'mihomo')
