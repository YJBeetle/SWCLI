import copy
import math
import unittest
from types import SimpleNamespace
from unittest import mock

from swcli.hosts import windows_sketch_inspection
from swcli.hosts.windows_sketch_inspection import (
    inspect_sketch_windows,
    list_sketches_windows_with_handles,
)
from swcli.result_schemas import OperationResultInvalid, validate_operation_result


def point(x, y, z=0):
    return SimpleNamespace(X=x, Y=y, Z=z)


class SketchInspectionTests(unittest.TestCase):
    def setUp(self):
        self.line = SimpleNamespace(
            GetType=lambda: 0,
            ConstructionGeometry=False,
            GetStartPoint2=lambda: point(0, 0),
            GetEndPoint2=lambda: point(0.1, 0.05),
        )
        self.circle = SimpleNamespace(
            GetType=lambda: 1,
            ConstructionGeometry=True,
            IsCircle=lambda: 1,
            GetRadius=lambda: 0.004,
            GetCenterPoint2=lambda: point(0.01, 0.02),
        )
        self.sketch = SimpleNamespace(
            GetSketchSegments=lambda: (self.line, self.circle),
            GetConstrainedStatus=lambda: 2,
            ModelToSketchTransform=SimpleNamespace(
                ArrayData=[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
            ),
        )
        self.feature = SimpleNamespace(
            Name="renamed-sketch",
            GetID=lambda: 1,
            GetTypeName2=lambda: "ProfileFeature",
            GetSpecificFeature2=lambda: self.sketch,
            GetOwnerFeature=lambda: None,
            GetNextFeature=lambda: None,
            GetFirstSubFeature=lambda: None,
            GetNextSubFeature=lambda: None,
        )
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            FirstFeature=lambda: self.feature,
            SketchManager=SimpleNamespace(ActiveSketch=None),
            ClearSelection2=mock.Mock(),
            EditRebuild3=mock.Mock(),
        )
        self.app = SimpleNamespace(IsSame=lambda first, second: int(first is second))

    def call(self, **kwargs):
        return inspect_sketch_windows(
            app=self.app, document=self.document, sketch_feature=self.feature, **kwargs
        )

    def schema_check(self, result):
        result = copy.deepcopy(result)
        if "sketch" in result:
            result["sketch"]["sketch_id"] = "s-ab12cd"
        result["document"] = {
            "title": "Part1",
            "path": "",
            "type": 1,
            "modified": True,
            "update_stamp": 0,
        }
        validate_operation_result("sketch.inspect", result)
        return result

    def test_decodes_lines_circles_construction_and_native_constraint_code_without_writes(
        self,
    ):
        result = self.call()
        self.assertTrue(result["ok"])
        self.assertTrue(result["geometry_complete"])
        self.assertEqual(result["segment_count"], 2)
        self.assertEqual(result["profile_segment_count"], 1)
        self.assertEqual(result["sketch"]["constraint_status"], 2)
        self.assertFalse(result["sketch"]["absorbed"] or result["editing"])
        self.assertIsNone(result["sketch"]["owner"])
        self.assertEqual(
            result["segments"][0]["geometry"]["end_mm"], {"x": 100, "y": 50, "z": 0}
        )
        self.assertEqual(
            result["segments"][1]["geometry"],
            {
                "kind": "arc",
                "complete_circle": True,
                "radius_mm": 4,
                "center_mm": {"x": 10, "y": 20, "z": 0},
            },
        )
        self.document.ClearSelection2.assert_not_called()
        self.document.EditRebuild3.assert_not_called()
        self.schema_check(result)

    def test_absorbed_sketch_remains_readable_with_native_owner_identity(self):
        owner = SimpleNamespace(Name="renamed-boss", GetTypeName2=lambda: "ICE")
        self.feature.GetOwnerFeature = lambda: owner
        result = self.call()
        self.assertTrue(result["ok"] and result["sketch"]["absorbed"])
        self.assertEqual(
            result["sketch"]["owner"], {"name": "renamed-boss", "type": "ICE"}
        )
        self.schema_check(result)

    def test_listed_absorbed_subfeature_only_handle_remains_inspectable(self):
        boss = FeatureFixture("boss", kind="ICE", name="absorbing-boss")
        boss.child = self.feature
        self.feature.GetOwnerFeature = lambda: boss
        self.document.FirstFeature = lambda: boss
        listed, handles = list_sketches_windows_with_handles(
            app=self.app, document=self.document
        )
        self.assertTrue(listed["ok"])
        self.assertEqual(handles, [self.feature])
        observed = inspect_sketch_windows(
            app=self.app, document=self.document, sketch_feature=handles[0]
        )
        self.assertTrue(observed["ok"] and observed["geometry_complete"])
        self.assertTrue(observed["sketch"]["absorbed"])
        self.assertEqual(
            observed["sketch"]["owner"], {"name": "absorbing-boss", "type": "ICE"}
        )
        self.document.ClearSelection2.assert_not_called()
        self.document.EditRebuild3.assert_not_called()
        self.schema_check(observed)

    def test_liveness_traversal_fails_closed_even_when_match_precedes_bad_graph(self):
        def unreadable():
            raise RuntimeError("native descendant traversal unavailable")

        for failure in ("cycle", "native", "budget", "identity"):
            with self.subTest(failure=failure):
                self.setUp()
                if failure == "cycle":
                    self.feature.GetNextFeature = lambda: self.feature
                elif failure == "native":
                    self.feature.GetFirstSubFeature = unreadable
                elif failure == "identity":
                    self.app.IsSame = lambda first, second: 2
                else:
                    self.feature.GetNextFeature = lambda: FeatureFixture(
                        "second", kind="RefPlane"
                    )
                with mock.patch.object(
                    windows_sketch_inspection,
                    "_LIST_TRAVERSAL_LIMIT",
                    1 if failure == "budget" else 10000,
                ):
                    result = self.call()
                self.assertFalse(result["ok"])
                self.assertNotIn("sketch", result)
                self.assertNotIn("segments", result)
                expected = {
                    "cycle": "SketchTraversalCycle",
                    "native": "RuntimeError",
                    "budget": "SketchTraversalLimitExceeded",
                    "identity": "RuntimeError",
                }[failure]
                self.assertEqual(result["error"]["type"], expected)
                self.schema_check(result)

    def test_editing_flag_uses_exact_sketch_not_any_active_sketch(self):
        self.document.SketchManager.ActiveSketch = self.sketch
        self.assertTrue(self.call()["editing"])
        self.document.SketchManager.ActiveSketch = object()
        self.assertFalse(self.call()["editing"])

    def test_open_arc_reports_endpoints_and_contract_requires_them(self):
        self.circle.IsCircle = lambda: 0
        self.circle.GetStartPoint2 = lambda: point(0.014, 0.02)
        self.circle.GetEndPoint2 = lambda: point(0.01, 0.024)
        result = self.schema_check(self.call())
        self.assertFalse(result["segments"][1]["geometry"]["complete_circle"])
        del result["segments"][1]["geometry"]["end_mm"]
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("sketch.inspect", result)

    def test_unreported_types_have_metadata_and_explicit_incomplete_warning(self):
        self.line.GetType = lambda: 3
        result = self.call()
        self.assertTrue(result["ok"])
        self.assertFalse(result["geometry_complete"])
        self.assertEqual(result["segments"][0]["type_code"], 3)
        self.assertIsNone(result["segments"][0]["geometry"])
        self.assertEqual(result["warnings"][0]["code"], "sketch-geometry-not-reported")
        self.schema_check(result)

    def test_empty_sketch_is_successfully_observed_without_guessing_geometry(self):
        self.sketch.GetSketchSegments = lambda: None
        result = self.call()
        self.assertTrue(result["ok"] and result["geometry_complete"])
        self.assertEqual(result["segments"], [])
        self.schema_check(result)

    def test_limits_reject_incomplete_inspection_before_decoding(self):
        for limit in (0, -1, True, 1.5):
            with self.subTest(limit=limit):
                self.assertEqual(
                    self.call(max_segments=limit)["error"]["type"], "InvalidArgument"
                )
        result = self.call(max_segments=1)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "SketchInspectionLimitExceeded")
        self.assertNotIn("segments", result)
        self.schema_check(result)

    def test_stale_cross_document_or_nonprofile_handle_is_rejected(self):
        self.document.FirstFeature = lambda: None
        self.assertEqual(self.call()["error"]["type"], "SketchUnavailable")
        self.document.FirstFeature = lambda: self.feature
        self.feature.GetTypeName2 = lambda: "Boss"
        self.assertEqual(self.call()["error"]["type"], "SketchUnavailable")
        self.document.GetType = lambda: 2
        self.assertEqual(self.call()["error"]["type"], "UnsupportedDocumentType")

    def test_native_read_failures_nonfinite_geometry_and_bad_transform_fail_closed(
        self,
    ):
        for change in ("coordinates", "radius", "constraint", "transform"):
            with self.subTest(change=change):
                self.setUp()
                if change == "coordinates":
                    self.line.GetEndPoint2 = lambda: point(math.inf, 0)
                elif change == "radius":
                    self.circle.GetRadius = lambda: math.nan
                elif change == "constraint":
                    self.sketch.GetConstrainedStatus = mock.Mock(
                        side_effect=RuntimeError("COM unavailable")
                    )
                else:
                    self.sketch.ModelToSketchTransform.ArrayData = [0] * 15
                result = self.call()
                self.assertFalse(result["ok"])
                self.assertNotIn("geometry_complete", result)
                self.schema_check(result)


