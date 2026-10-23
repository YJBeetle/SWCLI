import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/ci"))
from gate_support.drawing_template import drawing_template


class DrawingTemplateTests(unittest.TestCase):
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
