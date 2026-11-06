"""Linux concurrency guards; no services, certificates or real accounts accessed."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
if os.name == 'posix':
    import fcntl
    import renew_cert


@unittest.skipUnless(os.name == 'posix', 'Linux flock required')
class RenewalLockTests(unittest.TestCase):
    def test_concurrent_deployment_prevents_certificate_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with open(root/'manager.lock','a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(renew_cert,'CURRENT',root/'current'), patch.object(renew_cert,'deploy') as deploy:
                    with self.assertRaises(BlockingIOError):
                        renew_cert.main()
                    deploy.assert_not_called()

    def test_pending_recovery_prevents_certificate_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'pending.json').write_text('{}')
            with patch.object(renew_cert,'CURRENT',root/'current'), patch.object(renew_cert,'deploy') as deploy:
                with self.assertRaises(ValueError):
                    renew_cert.main()
                deploy.assert_not_called()

    def test_idle_deployment_allows_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(renew_cert,'CURRENT',Path(directory)/'current'), patch.object(renew_cert,'deploy') as deploy:
                renew_cert.main()
                deploy.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
