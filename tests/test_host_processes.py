import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/ci"))
from gate_support import host_processes


class HostInventoryTests(unittest.TestCase):
    def test_unix_pid_is_not_confused_with_windows_pid_or_other_wine_processes(self):
        output = " 123 /usr/bin/python3\n 456 SLDWORKS.exe\n 789 C:\\Program Files\\SOLIDWORKS\\sldworks.exe\n 888 lmgrd.exe\n"
        with patch.object(host_processes.sys, "platform", "linux"), \
                patch.object(host_processes.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=output)) as run:
            self.assertEqual(host_processes.solidworks_process_ids(), [456, 789])
        self.assertEqual(run.call_args.args[0], ["ps", "-axo", "pid=,comm="])

    def test_windows_csv_and_case_insensitive_image_name(self):
        output = '"System Idle Process","0","Services"\n"SLDWORKS.exe","1880","Console"\n"python.exe","25","Console"\n'
        with patch.object(host_processes.sys, "platform", "win32"), \
                patch.object(host_processes.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=output)) as run:
            self.assertEqual(host_processes.solidworks_process_ids(), [1880])
        self.assertEqual(run.call_args.args[0], ["tasklist", "/FO", "CSV", "/NH"])

    def test_unavailable_or_malformed_inventory_fails_closed(self):
        for code, output in ((1, "denied"), (0, ""), (0, "broken"), (0, "wrong-pid SLDWORKS.exe")):
            with self.subTest(output=output), patch.object(host_processes.sys, "platform", "darwin"), \
                    patch.object(host_processes.subprocess, "run", return_value=SimpleNamespace(returncode=code, stdout=output)), \
                    self.assertRaises(RuntimeError):
                host_processes.solidworks_process_ids()
        with patch.object(host_processes.subprocess, "run", side_effect=subprocess.TimeoutExpired("ps", 10)), \
                self.assertRaises(subprocess.TimeoutExpired):
            host_processes.solidworks_process_ids()
