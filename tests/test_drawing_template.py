import sys
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/ci"))
from gate_support.drawing_template import drawing_template


class DrawingTemplateTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32" and shutil.which("powershell.exe"),
                         "Windows PowerShell native argument regression")
    def test_powershell_passes_registry_install_dir_with_spaces_and_trailing_slash(self):
        root = Path(__file__).resolve().parents[1]
        wrapper = root / "scripts/ci/windows/smoke-solidworks.ps1"
        lines = wrapper.read_text().splitlines()
        # Execute the production call, not a second version of its quoting.
        call = "\n".join(line.strip() for line in lines
                         if line.strip().startswith(("$drawingInstallDir =", "$drawingTemplate = &")))
        self.assertIn("--installation $drawingInstallDir", call)
        with tempfile.TemporaryDirectory() as temporary:
            installation = Path(temporary) / "Program Files/SOLIDWORKS"
            fixture = installation / "data/templates/gb.drwdot"
            fixture.parent.mkdir(parents=True)
            fixture.write_bytes(b"official template")
            script = "$installation = @{install_dir = $env:SWCLI_TEST_INSTALL}\n"
            script += call.replace("$PSScriptRoot", "$env:SWCLI_TEST_SCRIPTS")
            script += "\n$drawingTemplate\nexit $LASTEXITCODE\n"
            result = subprocess.run([shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive",
                                     "-Command", script], capture_output=True, text=True, timeout=30,
                env={**os.environ, "SWCLI_TEST_INSTALL": str(installation) + "\\",
                     "SWCLI_TEST_SCRIPTS": str(wrapper.parent), "SWCLI_DRAWING_TEMPLATE": "",
                     "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Path(result.stdout.strip()), fixture.resolve())

    def test_fresh_install_uses_base_gb_without_first_run_generated_template(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installation = root / "Program Files/SOLIDWORKS"
            fixture = installation / "data/templates/gb.drwdot"
            fixture.parent.mkdir(parents=True)
            fixture.write_bytes(b"official base template")
            self.assertEqual(drawing_template(root / "ProgramData", installation=installation), fixture.resolve())
            explicit = root / "custom.drwdot"
            explicit.write_bytes(b"explicit")
            self.assertEqual(drawing_template(root, explicit, installation), explicit.resolve())
            fixture.unlink()
            with self.assertRaisesRegex(RuntimeError, "Explicit drawing template"):
                drawing_template(root, installation=installation)

    def test_missing_and_ambiguous_fail_with_available_fixtures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(RuntimeError, "SWCLI_DRAWING_TEMPLATE"):
                drawing_template(root)
            matches = []
            for version in ("2025", "2026"):
                fixture = root / "SOLIDWORKS" / version / "templates/gb_a4.drwdot"
                fixture.parent.mkdir(parents=True)
                fixture.write_bytes(b"fixture")
                matches.append(fixture)
                if len(matches) == 1:
                    self.assertEqual(drawing_template(root), fixture.resolve())
            with self.assertRaisesRegex(RuntimeError, "2025.*2026"):
                drawing_template(root)
            self.assertEqual(drawing_template(root, matches[1]), matches[1].resolve())

    def test_explicit_missing_or_wrong_extension_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "part.sldprt"
            path.write_bytes(b"not a template")
            for explicit in (path, root / "missing.drwdot"):
                with self.assertRaisesRegex(RuntimeError, "Explicit drawing template"):
                    drawing_template(root, explicit)
