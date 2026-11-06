"""Real loopback-only HY2 TLS tests. Run explicitly on an isolated Linux runner.

Requires OpenSSL and the fixed binaries from fetch_native.py. No TUN, controller,
system proxy, public listeners, production credentials or external test requests.
"""
import argparse
import contextlib
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import render


def run(argv):
    subprocess.run(argv, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE, timeout=30)


def port(kind=socket.SOCK_STREAM):
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@contextlib.contextmanager
def process(argv, log):
    with log.open('wb') as stream:
        child = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT)
        try:
            yield child
        finally:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


def wait_listener(number, child):
    for _ in range(100):
        if child.poll() is not None:
            raise RuntimeError('test core exited before listening')
        try:
            with socket.create_connection(('127.0.0.1', number), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError('test core did not listen')


class Target(BaseHTTPRequestHandler):
    def do_GET(self):
        data = b'hy2-pinned-loopback-proof'
        self.send_response(200)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def integration(artifacts):
    binaries = {name: str((Path(artifacts) / name).resolve()) for name in ('hysteria', 'mihomo')}
    results = {}
    with tempfile.TemporaryDirectory(prefix='hy2-pinned-test-') as directory:
        root = Path(directory)
        pins = []
        for name in ('original', 'replacement'):
            run(['openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt',
                 'ec_paramgen_curve:P-256', '-nodes', '-days', '1', '-subj', '/CN=tunnel.invalid',
                 '-addext', 'subjectAltName=DNS:tunnel.invalid',
                 '-keyout', str(root / (name + '.key')), '-out', str(root / (name + '.crt'))])
            der = ssl.PEM_cert_to_DER_cert((root / (name + '.crt')).read_text())
            pins.append(hashlib.sha256(der).hexdigest())
        udp_port = port(socket.SOCK_DGRAM)
        values = {'SERVER_HOST': '127.0.0.1', 'HY2_UDP_PORT': udp_port,
                  'HY2_PASSWORD': 'synthetic-loopback-auth', 'TLS_CERT_SHA256': pins[0],
                  'TLS_CERT_PATH': str(root / 'original.crt'), 'TLS_KEY_PATH': str(root / 'original.key')}
        values_path = root / 'values.json'
        values_path.write_text(json.dumps(values))
        values_path.chmod(0o600)
        client_path = root / 'client.json'
        render.render(ROOT / 'examples/client-hy2-pinned.template.json', values_path, client_path)
        # Exercise actual generated YAML syntax with the pinned native core as well.
        yaml_path = root / 'client.yaml'
        render.render(ROOT / 'examples/client-hy2-pinned.template.json', values_path, yaml_path)
        run([binaries['mihomo'], '-t', '-d', str(root), '-f', str(yaml_path)])
        results['yaml_native_parse'] = True
        base = json.loads(client_path.read_text())
        # Force even the loopback HTTP target through HY2; otherwise the template's
        # management-loopback DIRECT exception would make the negative tests invalid.
        base['rules'] = ['MATCH,SELECT']
        base['log-level'] = 'warning'
        server_path = root / 'server.json'
        render.render(ROOT / 'examples/server-hysteria2.template.json', values_path, server_path)
        server = json.loads(server_path.read_text())
        server['listen'] = '127.0.0.1:' + str(udp_port)
        target = ThreadingHTTPServer(('127.0.0.1', 0), Target)
        thread = threading.Thread(target=target.serve_forever, daemon=True)
        thread.start()
        try:
            cases = [('correct_pin', pins[0], 'original', True),
                     ('wrong_pin', '00' * 32, 'original', False),
                     ('missing_pin', None, 'original', False),
                     ('replaced_certificate', pins[0], 'replacement', False),
                     ('rotated_pin', pins[1], 'replacement', True)]
            for name, pin, certificate, expected in cases:
                server['tls'].update(cert=str(root / (certificate + '.crt')),
                                     key=str(root / (certificate + '.key')))
                server_path.write_text(json.dumps(server))
                client = json.loads(json.dumps(base))
                client['mixed-port'] = port()
                if pin is None:
                    del client['proxies'][0]['fingerprint']
                else:
                    client['proxies'][0]['fingerprint'] = pin
                path = root / (name + '.json')
                path.write_text(json.dumps(client))
                log = root / (name + '.log')
                with process([binaries['hysteria'], 'server', '-c', str(server_path)], root / 'server.log') as upstream:
                    time.sleep(0.3)
                    if upstream.poll() is not None:
                        raise RuntimeError('HY2 server startup failed')
                    with process([binaries['mihomo'], '-d', str(root), '-f', str(path)], log) as core:
                        wait_listener(client['mixed-port'], core)
                        success = False
                        connection = http.client.HTTPConnection('127.0.0.1', client['mixed-port'], timeout=8)
                        try:
                            connection.request('GET', 'http://127.0.0.1:' + str(target.server_port) + '/proof')
                            response = connection.getresponse()
                            success = response.status == 200 and response.read() == b'hy2-pinned-loopback-proof'
                        except (OSError, http.client.HTTPException):
                            pass
                        finally:
                            connection.close()
                        if success != expected:
                            raise AssertionError(name + ': unexpected request result')
                        if not expected:
                            diagnostic = log.read_text(errors='replace').lower()
                            marker = 'x509' if pin is None else 'certificate fingerprints do not match'
                            if marker not in diagnostic:
                                raise AssertionError(name + ': no certificate rejection evidence')
                        results[name] = True
        finally:
            target.shutdown()
            target.server_close()
            thread.join(timeout=5)
    print(json.dumps({'success': True, 'checks': results, 'scope': 'loopback TLS; no public route or GUI claim'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', required=True)
    integration(parser.parse_args().artifacts)
