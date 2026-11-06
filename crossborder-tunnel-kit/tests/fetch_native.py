"""Explicit Linux amd64 test dependency download; fixed upstream assets, no execution."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import urllib.request


def fetch(output):
    pins = json.loads(Path(__file__).with_name('native-assets.json').read_text())
    root = Path(output)
    root.mkdir(mode=0o700, exist_ok=False)
    for name, pin in pins.items():
        with urllib.request.urlopen(pin['url'], timeout=60) as response:
            data = response.read(100 * 1024 * 1024 + 1)
        if len(data) > 100 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != pin['sha256']:
            raise ValueError('native asset checksum or size mismatch')
        if pin['url'].endswith('.gz'):
            data = gzip.decompress(data)
        target = root / name
        target.write_bytes(data)
        target.chmod(0o700)
    print('Verified two fixed native test dependencies; not started.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    fetch(parser.parse_args().output)
