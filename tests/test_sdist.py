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
    def members(self):
        return [
            tarfile.TarInfo("swcli-0.1.0a4.dev0/" + name) for name in verifier.REQUIRED
        ]

    def test_complete_product_sources_pass(self):
        verifier.verify_members(self.members())

    def test_missing_documentation_or_example_is_rejected(self):
        for name in ("README.CN.md", "examples/model-plate.ps1", "docs/roadmap.md"):
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(RuntimeError, "missing product files"),
            ):
                verifier.verify_members(
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
                verifier.verify_members(self.members() + [tarfile.TarInfo(name)])
        link = tarfile.TarInfo("swcli-0.1.0a4.dev0/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "outside"
        with self.assertRaisesRegex(RuntimeError, "unexpected"):
            verifier.verify_members(self.members() + [link])


if __name__ == "__main__":
    unittest.main()
