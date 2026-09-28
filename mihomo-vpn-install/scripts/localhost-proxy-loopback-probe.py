#!/usr/bin/env python3
"""Compare a read-only loopback health endpoint with and without environment proxies."""
import argparse
import json
import re
from urllib import error, request


class PrivateParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, 'Invalid arguments; use --help. Values omitted for privacy.\n')


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_status(opener, url):
    try:
        with opener.open(url, timeout=3) as response:
            return response.status
    except error.HTTPError as exc:
        code = exc.code
        exc.close()
        return code
    except (OSError, ValueError):
        return 0


def main(argv=None):
    parser = PrivateParser(prog='localhost-proxy-loopback-probe.py', description=__doc__, allow_abbrev=False)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--path', default='/health', help='Known read-only path, no query, fragment or credentials')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535 or not re.fullmatch(r'/[A-Za-z0-9_/-]*', args.path):
        parser.error('invalid endpoint')
    url = 'http://127.0.0.1:' + str(args.port) + args.path
    direct = fetch_status(request.build_opener(request.ProxyHandler({}), NoRedirect()), url)
    environmental = fetch_status(request.build_opener(request.ProxyHandler(), NoRedirect()), url)
    if direct == 200 and environmental == 200:
        verdict, code = 'BOTH_REACHABLE', 0
    elif direct == 200:
        verdict, code = 'ENVIRONMENT_PATH_DIFFERS', 1
    else:
        verdict, code = 'CHECK_LOCAL_SERVICE', 2
    print(json.dumps({'direct_http': direct, 'environment_http': environmental, 'verdict': verdict}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
