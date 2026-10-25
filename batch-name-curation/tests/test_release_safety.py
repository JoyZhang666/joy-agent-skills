"""Release regressions. Run only in an isolated Windows environment."""
import csv
import ctypes
from ctypes import wintypes
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'batch_names.py'
spec = importlib.util.spec_from_file_location('release_batch_names', SCRIPT)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class ReleaseSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='release-safety-')
        self.base = Path(self.temp.name)
        self.root = self.base / 'source'
        self.root.mkdir()
        self.journal = self.base / 'events.jsonl'

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, schema=2):
        return b.make_plan(self.root, b.scan(self.root, True), [
            {'id': 'demo', 'kind': 'suffix', 'match': '【演示广告】',
             'replacement': '', 'target': 'both', 'reason': 'synthetic suffix'}],
            {'recursive': True, 'files': True, 'directories': True}, schema_version=schema)

    def bundle(self, schema=2):
        (self.root / '示例【演示广告】.txt').write_bytes(b'synthetic')
        plan = self.plan(schema)
        folder = self.base / 'proposal'
        b.save_plan(plan, folder)
        return plan, folder

    def test_csv_formula_prefixes_and_controls_are_visible_text(self):
        for value in ('=1+1', '+SUM(1)', '-1+2', '@SUM(1)', '＝1', '＋1', '－1', '＠x',
                      '  =1', '\t=1', '\r=1', '\n=1', '\u200b=1', '\ufeff=1', 'a\tb'):
            with self.subTest(value=repr(value)):
                self.assertEqual(b.csv_cell(value), '[text] ' + value)
        self.assertEqual(b.csv_cell('正常中文名称.txt'), '正常中文名称.txt')

    def test_csv_quoting_and_exact_json_names(self):
        name = '=1+1,中文【演示广告】.txt'
        (self.root / name).write_bytes(b'demo')
        plan = self.plan()
        folder = self.base / 'proposal'
        b.save_plan(plan, folder)
        loaded = b.load_plan(folder / 'plan.json')
        self.assertEqual(loaded['rows'][0]['old_path'], name)
        cells = list(csv.DictReader(io.StringIO(b.csv_text(loaded))))
        self.assertEqual(cells[0]['old_path'], '[text] ' + name)
        self.assertEqual(cells[0]['new_path'], '[text] =1+1,中文.txt')
        b.apply_plan(loaded, plan['plan_id'], self.journal, True)
        self.assertTrue((self.root / '=1+1,中文.txt').is_file())
        b.recover(loaded, self.journal, True)
        b.verify_state(loaded, 0)

    def test_embedded_quotes_and_delimiters_remain_one_cell(self):
        plan = {'schema_version': 2, 'rows': [
            dict(old_path='=x,";@y', new_path='=new,";@z', kind='file', size=1,
                 sha256='a' * 64, changes=[], notes=[])]}
        rows = list(csv.reader(io.StringIO(b.csv_text(plan))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[1]), 7)
        self.assertEqual(rows[1][0], '[text] =x,";@y')

    def test_legacy_csv_bytes_match_independent_v1_renderer(self):
        plan, _ = self.bundle(1)
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=b.CSV_FIELDS)
        writer.writeheader()
        for row in plan['rows']:
            out = {key: row[key] for key in b.CSV_FIELDS}
            out['changes'] = json.dumps(out['changes'], ensure_ascii=False, separators=(',', ':'))
            out['notes'] = json.dumps(out['notes'], ensure_ascii=False)
            writer.writerow(out)
        self.assertEqual(b.csv_text(plan), stream.getvalue())

    def test_legacy_approval_and_existing_journal_rollback(self):
        plan, folder = self.bundle(1)
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        original_id = plan['plan_id']
        loaded = b.load_plan(folder / 'plan.json')
        b.apply_plan(loaded, original_id, self.journal, True)
        # Existing v1 journals contain the original digest and no format conversion.
        self.assertEqual(json.loads(self.journal.read_text(encoding='utf-8').splitlines()[0])['plan_id'], original_id)
        b.recover(b.load_plan(folder / 'plan.json'), self.journal, True)
        b.verify_state(loaded, 0)
        self.assertEqual(before, {p.name: p.read_bytes() for p in folder.iterdir()})

    def test_unknown_and_boolean_schema_rejected(self):
        for schema in (0, 3, True, 2.0, '2'):
            with self.subTest(schema=schema), self.assertRaisesRegex(ValueError, 'schema'):
                self.plan(schema)

    def test_plan_symlink_rejected_before_read(self):
        _, folder = self.bundle()
        path = folder / 'plan.json'
        real = folder / 'real.json'
        path.rename(real)
        path.symlink_to(real)
        with patch.object(Path, 'read_text', side_effect=AssertionError('must not read')):
            with self.assertRaisesRegex(ValueError, 'reparse'):
                b.load_plan(path)

    def test_csv_symlink_rejected_before_json_read(self):
        _, folder = self.bundle()
        path = folder / 'rename-manifest.csv'
        real = folder / 'real.csv'
        path.rename(real)
        path.symlink_to(real)
        with patch.object(Path, 'read_text', side_effect=AssertionError('must not read')):
            with self.assertRaisesRegex(ValueError, 'reparse'):
                b.load_plan(folder / 'plan.json')

    def test_linked_parent_rejected_before_read(self):
        _, folder = self.bundle()
        linked = self.base / 'linked'
        linked.symlink_to(folder, target_is_directory=True)
        with patch.object(Path, 'read_text', side_effect=AssertionError('must not read')):
            with self.assertRaisesRegex(ValueError, 'reparse'):
                b.load_plan(linked / 'plan.json')

    def test_nonregular_inputs_rejected_before_read(self):
        _, folder = self.bundle()
        path = folder / 'rename-manifest.csv'
        path.unlink()
        path.mkdir()
        with patch.object(Path, 'read_text', side_effect=AssertionError('must not read')):
            with self.assertRaisesRegex(ValueError, 'regular'):
                b.load_plan(folder / 'plan.json')

    def test_csv_display_tampering_remains_rejected(self):
        (self.root / '=1【演示广告】.txt').write_bytes(b'demo')
        plan = self.plan()
        folder = self.base / 'proposal'
        b.save_plan(plan, folder)
        path = folder / 'rename-manifest.csv'
        path.write_bytes(path.read_bytes().replace(b'[text] ', b''))
        with self.assertRaisesRegex(ValueError, 'CSV'):
            b.load_plan(folder / 'plan.json')

    def test_all_rule_kinds_still_apply_and_rollback(self):
        for index, kind in enumerate(('suffix', 'literal', 'regex', 'exact')):
            root = self.base / f'case-{index}'
            root.mkdir()
            (root / '课程广告.txt').write_bytes(b'demo')
            rule = {'id': kind, 'kind': kind, 'match': '课程广告' if kind == 'exact' else '广告',
                    'replacement': '课程' if kind == 'exact' else '', 'target': 'file', 'reason': 'synthetic rule'}
            plan = b.make_plan(root, b.scan(root, False), [rule],
                               {'files': True, 'directories': False, 'recursive': False})
            journal = self.base / f'journal-{index}.jsonl'
            b.apply_plan(plan, plan['plan_id'], journal, True)
            self.assertEqual((root / '课程.txt').read_bytes(), b'demo')
            b.recover(plan, journal, True)
            b.verify_state(plan, 0)

    def test_actual_windows_lock_recovers_completed_subset(self):
        self.assertEqual(os.name, 'nt', 'Windows execution is required')
        (self.root / 'a【演示广告】.txt').write_bytes(b'a')
        locked = self.root / 'b【演示广告】.txt'
        locked.write_bytes(b'b')
        plan = self.plan()
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(locked), 0x80000000, 3, None, 3, 0x80, None)
        self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
        try:
            with self.assertRaises(OSError):
                b.apply_plan(plan, plan['plan_id'], self.journal, True)
            b.verify_state(plan, 0)
        finally:
            kernel.CloseHandle(handle)

    def test_cli_full_cycle_preserves_files_mtime_and_directories(self):
        folder = self.root / '中文目录【演示广告】'
        folder.mkdir()
        original = folder / '001.课程【演示广告】.txt'
        original.write_bytes(b'synthetic full cycle')
        before = original.stat()
        rules = self.base / 'rules.json'
        rules.write_text(json.dumps([{'id': 'demo', 'kind': 'suffix', 'match': '【演示广告】',
            'replacement': '', 'target': 'both', 'reason': 'synthetic'}], ensure_ascii=False), encoding='utf-8')
        proposal = self.base / 'proposal'
        def run(*args):
            result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(SCRIPT), *map(str, args)],
                                    capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            return json.loads(result.stdout)
        run('audit', self.root, '--recursive', '--output', self.base / 'audit.json')
        plan_result = run('plan', self.root, '--rules', rules, '--output', proposal,
                          '--recursive', '--include-directories', '--root-name', 'renamed-source')
        plan_path = proposal / 'plan.json'
        common = (plan_path, '--approved-plan', plan_result['plan_id'], '--journal', self.journal)
        run('apply', *common)
        self.assertFalse(self.journal.exists())
        run('apply', *common, '--execute')
        run('verify', plan_path, '--state', 'final')
        renamed = self.base / 'renamed-source/中文目录/001.课程.txt'
        self.assertEqual(renamed.read_bytes(), b'synthetic full cycle')
        self.assertEqual(renamed.stat().st_mtime_ns, before.st_mtime_ns)
        run('rollback', *common)
        run('rollback', *common, '--execute')
        run('verify', plan_path, '--state', 'original')
        self.assertEqual(original.read_bytes(), b'synthetic full cycle')
        self.assertEqual(original.stat().st_mtime_ns, before.st_mtime_ns)


if __name__ == '__main__':
    unittest.main(verbosity=2)
