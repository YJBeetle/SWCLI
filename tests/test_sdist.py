import importlib.util
import tarfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "verify_sdist", Path(__file__).resolve().parents[1] / "scripts/ci/verify-sdist.py"
)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class SourceDistributionTests(unittest.TestCase):
    def verify(self, members):
        source = Path(__file__).resolve().parents[1] / verifier.OWNED_FIXTURE
        verifier.verify_members(members, read_member=lambda member: source.read_bytes())

    def members(self):
        return [
            tarfile.TarInfo("swcli-0.1.0a4.dev0/" + name) for name in verifier.REQUIRED
        ]

    def test_complete_product_sources_pass(self):
        self.verify(self.members())

    def test_missing_documentation_or_example_is_rejected(self):
        for name in ("README.CN.md", "examples/model-plate.ps1", "docs/roadmap.md"):
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(RuntimeError, "missing product files"),
            ):
                self.verify(
                    [m for m in self.members() if not m.name.endswith("/" + name)]
                )

    def test_unsafe_path_other_root_link_or_binary_media_is_rejected(self):
        for name in (
            "/absolute",
            "root/../escape",
            "second/file.txt",
            "swcli-0.1.0a4.dev0/source.SLDPRT",
            "swcli-0.1.0a4.dev0/source.ISO",
            "swcli-0.1.0a4.dev0/settings.reg",
        ):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                self.verify(self.members() + [tarfile.TarInfo(name)])
        link = tarfile.TarInfo("swcli-0.1.0a4.dev0/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "outside"
        with self.assertRaisesRegex(RuntimeError, "unexpected"):
            self.verify(self.members() + [link])

    def test_owned_fixture_needs_contents_and_exact_checksum(self):
        with self.assertRaisesRegex(RuntimeError, "CAD/media/registry"):
            verifier.verify_members(self.members())
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            verifier.verify_members(self.members(), read_member=lambda member: b"other CAD data")
        fixture = tarfile.TarInfo("swcli-0.1.0a4.dev0/" + verifier.OWNED_FIXTURE)
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            self.verify(self.members() + [fixture])
        fixture.size = 65537
        with self.assertRaisesRegex(RuntimeError, "oversized"):
            self.verify([m for m in self.members() if not m.name.endswith(verifier.OWNED_FIXTURE)] + [fixture])

    def test_same_filename_in_another_directory_is_not_an_exception(self):
        fixture = tarfile.TarInfo("swcli-0.1.0a4.dev0/other/rectangle-origin-bound.SLDPRT")
        with self.assertRaisesRegex(RuntimeError, "CAD/media/registry"):
            self.verify(self.members() + [fixture])


if __name__ == "__main__":
    unittest.main()
