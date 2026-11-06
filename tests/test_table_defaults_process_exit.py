"""Exercise the actual Windows wrapper with fast plain-Python children, no CAD."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('powershell.exe') if sys.platform == 'win32' else None


class TableProcessExitTests(unittest.TestCase):
    @unittest.skipUnless(POWERSHELL, 'requires Windows PowerShell, starts no CAD')
    def test_real_wrapper_retains_zero_and_nonzero_fast_child_exit_codes(self):
        with tempfile.TemporaryDirectory(prefix='table process exit ') as temporary:
            directory = Path(temporary)
            scripts = directory / 'windows'
            scripts.mkdir()
            wrapper = scripts / 'calibrate-table-defaults.ps1'
            shutil.copyfile(ROOT / 'scripts/ci/windows/calibrate-table-defaults.ps1', wrapper)
            # Keep the production wrapper, argument quoting, redirection and
            # watchdog; replace only its script target with a plain child.
            (directory / 'verify-table-defaults-calibration.py').write_text(
                'import os, sys\n'
                'print("plain child completed", flush=True)\n'
                'sys.exit(int(os.environ["SWCLI_TEST_TABLE_CHILD_EXIT"]))\n')
            for exit_code in (0, 7):
                with self.subTest(exit_code=exit_code):
                    output = directory / ('output ' + str(exit_code))
                    result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-File', str(wrapper),
                        '-OutputDirectory', str(output), '-DrawingTemplate', str(directory / 'not-used.drwdot'),
                        '-DocumentTypes', 'assembly-drawing'], capture_output=True, text=True, timeout=30,
                        env=dict(os.environ, SWCLI_TEST_TABLE_CHILD_EXIT=str(exit_code)))
                    receipt = json.loads((output / 'wrapper-result.json').read_text(encoding='utf-8-sig'))
                    self.assertEqual(receipt['worker_exit_code'], exit_code, result.stdout + result.stderr)
                    self.assertEqual(receipt['success'], exit_code == 0)
                    self.assertEqual((receipt['native_seconds'], receipt['group_seconds']), (600, 1800))
                    self.assertEqual(result.returncode == 0, exit_code == 0, result.stdout + result.stderr)
                    self.assertIn('plain child completed', (output / 'worker.stdout.log').read_text())
                    self.assertFalse((output / 'watchdog-failure.json').exists())


if __name__ == '__main__':
    unittest.main()
