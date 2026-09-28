#!/usr/bin/env python3
"""Preview cleanup in one dedicated mihomo-probe-* directory. Never kill processes."""
import argparse
import json
import os
import re
from pathlib import Path


class PrivateParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, 'Invalid arguments; use --help. Values omitted for privacy.\n')


def is_link(path):
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def checked_directory(directory):
    directory = Path(os.path.abspath(directory))
    for part in [directory, *directory.parents]:
        if is_link(part):
            raise ValueError('links and reparse points are not allowed')
    if not directory.is_dir() or not directory.name.startswith('mihomo-probe-'):
        raise ValueError('a dedicated directory is required')
    if os.name == 'posix' and directory.stat().st_uid != os.getuid():
        raise ValueError('directory must belong to current user')
    return directory.resolve(strict=True)


def candidates(directory):
    found = []
    for item in sorted(directory.iterdir()):
        if re.fullmatch(r'ss_cfg_[A-Za-z0-9_-]+\.json|ss_test_config\.json', item.name):
            if is_link(item) or not item.is_file():
                raise ValueError('candidate is not a regular file')
            if item.resolve(strict=True).parent != directory:
                raise ValueError('candidate escaped the directory')
            if os.name == 'posix' and item.stat().st_uid != os.getuid():
                raise ValueError('candidate must belong to current user')
            found.append(item)
    return found


def identity(path):
    info = path.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def main(argv=None):
    parser = PrivateParser(prog='ss-probe-cleanup.py', description=__doc__, allow_abbrev=False)
    parser.add_argument('--directory', required=True, type=Path, help='Explicit dedicated directory named mihomo-probe-*')
    parser.add_argument('--apply', action='store_true', help='Delete matching JSON only after verifying ownership and stopping its processes')
    args = parser.parse_args(argv)
    deleted = 0
    try:
        directory = checked_directory(args.directory)
        directory_id = identity(directory)[:2]
        items = candidates(directory)
        snapshot = [(p, identity(p)) for p in items]
        if args.apply:
            for item, expected in snapshot:
                current_dir = checked_directory(args.directory)
                if current_dir != directory or identity(directory)[:2] != directory_id:
                    raise ValueError('directory changed')
                if is_link(item) or identity(item) != expected:
                    raise ValueError('candidate changed')
                item.unlink()
                deleted += 1
        print(json.dumps({'mode': 'apply' if args.apply else 'preview', 'matching_files': len(items), 'deleted': deleted}))
        return 0
    except (OSError, ValueError):
        print(json.dumps({'error': 'Cleanup stopped; private details omitted', 'deleted': deleted}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
