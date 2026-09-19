import tempfile
import unittest
from pathlib import Path
from unittest import mock

from swcli.hosts import windows_batch


class WindowsBatchTests(unittest.TestCase):
    def test_manifest_parser_ignores_comments_and_blank_lines(self):
        self.assertEqual(
            windows_batch._parse_manifest_lines(
                ["", "# comment", " part.SLDPRT # trailing ", "drawing.SLDDRW"]
            ),
            ["part.SLDPRT", "drawing.SLDDRW"],
        )

    def test_batch_targets_match_dockersw_contract(self):
        outdir = Path("output")
        self.assertEqual(
            windows_batch._batch_targets(Path("part.SLDPRT"), outdir),
            [outdir / "part.STEP"],
        )
        self.assertEqual(
            windows_batch._batch_targets(Path("drawing.SLDDRW"), outdir),
            [outdir / "drawing.PDF", outdir / "drawing.DWG"],
        )
        self.assertEqual(
            windows_batch._batch_targets(Path("scene.REND.SLDASM"), outdir),
            [outdir / "scene.REND.GLB"],
        )

    def test_preflight_rejects_output_collisions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            first = workspace / "one"
            second = workspace / "two"
            first.mkdir()
            second.mkdir()
            (first / "same.SLDPRT").touch()
            (second / "same.SLDASM").touch()

            plans, issues = windows_batch._plan_batch(
                ["one/same.SLDPRT", "two/same.SLDASM"],
                workspace,
                workspace / "output",
            )

        self.assertEqual(len(plans), 1)
        self.assertEqual(issues[0]["type"], "OutputCollision")

    def test_preflight_rejects_existing_output_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            output = workspace / "output"
            output.mkdir()
            (workspace / "part.SLDPRT").touch()
            (output / "part.STEP").touch()

            plans, issues = windows_batch._plan_batch(
                ["part.SLDPRT"], workspace, output
            )
            overwrite_plans, overwrite_issues = windows_batch._plan_batch(
                ["part.SLDPRT"], workspace, output, overwrite=True
            )

        self.assertEqual(plans, [])
        self.assertEqual(issues[0]["type"], "OutputExists")
        self.assertEqual(len(overwrite_plans), 1)
        self.assertEqual(overwrite_issues, [])

    def test_batch_export_is_rejected_off_windows(self):
        with mock.patch.object(windows_batch.sys, "platform", "darwin"):
            result = windows_batch.batch_export_windows(
                "list.txt", workspace="workspace"
            )

        self.assertEqual(result["error"]["type"], "UnsupportedPlatform")


if __name__ == "__main__":
    unittest.main()
