"""Dimension operations share document/session, lease and update-stamp guards."""

from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.daemon import operations
from swcli.daemon.documents import (
    DimensionNotFound,
    DocumentLeaseConflict,
    DocumentRegistry,
    SketchNotFound,
)
from swcli.result_schemas import OperationResultInvalid, validate_operation_result


def discovery_result():
    state = {"update_stamp": 10, "configuration": "Default", "editing": False}
    return {
        "ok": True,
        "action": "dimension.discover",
        "dimension": {
            "kind": "diameter",
            "unit": "millimeter",
            "value": 16,
            "driven_state": 2,
            "read_only": False,
            "configuration": "Default",
            "native_name": "D1@Sketch1",
        },
        "geometry_verification": {
            "passed": True,
            "method": "sketch-local-circle",
            "segment_count": 1,
            "profile_segment_count": 1,
            "complete_circle": True,
            "actual_radius_mm": 8,
            "actual_center_mm": {"x": 3, "y": 4, "z": 0},
            "absolute_tolerance_mm": 1e-6,
        },
        "constraint_status": 2,
        "editing": False,
        "equation_control": {"controlled": False, "equation_indices": []},
        "design_table_controlled": False,
        "observation": {
            "before": deepcopy(state),
            "after": deepcopy(state),
            "configuration_matched": True,
            "unchanged": True,
        },
    }


class Document:
    def __init__(self, title):
        self.title = title
        self.stamp = 10

    def GetTitle(self):
        return self.title

    def GetPathName(self):
        return ""

    def GetType(self):
        return 1

    def GetSaveFlag(self):
        return False

    def GetUpdateStamp(self):
        return self.stamp


class App:
    def __init__(self, target, foreground):
        self.documents = (target, foreground)
        self.ActiveDoc = foreground

    def GetDocuments(self):
        return self.documents

    def IsSame(self, first, second):
        return int(first is second)


