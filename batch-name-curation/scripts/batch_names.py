#!/usr/bin/env python3
"""Windows-local, approval-bound file and directory naming. Standard library only."""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import unicodedata

VERSION = 2
CSV_FIELDS = ['old_path', 'new_path', 'kind', 'size', 'sha256', 'changes', 'notes']
INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'} | {
    prefix + digit for prefix in ('COM', 'LPT') for digit in '123456789¹²³'
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def hash_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def no_links(path):
    for part in (path, *path.parents):
        if os.path.lexists(part):
            s = part.lstat()
            require(not stat.S_ISLNK(s.st_mode) and not (getattr(s, 'st_file_attributes', 0) & 1024),
                    f'symlink/reparse point rejected: {part}')


def absolute_root(value):
    path = Path(os.path.abspath(value))
    no_links(path)
    require(path.is_dir() and path.parent != path, 'target must be an existing non-volume-root directory')
    return path


def name_check(name):
    require(isinstance(name, str) and name not in ('', '.', '..'), 'empty or relative name')
    require(not INVALID.search(name), f'Windows-invalid name: {name!r}')
    require(not name.endswith((' ', '.')), f'trailing space/dot: {name!r}')
    require(name.split('.')[0].upper() not in RESERVED, f'reserved device name: {name!r}')
    require(len(name.encode('utf-16-le')) // 2 <= 255, f'component too long: {name!r}')


def relative_check(value):
    require(isinstance(value, str) and value and '\\' not in value, 'expected slash-delimited relative path')
    p = PurePosixPath(value)
    require(not p.is_absolute() and p.as_posix() == value, 'noncanonical relative path')
    for part in p.parts:
        name_check(part)
    return p


def extension(name):
    for suffix in ('.tar.gz', '.tar.bz2', '.tar.xz'):
        if name.lower().endswith(suffix):
            return name[-len(suffix):]
    return PurePosixPath(name).suffix


def facts(name, kind):
    ext = extension(name) if kind == 'file' else ''
    stem = name[:-len(ext)] if ext else name
    notes = []
    if len(stem) > (60 if kind == 'file' else 40):
        notes.append('long-name-review; do not truncate automatically')
    if any(unicodedata.category(c) in ('Cc', 'Cf', 'Co') or c == '\ufffd' for c in stem):
        notes.append('unicode-review; preserve until exact edit is approved')
    if re.search(r'https?://|www\.|(?:QQ|微信|wx|wechat)\s*[:：号]?\s*[A-Za-z0-9_-]{5,}|持续更新|关注|下载地址', stem, re.I):
        notes.append('possible-promotion; context required')
    number = re.match(r'^\d+', name)
    return {'extension': ext, 'name_length': len(name),
            'source_number': number.group() if number else '', 'notes': notes}


def scan(root, tree):
    no_links(root)
    result = []
    def visit(folder):
        for path in sorted(folder.iterdir(), key=lambda p: (p.name.casefold(), p.name)):
            no_links(path)
            before = path.stat()
            require(stat.S_ISREG(before.st_mode) or stat.S_ISDIR(before.st_mode), f'unsupported item: {path}')
            kind = 'directory' if path.is_dir() else 'file'
            row = {'path': path.relative_to(root).as_posix(), 'kind': kind,
                   'size': before.st_size if kind == 'file' else None,
                   'sha256': hash_file(path) if kind == 'file' else None,
                   'mtime_ns': before.st_mtime_ns if kind == 'file' else None}
            after = path.stat()
            require(kind != 'file' or (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
                    f'changed during scan: {path}')
            row.update(facts(path.name, kind))
            result.append(row)
            if kind == 'directory' and tree:
                visit(path)
    visit(root)
    return result


def summary(rows):
    files = [r for r in rows if r['kind'] == 'file']
    groups = {}
    for row in files:
        groups.setdefault(row['sha256'], []).append(row['path'])
    nums = [int(r['source_number']) for r in files if r['source_number']]
    numbering = {}
    for row in files:
        if row['source_number']:
            parent = str(PurePosixPath(row['path']).parent)
            numbering.setdefault(parent, {}).setdefault(int(row['source_number']), []).append(row['path'])
    number_report = {}
    for parent, values in numbering.items():
        low, high = min(values), max(values)
        number_report[parent] = {'min': low, 'max': high,
                                 'duplicate_numbers': [v for v in values.values() if len(v) > 1],
                                 'missing_between_min_max': [n for n in range(low, high + 1) if n not in values] if high - low < 100000 else None}
    return {'files': len(files), 'directories': len(rows) - len(files),
            'total_bytes': sum(r['size'] for r in files), 'hashes_verified': len(files),
            'zero_byte_files': [r['path'] for r in files if r['size'] == 0],
            'duplicate_content': [g for g in groups.values() if len(g) > 1],
            'number_min': min(nums) if nums else None, 'number_max': max(nums) if nums else None,
            'numbering_by_parent': number_report}


def validate_rules(rules):
    require(isinstance(rules, list), 'rules must be an array')
    ids = set()
    for rule in rules:
        require(set(rule) == {'id', 'kind', 'match', 'replacement', 'target', 'reason'}, 'rule fields invalid')
        require(all(isinstance(v, str) for v in rule.values()), 'rule values must be strings')
        require(rule['id'] and rule['id'] not in ids and rule['match'] and rule['reason'].strip(), 'rule lacks unique id, match or reason')
        ids.add(rule['id'])
        require(rule['kind'] in ('suffix', 'literal', 'regex', 'exact'), 'unsupported rule kind')
        require(rule['target'] in ('file', 'directory', 'both'), 'unsupported rule target')
        if rule['kind'] == 'regex':
            re.compile(rule['match'])


def transform(name, kind, rules):
    ext = extension(name) if kind == 'file' else ''
    text = name[:-len(ext)] if ext else name
    changes = []
    for rule in rules:
        if rule['target'] not in (kind, 'both'):
            continue
        before = text
        match, replacement = rule['match'], rule['replacement']
        if rule['kind'] == 'suffix' and text.endswith(match):
            text = text[:-len(match)] + replacement
        elif rule['kind'] == 'literal':
            text = text.replace(match, replacement)
        elif rule['kind'] == 'regex':
            text = re.sub(match, replacement, text)
        elif rule['kind'] == 'exact' and text == match:
            text = replacement
        if text != before:
            spans = [{'old_start': a, 'old_end': b, 'removed': before[a:b], 'inserted': text[c:d]}
                     for op, a, b, c, d in difflib.SequenceMatcher(None, before, text, autojunk=False).get_opcodes()
                     if op != 'equal']
            changes.append({'rule_id': rule['id'], 'reason': rule['reason'], 'before': before, 'after': text, 'spans': spans})
    require(bool(text.strip()), f'rules erase the entire name: {name!r}')
    return text + ext, changes


def make_plan(root, baseline, rules, scope, root_name=None, allow_number_change=False, check_live_root=True,
              schema_version=VERSION):
    require(type(schema_version) is int and schema_version in (1, VERSION), 'unsupported schema version')
    validate_rules(rules)
    require(set(scope) == {'recursive', 'files', 'directories'}, 'invalid scope')
    require(all(type(v) is bool for v in scope.values()), 'scope flags must be boolean')
    final_root = root.with_name(root_name) if root_name else root
    require(str(final_root) == str(root) or final_root != root, 'case-only root rename is unsupported')
    name_check(final_root.name)
    require(not check_live_root or final_root == root or not os.path.lexists(final_root), 'new root already exists')
    rows, own_names = [], {}
    for item in baseline:
        p = relative_check(item['path'])
        eligible = (scope['recursive'] or len(p.parts) == 1) and scope['files' if item['kind'] == 'file' else 'directories']
        new_name, changes = transform(p.name, item['kind'], rules) if eligible else (p.name, [])
        name_check(new_name)
        if not allow_number_change:
            require(facts(p.name, item['kind'])['source_number'] == facts(new_name, item['kind'])['source_number'],
                    f'source number change requires explicit plan option: {p}')
        if item['kind'] == 'file':
            require(extension(p.name) == extension(new_name), 'extension must be preserved exactly')
        own_names[item['path']] = new_name
        rows.append({'old_path': item['path'], 'new_path': '', 'new_name': new_name,
                     'kind': item['kind'], 'size': item['size'], 'sha256': item['sha256'],
                     'changes': changes, 'notes': facts(new_name, item['kind'])['notes']})
    for row in rows:
        parts = PurePosixPath(row['old_path']).parts
        row['new_path'] = '/'.join(own_names.get('/'.join(parts[:i+1]), part) for i, part in enumerate(parts))
        relative_check(row['new_path'])
        require(len(str(final_root / row['new_path']).encode('utf-16-le')) // 2 < 240, 'final path exceeds conservative 239 UTF-16-unit limit')
    old_paths = {r['old_path'].casefold() for r in rows}
    new_paths = {r['new_path'].casefold() for r in rows}
    require(len(old_paths) == len(rows) == len(new_paths), 'case-insensitive path collision')
    require(len({unicodedata.normalize('NFC', r['new_path']).casefold() for r in rows}) == len(rows),
            'Unicode-normalization collision; choose distinct names before execution')
    # Also check each unchanged-parent namespace: directory merges and cycles are unsupported.
    operations = []
    for row in sorted(rows, key=lambda r: (-len(PurePosixPath(r['old_path']).parts), r['old_path'])):
        old = row['old_path']
        new = str(PurePosixPath(old).with_name(row['new_name']))
        if old != new:
            require(new.casefold() not in old_paths, f'target overlaps existing item (including case-only rename): {new}')
            operations.append({'old': str(root / old), 'new': str(root / new)})
    if final_root != root:
        operations.append({'old': str(root), 'new': str(final_root)})
    payload = {'schema_version': schema_version, 'root': str(root), 'final_root': str(final_root),
               'scope': scope, 'tree': scope['recursive'] or scope['directories'] or bool(root_name),
               'root_name': root_name, 'allow_number_change': allow_number_change,
               'rules': rules, 'baseline': baseline, 'rows': rows, 'operations': operations,
               'summary': summary(baseline)}
    payload['plan_id'] = digest(payload)
    return payload


def csv_cell(value):
    if isinstance(value, str):
        stripped = value.lstrip()
        if (stripped.startswith(('=', '+', '-', '@', '＝', '＋', '－', '＠'))
                or any(unicodedata.category(c) in ('Cc', 'Cf') for c in value)):
            return '[text] ' + value
    return value


def csv_text(plan):
    stream = io.StringIO(newline='')
    legacy = plan['schema_version'] == 1
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS,
                            quoting=csv.QUOTE_MINIMAL if legacy else csv.QUOTE_ALL)
    writer.writeheader()
    for row in plan['rows']:
        out = {key: row[key] for key in CSV_FIELDS}
        out['changes'] = json.dumps(out['changes'], ensure_ascii=False, separators=(',', ':'))
        out['notes'] = json.dumps(out['notes'], ensure_ascii=False)
        if not legacy:
            out = {key: csv_cell(value) for key, value in out.items()}
        writer.writerow(out)
    return stream.getvalue()


def create_text(path, text, encoding='utf-8'):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding=encoding, newline='') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())


