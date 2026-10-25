"""Observable invariants; filesystem mutations only inside TemporaryDirectory."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'batch_names.py'
spec = importlib.util.spec_from_file_location('batch_names', SCRIPT)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def rule(match='【关注：wx_test】', replacement='', kind='suffix', target='both'):
    return {'id': 'strip-ad', 'match': match, 'replacement': replacement,
            'kind': kind, 'target': target, 'reason': 'approved bounded promotion fragment'}


class NamingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='batch-name-test-')
        self.base = Path(self.temp.name)
        self.root = self.base / 'source'
        self.root.mkdir()
        self.journal = self.base / 'events.jsonl'

    def tearDown(self):
        self.temp.cleanup()

    def file(self, name, content=b'content'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def plan(self, rules=None, recursive=False, directories=False, root_name=None):
        scope = {'files': True, 'directories': directories, 'recursive': recursive}
        rows = b.scan(self.root, recursive or directories or bool(root_name))
        return b.make_plan(self.root, rows, [rule()] if rules is None else rules, scope, root_name)

    def apply(self, plan):
        return b.apply_plan(plan, plan['plan_id'], self.journal, True)

    def test_bounded_ad_and_unicode_preserved(self):
        name = '001.【探案现场】微信与QQ音乐（上）｜C++【关注：wx_test】.m4a'
        self.file(name)
        p = self.plan()
        self.assertEqual(p['rows'][0]['new_name'], name.replace('【关注：wx_test】', ''))
        self.assertEqual(p['rows'][0]['changes'][0]['spans'][0]['removed'], '【关注：wx_test】')
        self.apply(p)
        self.assertTrue(b.recover(p, self.journal, True)['quality_pass'])
        self.assertEqual([f.name for f in self.root.iterdir()], [name])

    def test_unicode_repair_requires_explicit_rule(self):
        name = 'FranÃ§ais.pdf'
        self.file(name)
        self.assertEqual(len(self.plan()['operations']), 0)
        p = self.plan([rule('FranÃ§ais', 'Français', 'exact')])
        self.assertEqual(p['rows'][0]['new_name'], 'Français.pdf')

    def test_invisible_char_review_not_automatic_removal(self):
        self.file('02.标\u200b题.pdf')
        p = self.plan()
        self.assertEqual(len(p['operations']), 0)
        self.assertTrue(p['rows'][0]['notes'])

    def test_no_false_positive_or_truncation(self):
        for name in ['微信营销方法.pdf', 'QQ音乐介绍.pdf', '123456789的故事.pdf', 'example.com.pdf', '.NET说明.txt', '长' * 70 + '.pdf']:
            self.file(name)
        p = self.plan()
        self.assertEqual(len(p['operations']), 0)
        self.assertEqual(len(p['rows']), 6)

    def test_compound_extension_case_preserved(self):
        self.file('归档【关注：wx_test】.TAR.GZ')
        self.assertEqual(self.plan()['rows'][0]['new_name'], '归档.TAR.GZ')

    def test_numbers_not_silently_changed(self):
        self.file('001.故事.pdf')
        with self.assertRaisesRegex(ValueError, 'number change'):
            self.plan([rule('001', '002', 'literal')])

    def test_approval_and_preview_have_no_mutation(self):
        self.file('故事【关注：wx_test】.pdf')
        p = self.plan()
        with self.assertRaisesRegex(ValueError, 'approved'):
            b.apply_plan(p, '', self.journal, True)
        b.apply_plan(p, p['plan_id'], self.journal, False)
        self.assertFalse(self.journal.exists())
        self.assertTrue((self.root / '故事【关注：wx_test】.pdf').exists())

    def test_cli_default_dry_run(self):
        self.file('故事【关注：wx_test】.pdf')
        p = self.plan()
        out = self.base / 'plan'
        b.save_plan(p, out)
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), 'apply', str(out / 'plan.json'),
                                 '--approved-plan', p['plan_id'], '--journal', str(self.journal)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.journal.exists())

    def test_nested_directory_file_and_empty_directory(self):
        self.file('第一季【关注：wx_test】/分集【关注：wx_test】/001.故事【关注：wx_test】.m4a')
        (self.root / '空目录【关注：wx_test】').mkdir()
        p = self.plan(recursive=True, directories=True)
        self.apply(p)
        self.assertTrue((self.root / '第一季/分集/001.故事.m4a').exists())
        self.assertTrue((self.root / '空目录').is_dir())
        b.recover(p, self.journal, True)
        b.verify_state(p, 0)

    def test_shallow_directory_covers_descendants_without_renaming_them(self):
        self.file('目录【关注：wx_test】/故事【关注：wx_test】.pdf')
        p = self.plan(directories=True)
        self.assertEqual(len(p['operations']), 1)
        self.apply(p)
        self.assertTrue((self.root / '目录/故事【关注：wx_test】.pdf').exists())
        b.recover(p, self.journal, True)

    def test_default_scope_is_shallow_files_only(self):
        self.file('目录【关注：wx_test】/故事【关注：wx_test】.pdf')
        p = self.plan()
        self.assertEqual(len(p['operations']), 0)
        self.assertEqual(p['summary']['directories'], 1)
        self.assertEqual(p['summary']['files'], 0)

    def test_root_rename_restore_and_load_after_rename(self):
        self.file('内容【关注：wx_test】.pdf')
        p = self.plan(root_name='new-source')
        out = self.base / 'manifest'
        b.save_plan(p, out)
        self.apply(p)
        b.load_plan(out / 'plan.json')
        self.assertTrue((self.base / 'new-source/内容.pdf').exists())
        b.recover(p, self.journal, True)
        self.assertTrue((self.root / '内容【关注：wx_test】.pdf').exists())

    def test_idempotent_second_plan(self):
        self.file('故事【关注：wx_test】.pdf')
        self.apply(self.plan())
        self.assertEqual(len(self.plan()['operations']), 0)

    def test_file_set_drift_added_removed(self):
        f = self.file('故事【关注：wx_test】.pdf')
        p = self.plan()
        extra = self.file('new.txt')
        with self.assertRaisesRegex(ValueError, 'set drift'):
            self.apply(p)
        extra.unlink()
        f.unlink()
        with self.assertRaisesRegex(ValueError, 'set drift'):
            self.apply(p)

    def test_same_size_content_and_noop_drift(self):
        f = self.file('unchanged.txt', b'abc')
        p = self.plan()
        before = f.stat()
        f.write_bytes(b'xyz')
        os.utime(f, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, 'drift'):
            self.apply(p)

    def test_added_descendant_blocks_directory_rename(self):
        self.file('目录【关注：wx_test】/a.txt')
        p = self.plan(directories=True)
        self.file('目录【关注：wx_test】/b.txt')
        with self.assertRaisesRegex(ValueError, 'set drift'):
            self.apply(p)

    def test_conflicts_merge_and_cycle_rejected(self):
        self.file('a【关注：wx_test】.pdf')
        self.file('a.pdf')
        with self.assertRaises(ValueError):
            self.plan()
        with self.assertRaises(ValueError):
            b.name_check('COM¹.txt')
        for name in ('../outside', 'NUL.txt', 'bad.', 'bad ', 'a|b'):
            with self.assertRaises(ValueError):
                b.name_check(name)

    def test_plan_and_csv_tampering(self):
        self.file('a【关注：wx_test】.pdf')
        p = self.plan()
        out = self.base / 'bundle'
        b.save_plan(p, out)
        text = (out / 'plan.json').read_text(encoding='utf-8')
        (out / 'plan.json').write_text(text.replace('approved bounded', 'unapproved bounded'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'digest'):
            b.load_plan(out / 'plan.json')
        (out / 'plan.json').write_text(text, encoding='utf-8')
        with (out / 'rename-manifest.csv').open('a', encoding='utf-8') as f:
            f.write('extra')
        with self.assertRaisesRegex(ValueError, 'CSV'):
            b.load_plan(out / 'plan.json')

    def test_changed_mapping_with_recomputed_digest_rejected(self):
        self.file('a【关注：wx_test】.pdf')
        p = self.plan()
        p['operations'][0]['new'] = str(self.base / 'outside.pdf')
        p['plan_id'] = b.digest({k: v for k, v in p.items() if k != 'plan_id'})
        with self.assertRaisesRegex(ValueError, 'derived mapping'):
            self.apply(p)

    def test_failure_restores_completed_subset_and_can_recheck_journal(self):
        self.file('a【关注：wx_test】.pdf')
        self.file('b【关注：wx_test】.pdf')
        p = self.plan()
        real = b.rename_no_replace
        calls = 0
        def fail_second(old, new):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('simulated locked file')
            real(old, new)
        with patch.object(b, 'rename_no_replace', fail_second):
            with self.assertRaises(OSError):
                self.apply(p)
        b.verify_state(p, 0)
        self.assertEqual(b.recover(p, self.journal)['completed_operations'], 0)

    def test_crash_after_rename_before_completion_log(self):
        self.file('a【关注：wx_test】.pdf')
        p = self.plan()
        with self.journal.open('w', encoding='utf-8') as f:
            b.event(f, {'event': 'start', 'plan_id': p['plan_id']})
            b.event(f, {'event': 'intent', 'index': 0})
        b.rename_no_replace(**p['operations'][0])
        self.assertEqual(b.recover(p, self.journal)['completed_operations'], 1)
        b.recover(p, self.journal, True)
        b.verify_state(p, 0)

    def test_crash_before_rename(self):
        self.file('a【关注：wx_test】.pdf')
        p = self.plan()
        with self.journal.open('w', encoding='utf-8') as f:
            b.event(f, {'event': 'start', 'plan_id': p['plan_id']})
            b.event(f, {'event': 'intent', 'index': 0})
        b.recover(p, self.journal, True)
        self.assertEqual(b.recover(p, self.journal)['completed_operations'], 0)

    def test_rollback_conflict_preserves_new_file(self):
        self.file('a【关注：wx_test】.pdf')
        p = self.plan()
        self.apply(p)
        extra = self.file('a【关注：wx_test】.pdf', b'new external content')
        with self.assertRaisesRegex(ValueError, 'set drift'):
            b.recover(p, self.journal, True)
        self.assertEqual(extra.read_bytes(), b'new external content')

    def test_damaged_journal_stops(self):
        self.file('a【关注：wx_test】.pdf')
        p = self.plan()
        self.apply(p)
        with self.journal.open('a', encoding='utf-8') as f:
            f.write('{')
        with self.assertRaises(ValueError):
            b.recover(p, self.journal, True)
        b.verify_state(p, 1)

    def test_root_target_collision(self):
        (self.base / 'new-source').mkdir()
        with self.assertRaisesRegex(ValueError, 'root already exists'):
            self.plan(root_name='new-source')

    def test_case_only_root_rename_rejected(self):
        with self.assertRaisesRegex(ValueError, 'case-only'):
            self.plan(root_name='SOURCE')

    def test_complete_json_without_final_newline_rejected(self):
        self.file('a【关注：wx_test】.pdf')
        p = self.plan()
        self.apply(p)
        self.journal.write_bytes(self.journal.read_bytes().rstrip(b'\n'))
        before = self.journal.read_bytes()
        with self.assertRaisesRegex(ValueError, 'incomplete journal'):
            b.recover(p, self.journal, True)
        self.assertEqual(before, self.journal.read_bytes())
        b.verify_state(p, 1)

    def test_directory_merge_rejected(self):
        (self.root / '同名').mkdir()
        (self.root / '同名【关注：wx_test】').mkdir()
        with self.assertRaises(ValueError):
            self.plan(directories=True)

    def test_cycle_rejected(self):
        self.file('a.txt')
        self.file('b.txt')
        rules = [rule('a', 'temporary', 'exact'), dict(rule('b', 'a', 'exact'), id='two'),
                 dict(rule('temporary', 'b', 'exact'), id='three')]
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            self.plan(rules)

    def test_interrupted_reverse_operation(self):
        self.file('a【关注：wx_test】.pdf')
        p = self.plan()
        self.apply(p)
        with self.journal.open('a', encoding='utf-8') as f:
            b.event(f, {'event': 'undo_intent', 'index': 0})
        b.rename_no_replace(p['operations'][0]['new'], p['operations'][0]['old'])
        b.recover(p, self.journal, True)
        b.verify_state(p, 0)

    def test_path_traversal_rejected(self):
        for value in ('../outside', '/absolute', 'a/../b', 'a\\b', 'a//b'):
            with self.assertRaises(ValueError):
                b.relative_check(value)

    def test_unicode_normalization_collision(self):
        self.file('é.txt')
        self.file('e\u0301.txt')
        with self.assertRaisesRegex(ValueError, 'normalization collision'):
            self.plan()

    def test_numbering_gaps_and_duplicates_separate_from_content(self):
        self.file('001.a.txt', b'a')
        self.file('003.b.txt', b'b')
        self.file('003.c.txt', b'c')
        report = b.summary(b.scan(self.root, False))
        self.assertEqual(report['numbering_by_parent']['.']['missing_between_min_max'], [2])
        self.assertEqual(len(report['numbering_by_parent']['.']['duplicate_numbers']), 1)
        self.assertEqual(report['duplicate_content'], [])

    def test_reparse_attribute_rejected(self):
        f = self.file('normal.txt')
        original = Path.lstat
        class Reparse:
            st_mode = 0
            st_file_attributes = 1024
        def attributes(path, *args, **kwargs):
            return Reparse() if path == f else original(path, *args, **kwargs)
        with patch.object(Path, 'lstat', attributes):
            with self.assertRaisesRegex(ValueError, 'reparse'):
                b.no_links(f)

    def test_target_appearing_at_rename_does_not_overwrite(self):
        f = self.file('a【关注：wx_test】.pdf')
        target = self.root / 'a.pdf'
        p = self.plan()
        real = b.rename_no_replace
        def collision(old, new):
            target.write_bytes(b'external')
            real(old, new)
        with patch.object(b, 'rename_no_replace', collision):
            with self.assertRaises(ValueError):
                self.apply(p)
        self.assertTrue(f.exists())
        self.assertEqual(target.read_bytes(), b'external')


if __name__ == '__main__':
    unittest.main(verbosity=2)
