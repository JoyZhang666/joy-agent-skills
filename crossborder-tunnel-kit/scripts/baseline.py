#!/usr/bin/env python3
"""Local inventory only unless --external-ip is explicitly selected."""
import argparse
import json
import os
import platform
import shutil
import urllib.request


def baseline(environ=None):
    environ = os.environ if environ is None else environ
    names = ("http_proxy", "https_proxy", "all_proxy", "no_proxy")
    return {"system": platform.system(), "architecture": platform.machine(),
            "proxy_env_configured": {name: bool(environ.get(name) or environ.get(name.upper())) for name in names},
            "tools_available": {name: shutil.which(name) is not None for name in ("systemctl", "dig", "ip", "ss")},
            "network_requests": 0,
            "scope": "local metadata only; no routes, DNS, interfaces or proxy settings changed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-ip", action="store_true", help="Contact Cloudflare through current proxy environment")
    args = parser.parse_args()
    result = baseline()
    if args.external_ip:
        import ipaddress
        try:
            with urllib.request.urlopen("https://www.cloudflare.com/cdn-cgi/trace", timeout=15) as response:
                pairs = dict(line.split("=", 1) for line in response.read(8192).decode().splitlines() if "=" in line)
            result["external_ip"] = str(ipaddress.ip_address(pairs["ip"]))
            result["network_requests"] = 1
            result["scope"] = "one HTTP request; reports this request's exit only; output is private"
        except (OSError, ValueError, KeyError):
            print('{"status":"ERROR","reason":"external query failed"}')
            return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