def outside(path, root):
    path = Path(os.path.abspath(path))
    no_links(path)
    require(path != root and root not in path.parents, 'reports/journals must be outside source tree')
    return path


def save_plan(plan, directory):
    root = Path(plan['root'])
    directory = outside(directory, root)
    outside(directory, Path(plan['final_root']))
    require(not directory.exists(), 'output directory already exists; use a fresh run path')
    directory.mkdir(parents=True)
    create_text(directory / 'plan.json', json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    create_text(directory / 'rename-manifest.csv', csv_text(plan), 'utf-8-sig')
    lines = ['# 批量命名审批预览', '', f"计划摘要：`{plan['plan_id']}`", '',
             f"目标：`{plan['root']}`", f"最终目标：`{plan['final_root']}`", '',
             f"文件 {plan['summary']['files']}；目录 {plan['summary']['directories']}；实际改名操作 {len(plan['operations'])}。", '',
             '完整映射：[CSV](rename-manifest.csv)；执行依据：[JSON](plan.json)。', '',
             '格式 2 CSV 对危险文本添加 [text] 显示标记；准确原名以 JSON 为准。旧格式 CSV 请仅按文本查看。', '']
    for row in plan['rows']:
        lines.append('- ' + json.dumps(row['old_path'], ensure_ascii=False) + ' → ' + json.dumps(row['new_path'], ensure_ascii=False))
    create_text(directory / 'preview.md', '\n'.join(lines) + '\n')
    load_plan(directory / 'plan.json')


def load_plan(path):
    path = Path(os.path.abspath(path))
    csv_path = path.parent / 'rename-manifest.csv'
    for input_path in (path, csv_path):
        no_links(input_path)
        require(stat.S_ISREG(input_path.lstat().st_mode), 'plan and CSV must be regular files')
    plan = json.loads(path.read_text(encoding='utf-8'))
    expected = plan['plan_id']
    require(digest({k: v for k, v in plan.items() if k != 'plan_id'}) == expected, 'plan digest mismatch')
    require(type(plan['schema_version']) is int and plan['schema_version'] in (1, VERSION),
            'unsupported schema version')
    root = Path(plan['root'])
    require(root.is_absolute() and root.parent != root, 'invalid bound root')
    for input_path in (path, csv_path):
        outside(input_path, root)
        outside(input_path, Path(plan['final_root']))
    # Structural validation independent of current live names, including during rollback.
    rebuilt = make_plan(root, plan['baseline'], plan['rules'], plan['scope'],
                        plan['root_name'], plan['allow_number_change'], check_live_root=False,
                        schema_version=plan['schema_version'])
    require(rebuilt == plan, 'plan structure or derived mapping invalid')
    for row in plan['rows']:
        relative_check(row['old_path'])
        relative_check(row['new_path'])
    with csv_path.open(encoding='utf-8-sig', newline='') as f:
        require(f.read() == csv_text(plan), 'CSV differs from authoritative JSON')
    outside(path, root)
    outside(path, Path(plan['final_root']))
    return plan


def expected_state(plan, completed):
    root = Path(plan['root'])
    paths = {str(root / r['path']): r for r in plan['baseline']}
    for op in plan['operations'][:completed]:
        old, new = Path(op['old']), Path(op['new'])
        mapped = {}
        for value, row in paths.items():
            p = Path(value)
            mapped[str(new / p.relative_to(old)) if p == old or old in p.parents else value] = row
        paths = mapped
        if root == old:
            root = new
    return root, paths


def verify_state(plan, completed):
    root, expected = expected_state(plan, completed)
    current = scan(absolute_root(root), plan['tree'])
    actual = {str(root / r['path']): r for r in current}
    require(set(actual) == set(expected), 'file/directory set drift')
    for path, old in expected.items():
        new = actual[path]
        require(all(new[k] == old[k] for k in ('kind', 'size', 'sha256', 'mtime_ns')), f'content/metadata drift: {path}')
    return summary(current)


def event(stream, value):
    stream.write(json.dumps(value, ensure_ascii=False) + '\n')
    stream.flush()
    os.fsync(stream.fileno())


def rename_no_replace(old, new):
    require(os.name == 'nt', 'apply/rollback v1 supports Windows only')
    old, new = Path(old), Path(new)
    no_links(old)
    no_links(new.parent)
    require(not os.path.lexists(new), f'target exists: {new}')
    # Windows os.rename refuses an existing destination (no replace flag).
    os.rename(old, new)


def recover(plan, journal, execute=False):
    require(journal.is_file(), 'recovery requires existing journal')
    # A partial last line is not silently discarded: report for manual reconciliation.
    journal_text = journal.read_text(encoding='utf-8')
    require(journal_text.endswith('\n'), 'incomplete journal line; preserve state for review')
    events = [json.loads(line) for line in journal_text.splitlines()]
    require(events and events[0] == {'event': 'start', 'plan_id': plan['plan_id']}, 'journal/plan mismatch')
    done = 0
    pending = None
    for item in events[1:]:
        kind = item['event']
        if kind == 'intent':
            require(pending is None and item['index'] == done, 'invalid forward journal order')
            pending = ('forward', done)
        elif kind == 'done':
            require(pending == ('forward', done) and item['index'] == done, 'invalid completion record')
            done += 1
            pending = None
        elif kind == 'undo_intent':
            require(pending is None and done > 0 and item['index'] == done - 1, 'invalid reverse journal order')
            pending = ('reverse', done - 1)
        elif kind == 'undone':
            require(pending == ('reverse', done - 1) and item['index'] == done - 1, 'invalid reverse completion')
            done -= 1
            pending = None
        elif kind == 'cancelled_intent':
            require(pending == ('forward', done) and item['index'] == done, 'invalid cancelled intent')
            pending = None
        elif kind == 'cancelled_undo_intent':
            require(pending == ('reverse', done - 1) and item['index'] == done - 1, 'invalid cancelled reverse intent')
            pending = None
        elif kind in ('verified', 'restored', 'failure'):
            require(pending is None, 'unresolved journal intent')
        else:
            raise ValueError('unknown journal event')
    require(0 <= done <= len(plan['operations']), 'journal exceeds operation count')
    resolution = None
    if pending:
        direction, index = pending
        require(index < len(plan['operations']), 'journal intent out of range')
        op = plan['operations'][index]
        old, new = Path(op['old']), Path(op['new'])
        a, b = os.path.lexists(old), os.path.lexists(new)
        require(a != b, 'ambiguous interrupted operation; preserve state for review')
        if direction == 'forward':
            if b:
                done += 1
                resolution = {'event': 'done', 'index': index}
            else:
                resolution = {'event': 'cancelled_intent', 'index': index}
        elif a:
            done -= 1
            resolution = {'event': 'undone', 'index': index}
        else:
            resolution = {'event': 'cancelled_undo_intent', 'index': index}
    report = verify_state(plan, done)
    if not execute:
        return dict(report, quality_pass=True, mode='rollback-preview', completed_operations=done)
    with journal.open('a', encoding='utf-8', newline='') as stream:
        if resolution:
            event(stream, resolution)
        for index in range(done - 1, -1, -1):
            op = plan['operations'][index]
            event(stream, {'event': 'undo_intent', 'index': index})
            rename_no_replace(op['new'], op['old'])
            event(stream, {'event': 'undone', 'index': index})
        report = verify_state(plan, 0)
        event(stream, {'event': 'restored'})
    return dict(report, quality_pass=True, mode='rollback', restored_operations=done)


def apply_plan(plan, approved, journal, execute=False):
    require(approved == plan['plan_id'], 'explicit approved plan digest required')
    require(not journal.exists(), 'journal exists; verify/recover, do not re-apply')
    report = verify_state(plan, 0)
    # Rebuild mapping from bound baseline and rules; reject changed semantics independently.
    rebuilt = make_plan(Path(plan['root']), plan['baseline'], plan['rules'], plan['scope'],
                        plan['root_name'], plan['allow_number_change'],
                        schema_version=plan['schema_version'])
    require(rebuilt == plan, 'plan structure or derived mapping invalid')
    for op in plan['operations']:
        require(not os.path.lexists(op['new']), f'new target exists: {op["new"]}')
    if not execute:
        return dict(report, quality_pass=True, mode='apply-preview', operations=len(plan['operations']))
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open('x', encoding='utf-8', newline='') as stream:
        event(stream, {'event': 'start', 'plan_id': plan['plan_id']})
        try:
            for index, op in enumerate(plan['operations']):
                event(stream, {'event': 'intent', 'index': index})
                rename_no_replace(op['old'], op['new'])
                event(stream, {'event': 'done', 'index': index})
            report = verify_state(plan, len(plan['operations']))
            event(stream, {'event': 'verified'})
        except BaseException:
            # Reconcile the last intent and validate all contents before automatic rollback.
            stream.close()
            try:
                restored = recover(plan, journal, True)
                print(json.dumps({'automatic_recovery': restored}, ensure_ascii=False), file=sys.stderr)
            except Exception as recovery_error:
                print(json.dumps({'recovery_blocked': str(recovery_error), 'journal': str(journal)}, ensure_ascii=False), file=sys.stderr)
            raise
    return dict(report, quality_pass=True, mode='apply', completed_operations=len(plan['operations']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    audit = sub.add_parser('audit')
    audit.add_argument('target')
    audit.add_argument('--recursive', action='store_true')
    audit.add_argument('--output')
    prepare = sub.add_parser('plan')
    prepare.add_argument('target')
    prepare.add_argument('--rules', required=True)
    prepare.add_argument('--output', required=True)
    prepare.add_argument('--recursive', action='store_true')
    prepare.add_argument('--include-directories', action='store_true')
    prepare.add_argument('--directories-only', action='store_true')
    prepare.add_argument('--root-name')
    prepare.add_argument('--allow-number-change', action='store_true')
    for command in ('apply', 'verify', 'rollback'):
        p = sub.add_parser(command)
        p.add_argument('plan')
        if command != 'verify':
            p.add_argument('--approved-plan', required=True)
            p.add_argument('--journal', required=True)
            p.add_argument('--execute', action='store_true')
        else:
            p.add_argument('--state', choices=('original', 'final'), default='final')
    args = parser.parse_args()
    if args.command == 'audit':
        root = absolute_root(args.target)
        rows = scan(root, args.recursive)
        report = {'root': str(root), 'recursive': args.recursive, 'rows': rows, 'summary': summary(rows), 'quality_pass': True}
        if args.output:
            create_text(outside(args.output, root), json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        return {k: v for k, v in report.items() if k != 'rows'}
    if args.command == 'plan':
        root = absolute_root(args.target)
        scope = {'recursive': args.recursive, 'files': not args.directories_only,
                 'directories': args.include_directories or args.directories_only}
        rows = scan(root, scope['recursive'] or scope['directories'] or bool(args.root_name))
        rules = json.loads(Path(args.rules).read_text(encoding='utf-8-sig'))
        plan = make_plan(root, rows, rules, scope, args.root_name, args.allow_number_change)
        save_plan(plan, args.output)
        return {'quality_pass': True, 'plan_id': plan['plan_id'], 'summary': plan['summary'],
                'operations': len(plan['operations']), 'output': str(Path(args.output).absolute())}
    plan = load_plan(args.plan)
    if args.command == 'verify':
        return dict(verify_state(plan, 0 if args.state == 'original' else len(plan['operations'])), quality_pass=True, mode='verify-' + args.state)
    journal = outside(args.journal, Path(plan['root']))
    outside(journal, Path(plan['final_root']))
    require(args.approved_plan == plan['plan_id'], 'explicit approved plan digest required')
    if args.command == 'apply':
        return apply_plan(plan, args.approved_plan, journal, args.execute)
    return recover(plan, journal, args.execute)


if __name__ == '__main__':
    try:
        print(json.dumps(main(), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({'quality_pass': False, 'error': str(exc)}, ensure_ascii=False, indent=2))
        sys.exit(2)