class FeatureFixture:
    _ids_by_identity = {}

    def __init__(self, identity, *, kind="ProfileFeature", name=None):
        self.identity = identity
        self.feature_id = self._ids_by_identity.setdefault(
            identity, len(self._ids_by_identity) + 100
        )
        self.Name = name or str(identity)
        self.kind = kind
        self.root_next = self.sub_next = self.child = self.owner = None
        self.sketch = SimpleNamespace(GetConstrainedStatus=lambda: 2)

    def GetID(self):
        return self.feature_id

    def GetTypeName2(self):
        return self.kind

    def GetSpecificFeature2(self):
        return self.sketch

    def GetNextFeature(self):
        return self.root_next

    def GetFirstSubFeature(self):
        return self.child

    def GetNextSubFeature(self):
        return self.sub_next

    def GetOwnerFeature(self):
        return self.owner


class SketchListingTests(unittest.TestCase):
    def setUp(self):
        self.feature = FeatureFixture("circle", name="圆草图")
        self.app = SimpleNamespace(
            IsSame=lambda first, second: int(first.identity == second.identity),
            ActivateDoc3=mock.Mock(),
            SetUserPreferenceToggle=mock.Mock(),
        )
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            FirstFeature=lambda: self.feature,
            ClearSelection2=mock.Mock(),
            EditRebuild3=mock.Mock(),
            EditSketch=mock.Mock(),
            SketchManager=SimpleNamespace(
                ActiveSketch=object(), InsertSketch=mock.Mock()
            ),
        )

    def call(self, **kwargs):
        return list_sketches_windows_with_handles(
            app=self.app, document=self.document, **kwargs
        )

    def assert_failure(self, result, handles, error):
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], error)
        self.assertNotIn("sketches", result)
        self.assertNotIn("count", result)
        self.assertEqual(handles, [])

    def test_normal_list_returns_exact_handles_without_mutation_or_edit_exit(self):
        result, handles = self.call()
        self.assertEqual(
            result,
            {
                "ok": True,
                "action": "sketch.list",
                "count": 1,
                "sketches": [
                    {
                        "name": "圆草图",
                        "type": "ProfileFeature",
                        "constraint_status": 2,
                        "absorbed": False,
                        "owner": None,
                    }
                ],
            },
        )
        self.assertIs(handles[0], self.feature)
        self.document.ClearSelection2.assert_not_called()
        self.document.EditRebuild3.assert_not_called()
        self.document.EditSketch.assert_not_called()
        self.document.SketchManager.InsertSketch.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()
        self.app.SetUserPreferenceToggle.assert_not_called()

    def test_nested_absorbed_profiles_are_discovered_with_native_owner(self):
        folder = FeatureFixture("folder", kind="FtrFolder")
        boss = FeatureFixture("boss", kind="ICE", name="拉伸")
        self.document.FirstFeature = lambda: folder
        folder.child = boss
        boss.child = self.feature
        self.feature.owner = boss
        result, handles = self.call()
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertIs(handles[0], self.feature)
        self.assertEqual(
            result["sketches"][0]["owner"], {"name": "拉伸", "type": "ICE"}
        )
        self.assertTrue(result["sketches"][0]["absorbed"])

    def test_root_and_subfeature_aliases_deduplicate_by_native_identity(self):
        boss = FeatureFixture("boss", kind="ICE")
        alias = FeatureFixture("circle", name="圆草图")
        alias.owner = self.feature.owner = boss
        self.feature.root_next = boss
        boss.child = alias
        result, handles = self.call()
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(handles, [self.feature])

    def test_distinct_sketches_with_same_name_are_not_deduplicated(self):
        second = FeatureFixture("other-circle", name="圆草图")
        self.feature.root_next = second
        result, handles = self.call()
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(handles, [self.feature, second])

    def test_thousand_unique_features_have_linear_native_identity_reads(self):
        nodes = [FeatureFixture(index, kind="RefPlane") for index in range(1000)]
        reads = []
        for node in nodes:
            identity = node.GetID()

            def get_id(identity=identity):
                reads.append(identity)
                return identity

            node.GetID = get_id
        for first, second in zip(nodes, nodes[1:]):
            first.root_next = second
        self.document.FirstFeature = lambda: nodes[0]
        self.app.IsSame = mock.Mock(side_effect=self.app.IsSame)
        result, handles = self.call()
        self.assertTrue(result["ok"], result)
        self.assertEqual((result["count"], handles), (0, []))
        self.assertEqual(len(reads), 1000)
        self.assertEqual(len(set(reads)), 1000)
        self.app.IsSame.assert_not_called()

    def test_duplicate_native_id_for_different_features_fails_closed(self):
        second = FeatureFixture("different", name=self.feature.Name)
        second.feature_id = self.feature.feature_id
        self.feature.root_next = second
        self.assert_failure(*self.call(), "SketchFeatureIdConflict")

    def test_invalid_unavailable_or_unreadable_feature_ids_fail_closed(self):
        for value in (None, True, 1.5, "1", 2**31, -(2**31) - 1):
            with self.subTest(value=value):
                self.setUp()
                self.feature.GetID = lambda value=value: value
                self.assert_failure(*self.call(), "RuntimeError")
        self.setUp()
        self.feature.GetID = None
        self.assert_failure(*self.call(), "RuntimeError")
        self.setUp()

        def unreadable():
            raise RuntimeError("native GetID unavailable")

        self.feature.GetID = unreadable
        self.assert_failure(*self.call(), "RuntimeError")

    def test_zero_and_signed_feature_ids_are_not_assumed_positive(self):
        for identity in (0, -1, -(2**31), 2**31 - 1):
            with self.subTest(identity=identity):
                self.feature.feature_id = identity
                result, handles = self.call()
                self.assertTrue(result["ok"], result)
                self.assertEqual(handles, [self.feature])

    def test_empty_part_and_only_non_2d_profiles_return_complete_empty_list(self):
        for first in (
            None,
            FeatureFixture("3d", kind="3DProfileFeature"),
            FeatureFixture("plane", kind="RefPlane"),
        ):
            with self.subTest(first=first):
                self.document.FirstFeature = lambda: first
                result, handles = self.call()
                self.assertEqual(
                    result,
                    {"ok": True, "action": "sketch.list", "sketches": [], "count": 0},
                )
                self.assertEqual(handles, [])

    def test_invalid_max_sketches_fails_before_native_read(self):
        def should_not_read():
            raise AssertionError("invalid limit reached native document")

        self.document.GetType = should_not_read
        for value in (0, -1, True, 1.5, "2", None):
            with self.subTest(limit=value):
                self.assert_failure(*self.call(max_sketches=value), "InvalidArgument")

    def test_limit_exceeded_returns_no_partial_list_or_handles(self):
        second = FeatureFixture("other")
        self.feature.root_next = second
        self.assert_failure(*self.call(max_sketches=1), "SketchListLimitExceeded")

    def test_nonpart_is_rejected_before_traversal(self):
        self.document.GetType = lambda: 2
        self.document.FirstFeature = lambda: self.fail(
            "unsupported document reached traversal"
        )
        self.assert_failure(*self.call(), "UnsupportedDocumentType")

    def test_cycles_in_root_sibling_child_and_subfeature_sibling_chains_fail_closed(
        self,
    ):
        for cycle in ("root", "child", "sub-sibling", "alias-root", "alias-ancestor"):
            with self.subTest(cycle=cycle):
                self.setUp()
                if cycle == "root":
                    self.feature.root_next = self.feature
                elif cycle == "child":
                    self.feature.child = self.feature
                elif cycle == "sub-sibling":
                    child = FeatureFixture("child")
                    self.feature.child = child
                    child.sub_next = child
                elif cycle == "alias-root":
                    self.feature.root_next = FeatureFixture("circle")
                else:
                    self.feature.child = FeatureFixture("circle")
                self.assert_failure(*self.call(), "SketchTraversalCycle")

    def test_traversal_budget_also_bounds_non_sketch_nodes(self):
        nodes = [FeatureFixture(index, kind="FtrFolder") for index in range(4)]
        for first, second in zip(nodes, nodes[1:]):
            first.child = second
        self.document.FirstFeature = lambda: nodes[0]
        with mock.patch.object(windows_sketch_inspection, "_LIST_TRAVERSAL_LIMIT", 3):
            self.assert_failure(*self.call(), "SketchTraversalLimitExceeded")

    def test_deep_native_tree_uses_no_python_recursion(self):
        nodes = [FeatureFixture(index, kind="FtrFolder") for index in range(1200)]
        for first, second in zip(nodes, nodes[1:]):
            first.child = second
        nodes[-1].child = self.feature
        self.document.FirstFeature = lambda: nodes[0]
        result, handles = self.call()
        self.assertTrue(result["ok"])
        self.assertEqual(handles, [self.feature])

    def test_native_metadata_and_owner_read_failures_do_not_publish_partial_handles(
        self,
    ):
        for read in (
            "GetOwnerFeature",
            "GetID",
            "GetSpecificFeature2",
            "GetTypeName2",
            "GetFirstSubFeature",
            "GetNextFeature",
            "constraint",
        ):
            with self.subTest(read=read):
                self.setUp()
                second = FeatureFixture("second")
                self.feature.root_next = second

                def fail():
                    raise RuntimeError("native read failed")

                if read == "constraint":
                    second.sketch.GetConstrainedStatus = fail
                else:
                    setattr(second, read, fail)
                self.assert_failure(*self.call(), "RuntimeError")

    def test_missing_specific_sketch_and_unsupported_identity_fail_closed(self):
        self.feature.sketch = None
        self.assert_failure(*self.call(), "RuntimeError")
        self.setUp()
        self.feature.root_next = FeatureFixture("other")
        self.feature.root_next.feature_id = self.feature.feature_id
        self.app.IsSame = lambda first, second: 2
        self.assert_failure(*self.call(), "RuntimeError")

    def test_native_identity_exception_is_not_swallowed_as_a_distinct_object(self):
        self.feature.root_next = FeatureFixture("other")
        self.feature.root_next.feature_id = self.feature.feature_id

        def fail(first, second):
            raise RuntimeError("native identity unavailable")

        self.app.IsSame = fail
        self.assert_failure(*self.call(), "RuntimeError")

    def test_duplicate_identity_requires_native_enum_not_boolean_or_coercion(self):
        for value in (True, False, "1", "0", 1.0, None):
            with self.subTest(value=value):
                self.setUp()
                self.feature.root_next = FeatureFixture("other")
                self.feature.root_next.feature_id = self.feature.feature_id
                self.app.IsSame = lambda first, second: value
                self.assert_failure(*self.call(), "RuntimeError")


if __name__ == "__main__":
    unittest.main()
