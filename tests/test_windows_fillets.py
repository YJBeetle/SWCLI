import unittest
from contextlib import ExitStack
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from swcli.hosts import windows_fillets as module
from swcli.hosts.windows_edge_observation import EdgeBinding


class FilletTests(unittest.TestCase):
    def run_case(self, *, initial_selection=0, create_error=None, access_error=None,
                 release_error=None, radius=2, unhealthy=False, unchanged=False,
                 wrong_target=False, restoration=False, missing=False):
        edge, body = object(), object()
        binding = EdgeBinding(edge, body, b"edge")
        selection = NS(GetSelectedObjectCount2=Mock(return_value=initial_selection),
                       CreateSelectData=NS(Mark=0), GetSelectedObject6=lambda *a: edge)
        edge = NS(Select4=Mock(side_effect=lambda *a: selection.GetSelectedObjectCount2.configure_mock(return_value=1) or True))
        binding = EdgeBinding(edge, body, b"edge")
        selection.GetSelectedObject6 = lambda *a: edge
        data = NS(Initialize=lambda value: True, DefaultRadius=.002,
                  ConicTypeForCrossSectionProfile=0, PropagateToTangentFaces=False,
                  AccessSelections=Mock(side_effect=access_error, return_value=True),
                  ReleaseSelectionAccess=Mock(side_effect=release_error),
                  Edges=[object() if wrong_target else edge])
        release = data.ReleaseSelectionAccess
        data.ReleaseSelectionAccess = lambda: release()
        data.release_mock = release
        feature = NS(Name="Fillet1", GetTypeName2="Fillet", GetDefinition=data)
        manager = NS(CreateDefinition=lambda value: data,
                     CreateFeature=Mock(side_effect=create_error, return_value=None if missing else feature))
        document = NS(IsOpenedReadOnly=False, IsOpenedViewOnly=False,
                      GetConfigurationNames=["Default"], GetConfigurationCount=1,
                      SelectionManager=selection, Extension=object(), FeatureManager=manager,
                      EditRebuild3=True)
        document.ClearSelection2 = Mock(side_effect=lambda *a: selection.GetSelectedObjectCount2.configure_mock(return_value=0))
        app = object()
        state = dict(configuration="Default", update_stamp=1, editing=False)
        states = [(state, None, document), (dict(state, configuration="Other") if restoration else state, None, document)]
        with ExitStack() as stack:
            for name, value in {
                "_state": Mock(side_effect=states), "_same": lambda a, b, c: b is c,
                "_identical": lambda a, b, c: b is c,
                "_running_command": lambda a: dict(ui_active=False),
                "observe_part_edges_with_handles": lambda *a: (dict(ok=True), [binding]),
                "capture_verified_reference": lambda a, e, item: b"edge" if item is edge else b"wrong",
                "_volume": Mock(side_effect=[12000., 12000. if unchanged else 11991.]),
                "_diagnose_features": lambda *a: dict(healthy=not unhealthy, truncated=False),
                "_null_dispatch": lambda: None,
            }.items():
                stack.enter_context(patch.object(module, name, value))
            result, returned = module.create_edge_fillet_windows_with_handle(
                app=app, document=document, binding=binding, radius_mm=radius)
        return result, returned, feature, data, manager, document

    def test_success_retains_exact_feature(self):
        result, returned, feature, data, *_ = self.run_case()
        self.assertTrue(result["ok"], result)
        self.assertIs(returned, feature)
        self.assertTrue(result["rebuilt"])
        data.release_mock.assert_called_once()

    def test_invalid_radius_never_mutates(self):
        for radius in (False, 0, -1, float("nan"), float("inf")):
            result, _, _, _, manager, _ = self.run_case(radius=radius)
            self.assertFalse(result["ok"])
            manager.CreateFeature.assert_not_called()

    def test_existing_selection_untouched(self):
        result, _, _, _, manager, document = self.run_case(initial_selection=1)
        self.assertFalse(result["ok"])
        manager.CreateFeature.assert_not_called()
        document.ClearSelection2.assert_not_called()

    def test_creation_exception_records_possible_mutation(self):
        result, returned, *_ = self.run_case(create_error=RuntimeError("first error"))
        self.assertIsNone(returned)
        self.assertTrue(result["mutation"]["may_have_changed"])
        self.assertIn("first error", result["error"]["message"])

    def test_null_creation_is_not_success(self):
        result, returned, *_ = self.run_case(missing=True)
        self.assertFalse(result["ok"])
        self.assertIsNone(returned)

    def test_access_throw_still_releases_retains_first_error(self):
        result, returned, feature, data, *_ = self.run_case(
            access_error=RuntimeError("access failed"), release_error=RuntimeError("release failed"))
        self.assertIs(returned, feature)
        self.assertIn("access failed", result["error"]["message"])
        self.assertEqual(result["cleanup_errors"][0]["stage"], "ReleaseSelectionAccess")
        data.release_mock.assert_called_once()

    def test_wrong_target_unhealthy_or_unchanged_fail_closed(self):
        for option in ("wrong_target", "unhealthy", "unchanged", "restoration"):
            result, returned, feature, *_ = self.run_case(**{option: True})
            self.assertFalse(result["ok"], (option, result))
            self.assertIs(returned, feature)


if __name__ == "__main__":
    unittest.main()