class DimensionOperationTests(unittest.TestCase):
    def setUp(self):
        self.target, self.foreground = Document("Part1"), Document("Part2")
        self.app = App(self.target, self.foreground)
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.target)
        self.other = self.registry.register(self.foreground)
        self.registry.set_current(self.other, session_id="writer")
        self.sketch, self.dimension = SimpleNamespace(GetID=lambda: 1), object()
        self.sketch_id = self.registry.register_sketch(self.entry, self.sketch)
        self.dimension_id = self.registry.register_dimension(
            self.entry, self.sketch_id, self.dimension
        )
        self.lease = self.registry.acquire_lease(
            self.entry, session_id="writer", ttl_seconds=60
        )["lease_id"]

    @contextmanager
    def activate(self, selected):
        self.assertIs(selected, self.entry)
        self.app.ActiveDoc = selected.document
        try:
            yield
        finally:
            self.app.ActiveDoc = self.foreground

    def call(self, operation, parameters, **context):
        return operations.execute_operation(
            self.app,
            operation,
            parameters,
            documents=self.registry,
            **{
                "session_id": "writer",
                "document_id": self.entry.document_id,
                **context,
            },
        )

    def assert_context_retained(self, result):
        self.assertFalse(result["document"]["active"])
        self.assertFalse(result["document"]["current"])
        self.assertIs(self.app.ActiveDoc, self.foreground)
        self.assertIs(self.registry.resolve(None, session_id="writer"), self.other)

    @mock.patch("swcli.daemon.operations.discover_circle_diameter_windows_with_handle")
    def test_discovery_observes_another_sessions_leased_background_without_activation(
        self, discover
    ):
        self.registry.set_current(self.other, session_id="observer")
        discover.return_value = (discovery_result(), self.dimension)
        with mock.patch.object(self.registry, "temporarily_activate") as activate:
            result = self.call(
                "dimension.discover-diameter",
                {"sketch_id": self.sketch_id},
                session_id="observer",
                expected_update_stamp=10,
            )
        activate.assert_not_called()
        discover.assert_called_once_with(
            app=self.app,
            document=self.target,
            sketch_feature=self.sketch,
        )
        self.assertEqual(result["action"], "dimension.discover-diameter")
        self.assertEqual(result["dimension"]["dimension_id"], self.dimension_id)
        self.assertEqual(result["dimension"]["sketch_id"], self.sketch_id)
        self.assertEqual(self.target.stamp, 10)
        self.assert_context_retained(result)
        self.assertIs(self.registry.resolve(None, session_id="observer"), self.other)
        validate_operation_result("dimension.discover-diameter", result)

    @mock.patch("swcli.daemon.operations.discover_circle_diameter_windows_with_handle")
    def test_discovery_reuses_exact_native_handle_on_repeated_observation(
        self, discover
    ):
        native = object()
        discover.side_effect = [
            (discovery_result(), native),
            (discovery_result(), native),
        ]
        results = [
            self.call("dimension.discover-diameter", {"sketch_id": self.sketch_id})
            for _ in range(2)
        ]
        recovered_id = results[0]["dimension"]["dimension_id"]
        self.assertEqual(results[1]["dimension"]["dimension_id"], recovered_id)
        self.assertNotEqual(recovered_id, self.dimension_id)
        self.assertEqual(len(self.entry.dimensions), 2)
        self.assertIs(
            self.registry.resolve_dimension(self.entry, recovered_id).dimension, native
        )
        for result in results:
            self.assert_context_retained(result)
            validate_operation_result("dimension.discover-diameter", result)

    @mock.patch("swcli.daemon.operations.discover_circle_diameter_windows_with_handle")
    def test_discovery_guards_stale_stamp_wrong_document_and_unknown_sketch(
        self, discover
    ):
        values = {"sketch_id": self.sketch_id}
        with self.assertRaises(operations.DocumentUpdateConflict):
            self.call("dimension.discover-diameter", values, expected_update_stamp=9)
        with self.assertRaises(SketchNotFound):
            self.call(
                "dimension.discover-diameter",
                values,
                document_id=self.other.document_id,
            )
        with self.assertRaises(SketchNotFound):
            self.call("dimension.discover-diameter", {"sketch_id": "s-000000"})
        with self.assertRaisesRegex(ValueError, "lease_id is not supported"):
            self.call("dimension.discover-diameter", values, lease_id=self.lease)
        discover.assert_not_called()

    @mock.patch("swcli.daemon.operations.discover_circle_diameter_windows_with_handle")
    def test_discovery_cannot_recover_closed_or_replaced_sketch_handles(self, discover):
        values = {"sketch_id": self.sketch_id}
        self.registry.forget(self.entry.document_id)
        replacement = self.registry.register(self.target)
        with self.assertRaises(SketchNotFound):
            self.call(
                "dimension.discover-diameter",
                values,
                document_id=replacement.document_id,
            )
        discover.assert_not_called()
        self.assertFalse(replacement.dimensions)

    @mock.patch("swcli.daemon.operations.discover_circle_diameter_windows_with_handle")
    def test_failed_discovery_preserves_error_and_observation_without_any_dimension_id(
        self, discover
    ):
        native_result = {
            "ok": False,
            "action": "dimension.discover",
            "dimension": {
                "native_name": "D1@Sketch1",
                "dimension_id": "m-stale1",
                "sketch_id": "s-stale1",
            },
            "observation": {
                "before": {
                    "update_stamp": 10,
                    "configuration": "Default",
                    "editing": False,
                },
                "unchanged": False,
            },
            "error": {
                "type": "DimensionObservationUnavailable",
                "message": "ReadOnly returned unknown native metadata",
            },
        }
        before = deepcopy(native_result)
        # Even an unexpected native object on a failed read conveys no authority.
        discover.return_value = (native_result, object())
        result = self.call("dimension.discover-diameter", {"sketch_id": self.sketch_id})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], before["error"])
        self.assertEqual(result["observation"], before["observation"])
        self.assertEqual(result["dimension"], {"native_name": "D1@Sketch1"})
        self.assertEqual(len(self.entry.dimensions), 1)
        self.assert_context_retained(result)
        validate_operation_result("dimension.discover-diameter", result)

    @mock.patch("swcli.daemon.operations.discover_circle_diameter_windows_with_handle")
    def test_incomplete_or_inconsistent_discovery_success_never_registers(
        self, discover
    ):
        native = object()
        invalid_results = []
        for field, value in (
            ("read_only", None),
            ("driven_state", 2.9),
            ("native_name", None),
            ("value", float("nan")),
        ):
            result = discovery_result()
            result["dimension"][field] = value
            invalid_results.append(result)
        result = discovery_result()
        del result["dimension"]["configuration"]
        invalid_results.append(result)
        result = discovery_result()
        result["observation"]["after"]["update_stamp"] = 11
        invalid_results.append(result)
        result = discovery_result()
        result["dimension"]["configuration"] = "Other"
        invalid_results.append(result)
        result = discovery_result()
        result["observation"]["unchanged"] = False
        invalid_results.append(result)
        for result in invalid_results:
            with self.subTest(result=result), self.assertRaises(OperationResultInvalid):
                discover.return_value = (result, native)
                self.call("dimension.discover-diameter", {"sketch_id": self.sketch_id})
            self.assertEqual(len(self.entry.dimensions), 1)
            self.assertNotIn("dimension_id", result["dimension"])
            self.assertIs(self.app.ActiveDoc, self.foreground)
        discover.return_value = (discovery_result(), None)
        with self.assertRaisesRegex(OperationResultInvalid, "returned no dimension"):
            self.call("dimension.discover-diameter", {"sketch_id": self.sketch_id})
        self.assertEqual(len(self.entry.dimensions), 1)

    @mock.patch("swcli.daemon.operations.create_circle_diameter_windows_with_handle")
    def test_creation_guarded_before_mutation_and_retains_partial_native_handle(
        self, create
    ):
        values = {"sketch_id": self.sketch_id, "diameter_mm": 16}
        with self.assertRaises(DocumentLeaseConflict):
            self.call("sketch.dimension-diameter", values)
        with self.assertRaises(operations.DocumentUpdateConflict):
            self.call(
                "sketch.dimension-diameter",
                values,
                lease_id=self.lease,
                expected_update_stamp=9,
            )
        with self.assertRaises(SketchNotFound):
            self.call(
                "sketch.dimension-diameter",
                {**values, "sketch_id": "s-000000"},
                lease_id=self.lease,
            )
        create.assert_not_called()
        native = object()
        create.return_value = (
            {
                "ok": False,
                "action": "sketch.dimension-diameter",
                "error": {"type": "DimensionVerificationFailed", "message": "partial"},
            },
            native,
        )
        with mock.patch.object(
            self.registry, "temporarily_activate", side_effect=self.activate
        ):
            result = self.call(
                "sketch.dimension-diameter",
                values,
                lease_id=self.lease,
                expected_update_stamp=10,
            )
        create.assert_called_once_with(
            app=self.app,
            document=self.target,
            sketch_feature=self.sketch,
            diameter_mm=16.0,
        )
        self.assertEqual(result["sketch_id"], self.sketch_id)
        self.assertEqual(result["dimension"]["sketch_id"], self.sketch_id)
        self.assertIs(
            self.registry.resolve_dimension(
                self.entry, result["dimension"]["dimension_id"]
            ).dimension,
            native,
        )
        self.assert_context_retained(result)

    @mock.patch("swcli.daemon.operations.create_circle_diameter_windows_with_handle")
    def test_rejected_creation_does_not_invent_dimension_handle(self, create):
        create.return_value = (
            {
                "ok": False,
                "action": "sketch.dimension-diameter",
                "error": {"type": "SketchAlreadyDimensioned", "message": "duplicate"},
            },
            None,
        )
        with mock.patch.object(
            self.registry, "temporarily_activate", side_effect=self.activate
        ):
            result = self.call(
                "sketch.dimension-diameter",
                {"sketch_id": self.sketch_id, "diameter_mm": 16},
                lease_id=self.lease,
            )
        self.assertNotIn("dimension", result)
        self.assertEqual(len(self.entry.dimensions), 1)

    @mock.patch("swcli.daemon.operations.inspect_dimension_windows")
    def test_inspection_reads_exact_leased_background_dimension_without_activation(
        self, inspect
    ):
        inspect.return_value = {
            "ok": True,
            "action": "dimension.inspect",
            "dimension": {"value": 16},
        }
        values = {"dimension_id": self.dimension_id}
        with self.assertRaises(operations.DocumentUpdateConflict):
            self.call("dimension.inspect", values, expected_update_stamp=9)
        inspect.assert_not_called()
        with mock.patch.object(self.registry, "temporarily_activate") as activate:
            result = self.call(
                "dimension.inspect",
                values,
                session_id="observer",
                expected_update_stamp=10,
            )
        activate.assert_not_called()
        inspect.assert_called_once_with(
            app=self.app,
            document=self.target,
            sketch_feature=self.sketch,
            dimension=self.dimension,
        )
        self.assertEqual(result["dimension"]["dimension_id"], self.dimension_id)
        self.assertEqual(result["sketch_id"], self.sketch_id)
        self.assert_context_retained(result)

    @mock.patch("swcli.daemon.operations.set_dimension_windows")
    def test_value_edit_guards_lease_session_stamp_and_exact_target(self, setter):
        values = {"dimension_id": self.dimension_id, "value_mm": 20}
        for context in ({}, {"lease_id": self.lease, "session_id": "other"}):
            with self.assertRaises(DocumentLeaseConflict):
                self.call("dimension.set", values, **context)
        with self.assertRaises(operations.DocumentUpdateConflict):
            self.call(
                "dimension.set", values, lease_id=self.lease, expected_update_stamp=9
            )
        with self.assertRaises(DimensionNotFound):
            self.call(
                "dimension.set",
                {**values, "dimension_id": "m-000000"},
                lease_id=self.lease,
            )
        setter.assert_not_called()
        setter.return_value = {
            "ok": True,
            "action": "dimension.set",
            "dimension": {"value": 20},
        }
        with mock.patch.object(
            self.registry, "temporarily_activate", side_effect=self.activate
        ):
            result = self.call(
                "dimension.set", values, lease_id=self.lease, expected_update_stamp=10
            )
        setter.assert_called_once_with(
            app=self.app,
            document=self.target,
            sketch_feature=self.sketch,
            dimension=self.dimension,
            value_mm=20.0,
        )
        self.assert_context_retained(result)

    @mock.patch("swcli.daemon.operations.inspect_dimension_windows")
    def test_wrong_document_closed_handle_and_restart_never_reach_adapter(
        self, inspect
    ):
        values = {"dimension_id": self.dimension_id}
        with self.assertRaises(DimensionNotFound):
            self.call("dimension.inspect", values, document_id=self.other.document_id)
        self.registry.forget(self.entry.document_id)
        replacement = self.registry.register(self.target)
        with self.assertRaises(DimensionNotFound):
            self.call("dimension.inspect", values, document_id=replacement.document_id)
        inspect.assert_not_called()

    def test_internal_linear_bindings_never_enter_diameter_adapter_or_activation(self):
        for kind in ("width", "height"):
            handle = self.registry.register_dimension(
                self.entry,
                self.sketch_id,
                object(),
                kind=kind,
                profile_kind="rectangle",
            )
            for operation, values in (
                ("dimension.inspect", {"dimension_id": handle}),
                ("dimension.set", {"dimension_id": handle, "value_mm": 50}),
            ):
                with (
                    self.subTest(kind=kind, operation=operation),
                    mock.patch.object(
                        self.registry, "temporarily_activate"
                    ) as activate,
                    mock.patch.object(
                        operations, "inspect_dimension_windows"
                    ) as inspect,
                    mock.patch.object(operations, "set_dimension_windows") as setter,
                    self.assertRaises(operations.UnsupportedDimensionKind),
                ):
                    self.call(
                        operation,
                        values,
                        **(
                            {"lease_id": self.lease}
                            if operation == "dimension.set"
                            else {}
                        ),
                    )
                activate.assert_not_called()
                inspect.assert_not_called()
                setter.assert_not_called()
                self.assertIs(self.app.ActiveDoc, self.foreground)


if __name__ == "__main__":
    unittest.main()
