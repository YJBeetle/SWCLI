"""Read-only discovery reconnects persisted native models to exact sketch handles."""

from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.daemon.documents import DocumentRegistry
from swcli.daemon import operations


class Document:
    GetTitle = lambda self: "Part1"
    GetPathName = lambda self: ""
    GetType = lambda self: 1
    GetSaveFlag = lambda self: False
    GetUpdateStamp = lambda self: 10


class Feature:
    _ids_by_identity = {}

    def __init__(self, identity):
        self.identity = identity
        self.native_id = self._ids_by_identity.setdefault(
            identity, len(self._ids_by_identity)
        )

    def GetID(self):
        return self.native_id


class SketchDiscoveryOperationTests(unittest.TestCase):
    def setUp(self):
        self.target = Document()
        self.other = Document()
        self.other.GetTitle = lambda: "Part2"
        self.app = SimpleNamespace(ActiveDoc=self.other)
        self.app.GetDocuments = lambda: (self.target, self.other)
        self.app.IsSame = lambda first, second: int(
            first is second
            or (
                isinstance(first, Feature)
                and isinstance(second, Feature)
                and first.identity == second.identity
            )
        )
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.target)
        self.other_entry = self.registry.register(self.other)
        self.registry.set_current(self.other_entry, session_id="observer")
        self.registry.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)

    def call(self, values=None, **context):
        return operations.execute_operation(
            self.app,
            "sketch.list",
            values or {},
            documents=self.registry,
            document_id=self.entry.document_id,
            session_id="observer",
            **context,
        )

    @mock.patch(
        "swcli.hosts.windows_sketch_inspection.list_sketches_windows_with_handles"
    )
    def test_background_leased_discovery_keeps_stamp_foreground_and_current(
        self, discover
    ):
        features = [Feature("one"), Feature("two")]
        discover.return_value = (
            {
                "ok": True,
                "action": "sketch.list",
                "count": 2,
                "sketches": [{"name": "one"}, {"name": "two"}],
            },
            features,
        )
        with mock.patch.object(self.registry, "temporarily_activate") as activate:
            result = self.call({"max_sketches": 10}, expected_update_stamp=10)
        activate.assert_not_called()
        discover.assert_called_once_with(
            app=self.app, document=self.target, max_sketches=10
        )
        self.assertFalse(result["document"]["active"] or result["document"]["current"])
        self.assertEqual(result["document"]["update_stamp"], 10)
        for descriptor, feature in zip(result["sketches"], features):
            self.assertIs(
                self.registry.resolve_sketch(self.entry, descriptor["sketch_id"]),
                feature,
            )
        self.assertIs(self.app.ActiveDoc, self.other)
        self.assertIs(
            self.registry.resolve(None, session_id="observer"), self.other_entry
        )

    @mock.patch(
        "swcli.hosts.windows_sketch_inspection.list_sketches_windows_with_handles"
    )
    def test_repeat_native_wrappers_reuse_ids_and_dimension_owner(self, discover):
        initial = Feature("one")
        sketch_id = self.registry.register_sketch(self.entry, initial)
        dimension_id = self.registry.register_dimension(self.entry, sketch_id, object())
        for _ in range(2):
            wrapper = Feature("one")
            discover.return_value = (
                {
                    "ok": True,
                    "action": "sketch.list",
                    "count": 1,
                    "sketches": [{"name": "one"}],
                },
                [wrapper],
            )
            result = self.call()
            self.assertEqual(result["sketches"][0]["sketch_id"], sketch_id)
            self.assertIs(self.registry.resolve_sketch(self.entry, sketch_id), wrapper)
            self.assertEqual(
                self.registry.resolve_dimension(self.entry, dimension_id).sketch_id,
                sketch_id,
            )
        self.assertEqual(len(self.entry.sketches), 1)

    @mock.patch(
        "swcli.hosts.windows_sketch_inspection.list_sketches_windows_with_handles"
    )
    def test_stale_stamp_and_invalid_limit_fail_before_adapter(self, discover):
        with self.assertRaises(operations.DocumentUpdateConflict):
            self.call(expected_update_stamp=11)
        for limit in (0, -1, True, "10"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.call({"max_sketches": limit})
        discover.assert_not_called()

    @mock.patch(
        "swcli.hosts.windows_sketch_inspection.list_sketches_windows_with_handles"
    )
    def test_failed_discovery_never_registers_partial_handles(self, discover):
        discover.return_value = (
            {
                "ok": False,
                "action": "sketch.list",
                "error": {"type": "SketchListLimitExceeded", "message": "limit"},
            },
            [Feature("one")],
        )
        result = self.call()
        self.assertFalse(result["ok"])
        self.assertEqual(self.entry.sketches, {})

    @mock.patch(
        "swcli.hosts.windows_sketch_inspection.list_sketches_windows_with_handles"
    )
    def test_inconsistent_native_results_publish_no_handles(self, discover):
        for count, descriptors, handles in (
            (1, [{"name": "one"}], []),
            (2, [{"name": "one"}], [Feature("one")]),
            (1, [{"name": "one"}], [None]),
        ):
            with self.subTest(count=count, handles=handles):
                discover.return_value = (
                    {
                        "ok": True,
                        "action": "sketch.list",
                        "count": count,
                        "sketches": descriptors,
                    },
                    handles,
                )
                with self.assertRaises(RuntimeError):
                    self.call()
                self.assertEqual(self.entry.sketches, {})

    def test_stale_sketch_proxy_drops_only_its_dimensions(self):
        class ComError(Exception):
            hresult = 0x80010108

        stale = Feature("stale")
        old_id = self.registry.register_sketch(self.entry, stale)
        dimension_id = self.registry.register_dimension(self.entry, old_id, object())
        self.app.IsSame = mock.Mock(side_effect=ComError("disconnected"))
        replacement = Feature("replacement")
        replacement.native_id = stale.native_id
        new_id = self.registry.register_sketch(self.entry, replacement)
        self.assertNotEqual(old_id, new_id)
        self.assertNotIn(old_id, self.entry.sketches)
        self.assertNotIn(dimension_id, self.entry.dimensions)

    def test_busy_unknown_sketch_proxy_preserves_handles(self):
        class ComError(Exception):
            def __init__(self, hresult):
                self.hresult = hresult

        for hresult in (0x80010001, 0x80004005):
            with self.subTest(hresult=hresult):
                self.setUp()
                feature = Feature("one")
                sketch_id = self.registry.register_sketch(self.entry, feature)
                dimension = object()
                dimension_id = self.registry.register_dimension(
                    self.entry, sketch_id, dimension
                )
                self.app.IsSame = mock.Mock(side_effect=ComError(hresult))
                with self.assertRaises(ComError):
                    self.registry.register_sketch(self.entry, Feature("one"))
                self.assertIs(self.entry.sketches[sketch_id], feature)
                self.assertIs(self.entry.dimensions[dimension_id].dimension, dimension)


if __name__ == "__main__":
    unittest.main()
