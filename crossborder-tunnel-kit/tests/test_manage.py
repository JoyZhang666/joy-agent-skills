"""Exercise actual pointer/journal transactions with synthetic service callbacks."""
import json
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import manage


@unittest.skipUnless(os.name == 'posix', 'Linux service transaction semantics required')
class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('old', 'new'):
            (self.root/'releases'/name).mkdir(parents=True)
        try:
            (self.root/'current').symlink_to(self.root/'releases'/'old', target_is_directory=True)
        except OSError:
            self.skipTest('symlink privilege unavailable; run on Linux')

    def test_success_then_idempotence(self):
        calls = []
        self.assertTrue(manage.activate(self.root, 'new', lambda: calls.append('restart'), lambda: None))
        self.assertEqual(manage.current(self.root), 'new')
        self.assertEqual(json.loads((self.root/'state.json').read_text())['previous'], 'old')
        self.assertFalse(manage.activate(self.root, 'new', lambda: calls.append('restart'), lambda: None))
        self.assertEqual(calls, ['restart'])

    def test_bad_health_restores_previous_pointer(self):
        def fail():
            raise RuntimeError('failed health')
        calls = []
        with self.assertRaises(RuntimeError):
            manage.activate(self.root, 'new', lambda: calls.append('restart'), fail)
        self.assertEqual(manage.current(self.root), 'old')
        self.assertEqual(len(calls), 2)
        self.assertFalse((self.root/'pending.json').exists())

    def test_failed_recovery_keeps_journal(self):
        def fail():
            raise RuntimeError('service failure')
        with self.assertRaises(RuntimeError):
            manage.activate(self.root, 'new', fail, lambda: None)
        self.assertTrue((self.root/'pending.json').exists())
        with self.assertRaises(ValueError):
            manage.activate(self.root, 'new', lambda: None, lambda: None)

    def test_external_pointer_rejected(self):
        (self.root/'current').unlink()
        (self.root/'current').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            manage.current(self.root)

    def test_traversal_revision_rejected(self):
        with self.assertRaises(ValueError):
            manage.switch(self.root, '../old')

    def test_health_checks_each_service(self):
        calls = []
        def invoke(argv):
            calls.append(argv)
            if argv[:2] == ['systemctl', 'is-active'] and argv[-1] == manage.UNITS[1]:
                raise RuntimeError('caddy down')
            return b'warp=on\n'
        with patch.object(manage, 'run', invoke), self.assertRaises(RuntimeError):
            manage.health()
        self.assertEqual(len(calls), 2)


class PlanTests(unittest.TestCase):
    def test_plan_lists_exact_owned_changes_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root/'synthetic-binary'
            binary.write_bytes(b'non-executable fixture')
            pin = {'path':str(binary),'sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}
            values = {'domain':'edge.example.com','uuid':'11111111-1111-4111-8111-111111111111',
                      'ws_path':'/'+'a'*32,'xray_port':18443,'warp_port':40000,
                      'binaries':{'xray':pin,'caddy':pin}}
            before = {str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch.object(manage,'preflight',return_value=0):
                result = manage.plan(root,values)
            self.assertFalse(result['changed'])
            self.assertTrue(result['would_change'])
            self.assertEqual(len(result['writes']),7)
            self.assertEqual(result['restart_units'],list(manage.UNITS))
            self.assertEqual(before,{str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()})
            self.assertFalse((root/'releases').exists())


if __name__ == '__main__':
    unittest.main()
