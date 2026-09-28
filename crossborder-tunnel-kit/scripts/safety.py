#!/usr/bin/env python3
"""Linux-only, batch-scoped rollback and systemd timer control. Default is review."""
import argparse
import hashlib
import ipaddress
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

CONFIG = Path("/etc/crossborder-tunnel-kit")
BATCHES = Path("/var/lib/crossborder-tunnel-kit/batches")
SERVICES = {"hysteria.json": "hysteria-server.service", "xray.json": "xray.service",
            "sing-box.json": "sing-box-warp.service"}


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=40).stdout.strip()


def trusted(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("absolute path required")
    for item in (path, *path.parents):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("untrusted owner, writable path or symlink")


def root_guard():
    if not sys.platform.startswith("linux") or os.geteuid() != 0:
        raise ValueError("apply requires Linux root")


def load_manifest(path, secure=False):
    path = Path(path)
    if secure:
        trusted(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    batch = data["batch"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", batch):
        raise ValueError("invalid batch")
    if secure and path != BATCHES / batch / "rollback.json":
        raise ValueError("manifest outside batch")
    restore = data["restore"]
    stop_new = data["stop_new_services"]
    if not isinstance(restore, dict) or not isinstance(stop_new, list) or not (restore or stop_new):
        raise ValueError("empty or invalid plan")
    if set(restore) - SERVICES.keys() or set(stop_new) - set(SERVICES.values()):
        raise ValueError("unknown target")
    if set(stop_new) & {SERVICES[name] for name in restore}:
        raise ValueError("cannot stop and restore the same service")
    for name, expected in restore.items():
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("missing backup digest")
        backup = path.parent / name
        if secure:
            trusted(backup)
            trusted(CONFIG)
            target = CONFIG / name
            if target.exists() or target.is_symlink():
                trusted(target)
        if hashlib.sha256(backup.read_bytes()).hexdigest() != expected:
            raise ValueError("backup digest mismatch")
    domain = data["dns_name"]
    if not isinstance(domain, str) or len(domain) > 253 or "." not in domain or not all(
        re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
        for label in domain.rstrip(".").split(".")
    ):
        raise ValueError("invalid DNS test name")
    answers = data["dns_expected_ipv4"]
    if not isinstance(answers, list) or not answers:
        raise ValueError("expected DNS answers required")
    for answer in answers:
        if not isinstance(answer, str) or ipaddress.ip_address(answer).version != 4:
            raise ValueError("expected IPv4 answer")
    return data


def dns_ok(output, expected):
    # dig exits zero for NXDOMAIN. Require status and actual A answer records.
    if "status: NOERROR," not in output:
        return False
    found = set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 5 and parts[2:4] == ["IN", "A"]:
            found.add(parts[4])
    return bool(found.intersection(expected))


def rollback(path):
    root_guard()
    data = load_manifest(path, secure=True)  # Preflight every backup before any mutation.
    import grp
    group = grp.getgrnam("tunnel").gr_gid if data["restore"] else None
    for service in data["stop_new_services"]:
        run(["systemctl", "disable", "--now", service])
        if run(["systemctl", "show", service, "--property=ActiveState", "--value"]) != "inactive":
            raise ValueError("new service still running")
        if run(["systemctl", "show", service, "--property=UnitFileState", "--value"]) not in ("disabled", "static"):
            raise ValueError("new service still enabled")
    for name, expected in data["restore"].items():
        target = CONFIG / name
        temporary = CONFIG / ("." + name + ".rollback-" + data["batch"])
        raw = (Path(path).parent / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("backup changed after preflight")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.chown(temporary, 0, group)
            os.chmod(temporary, 0o640)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError("restore readback mismatch")
        service = SERVICES[name]
        run(["systemctl", "restart", service])
        if run(["systemctl", "show", service, "--property=ActiveState", "--value"]) != "active":
            raise ValueError("restored service inactive")
    answer = run(["dig", "+time=3", "+tries=1", "+noall", "+comments", "+answer", data["dns_name"], "A"])
    if not dns_ok(answer, data["dns_expected_ipv4"]):
        raise ValueError("DNS acceptance failed")


def unit_name(name):
    if not re.fullmatch(r"tunnel-rollback-[a-z0-9][a-z0-9-]{0,47}", name):
        raise ValueError("invalid timer unit")
    return name


def arm(path, name, minutes):
    root_guard()
    unit_name(name)
    load_manifest(path, secure=True)
    if not 1 <= minutes <= 60:
        raise ValueError("timer must be 1..60 minutes")
    script = Path(__file__).absolute()
    trusted(script)
    trusted(Path(sys.executable).resolve())
    run(["systemd-run", "--unit=" + name, "--on-active=" + str(minutes) + "m",
         "--timer-property=AccuracySec=1s", "--property=Type=exec",
         str(Path(sys.executable).resolve()), str(script), "rollback", "--manifest", str(Path(path).absolute()), "--apply"])
    if run(["systemctl", "show", name + ".timer", "--property=ActiveState", "--value"]) != "active":
        raise ValueError("timer not armed")


def disarm(name):
    root_guard()
    unit_name(name)
    # Freeze the timer first; never interrupt an already executing rollback.
    run(["systemctl", "stop", name + ".timer"])
    if run(["systemctl", "show", name + ".timer", "--property=ActiveState", "--value"]) != "inactive":
        raise ValueError("timer cancellation failed")
    output = run(["systemctl", "show", name + ".service",
                  "--property=ActiveState,Result,ExecMainStartTimestampMonotonic,Job"])
    snapshot = dict(line.split("=", 1) for line in output.splitlines() if "=" in line)
    if snapshot.get("ActiveState") != "inactive":
        raise ValueError("rollback started or failed; inspect service, do not claim cancellation")
    if snapshot.get("Result") != "success" or snapshot.get("ExecMainStartTimestampMonotonic") != "0":
        raise ValueError("rollback already executed; cancellation is not a success acceptance")
    if snapshot.get("Job") != "0":
        raise ValueError("rollback job queued or unrecognized state; inspect before proceeding")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("arm", "disarm", "rollback"))
    parser.add_argument("--manifest")
    parser.add_argument("--unit")
    parser.add_argument("--minutes", type=int, default=15)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if args.action in ("arm", "rollback"):
            if not args.manifest:
                raise ValueError("manifest required")
            data = load_manifest(args.manifest)
        if args.action in ("arm", "disarm"):
            unit_name(args.unit or "")
        if not args.apply:
            print("REVIEW ONLY: no service, timer or configuration changed")
        elif args.action == "arm":
            arm(args.manifest, args.unit, args.minutes)
            print("Timer armed and read back")
        elif args.action == "disarm":
            disarm(args.unit)
            print("Timer inactive; rollback service has not executed")
        else:
            rollback(args.manifest)
            print("Scoped rollback completed; service, file and DNS checks passed")
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print("ERROR: operation incomplete; inspect protected local state; no secret values emitted")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
