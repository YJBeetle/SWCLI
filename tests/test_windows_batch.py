import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

from swcli.utils import export


class WindowsBatchTests(unittest.TestCase):
    def test_manifest_parser_ignores_comments_and_blank_lines(self):
        self.assertEqual(
            export._parse_manifest_lines(
                ["", "# comment", " part.SLDPRT # trailing ", "drawing.SLDDRW"]
            ),
            ["part.SLDPRT", "drawing.SLDDRW"],
        )

    def test_batch_targets_match_dockersw_contract(self):
        outdir = Path("output")
        self.assertEqual(
            export._batch_targets(Path("part.SLDPRT"), outdir),
            [outdir / "part.STEP"],
        )
        self.assertEqual(
            export._batch_targets(Path("drawing.SLDDRW"), outdir),
            [outdir / "drawing.PDF", outdir / "drawing.DWG"],
        )
        self.assertEqual(
            export._batch_targets(Path("scene.REND.SLDASM"), outdir),
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

            plans, issues = export._plan_batch(
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

            plans, issues = export._plan_batch(
                ["part.SLDPRT"], workspace, output
            )
            overwrite_plans, overwrite_issues = export._plan_batch(
                ["part.SLDPRT"], workspace, output, overwrite=True
            )

        self.assertEqual(plans, [])
        self.assertEqual(issues[0]["type"], "OutputExists")
        self.assertEqual(len(overwrite_plans), 1)
        self.assertEqual(overwrite_issues, [])

    def test_batch_export_is_rejected_off_windows(self):
        with mock.patch.object(export.sys, "platform", "darwin"):
            result = export.batch_export_windows(
                "list.txt", workspace="workspace"
            )

        self.assertEqual(result["error"]["type"], "UnsupportedPlatform")

    def test_batch_reuses_provided_app_without_owning_com_apartment(self):
        pythoncom = ModuleType("pythoncom")
        pythoncom.CoInitialize = mock.Mock()
        pythoncom.CoUninitialize = mock.Mock()
        win32com = ModuleType("win32com")
        win32com_client = ModuleType("win32com.client")
        win32com_client.GetActiveObject = mock.Mock()
        win32com.client = win32com_client
        app = mock.Mock(ActiveDoc=None)

        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            source = workspace / "part.SLDPRT"
            manifest = workspace / "list.txt"
            outdir = workspace / "output"
            source.touch()
            manifest.write_text("part.SLDPRT\n", encoding="utf-8")
            artifact = {"path": str(outdir / "part.STEP"), "size": 123}

            with (
                mock.patch.object(export.sys, "platform", "win32"),
                mock.patch.dict(
                    "sys.modules",
                    {
                        "pythoncom": pythoncom,
                        "win32com": win32com,
                        "win32com.client": win32com_client,
                    },
                ),
                mock.patch.object(
                    export,
                    "open_windows_document",
                    return_value={"ok": True},
                ) as opened,
                mock.patch.object(
                    export,
                    "export_active_windows_document",
                    return_value={"ok": True, "artifact": artifact},
                ) as exported,
                mock.patch.object(
                    export,
                    "close_active_windows_document",
                    return_value={"ok": True},
                ) as closed,
            ):
                result = export.batch_export_windows(
                    str(manifest),
                    workspace=str(workspace),
                    outdir=str(outdir),
                    app=app,
                )

        self.assertTrue(result["ok"])
        pythoncom.CoInitialize.assert_not_called()
        pythoncom.CoUninitialize.assert_not_called()
        win32com_client.GetActiveObject.assert_not_called()
        opened.assert_called_once_with(str(source.resolve()), app=app)
        exported.assert_called_once_with(
            str((outdir / "part.STEP").resolve()),
            overwrite=False,
            allow_source_modification=True,
            app=app,
        )
        closed.assert_called_once_with(discard=True, app=app)


if __name__ == "__main__":
    unittest.main()
