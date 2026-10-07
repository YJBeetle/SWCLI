"""Document-local native IDs bound sketch registration without COM-wide scans."""

from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.daemon.documents import (
    DimensionNotFound,
    DocumentNotFound,
    DocumentRegistry,
    SketchNotFound,
)
from swcli.hosts.windows_sketch_inspection import SketchFeatureIdConflict


class Feature:
    def __init__(self, native_id, *, identity=None):
        self.native_id = native_id
        self.identity = identity if identity is not None else object()
        self.reads = 0
        self.Name = "same name is not native identity"

    def GetID(self):
        self.reads += 1
        return self.native_id


class ComError(Exception):
    def __init__(self, hresult):
        self.hresult = hresult
        super().__init__(hresult)


def document(title):
    return SimpleNamespace(
        GetTitle=lambda: title,
        GetPathName=lambda: "",
        GetType=lambda: 1,
        GetSaveFlag=lambda: False,
        GetUpdateStamp=lambda: 0,
    )


class SketchRegistryTests(unittest.TestCase):
    def setUp(self):
        self.document = document("Part1")
        self.other = document("Part2")
        self.app = SimpleNamespace(
            GetDocuments=lambda: (self.document, self.other),
            IsSame=mock.Mock(
                side_effect=lambda first, second: int(first.identity is second.identity)
            ),
        )
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.document)
        self.other_entry = self.registry.register(self.other)

    def register(self, feature):
        return self.registry.register_sketch(self.entry, feature)

    def state(self):
        return (
            self.entry.sketches.copy(),
            self.entry.sketch_ids_by_native_id.copy(),
            self.entry.dimensions.copy(),
        )

    def test_thousand_new_sketches_use_one_native_read_each_without_com_comparisons(
        self,
    ):
        features = [Feature(index) for index in range(1000)]
        handles = [self.register(feature) for feature in features]
        self.assertEqual(len(set(handles)), 1000)
        self.assertEqual(len(self.entry.sketch_ids_by_native_id), 1000)
        self.assertTrue(all(feature.reads == 1 for feature in features))
        self.app.IsSame.assert_not_called()
        for native_id, handle in enumerate(handles):
            self.assertEqual(self.entry.sketch_ids_by_native_id[native_id], handle)
            self.assertIs(
                self.registry.resolve_sketch(self.entry, handle), features[native_id]
            )

    def test_thousand_repeated_wrappers_use_one_com_comparison_each_and_keep_handles(
        self,
    ):
        originals = [Feature(index) for index in range(1000)]
        handles = [self.register(feature) for feature in originals]
        dimension_id = self.registry.register_dimension(
            self.entry, handles[0], object()
        )
        wrappers = [
            Feature(original.native_id, identity=original.identity)
            for original in originals
        ]
        reused = [self.register(wrapper) for wrapper in wrappers]
        self.assertEqual(reused, handles)
        self.assertEqual(self.app.IsSame.call_count, 1000)
        self.assertTrue(all(wrapper.reads == 1 for wrapper in wrappers))
        self.assertEqual(len(self.entry.sketches), 1000)
        self.assertEqual(self.entry.dimensions[dimension_id].sketch_id, handles[0])
        for handle, wrapper in zip(handles, wrappers):
            self.assertIs(self.entry.sketches[handle], wrapper)

    def test_native_ids_are_document_local_not_names_or_global_identity(self):
        first, second = Feature(1), Feature(2)
        first_id, second_id = self.register(first), self.register(second)
        self.assertNotEqual(first_id, second_id)
        other = Feature(1)
        other_id = self.registry.register_sketch(self.other_entry, other)
        self.assertNotEqual(first_id, other_id)
        self.assertEqual(self.other_entry.sketch_ids_by_native_id, {1: other_id})
        self.app.IsSame.assert_not_called()
        with self.assertRaises(SketchNotFound):
            self.registry.resolve_sketch(self.other_entry, first_id)

    def test_duplicate_id_for_different_native_object_preserves_existing_owner(self):
        original = Feature(1)
        handle = self.register(original)
        self.registry.register_dimension(self.entry, handle, object())
        before = self.state()
        with self.assertRaises(SketchFeatureIdConflict):
            self.register(Feature(1))
        self.assertEqual(self.state(), before)
        self.app.IsSame.assert_called_once()

    def test_python_wrapper_identity_never_bypasses_repeat_native_validation(self):
        original = Feature(1)
        self.register(original)
        before = self.state()
        self.app.IsSame.return_value = 0
        self.app.IsSame.side_effect = None
        with self.assertRaises(SketchFeatureIdConflict):
            self.register(original)
        self.assertEqual(self.state(), before)
        self.app.IsSame.assert_called_once_with(original, original)

    def test_invalid_unavailable_and_failed_incoming_id_reads_do_not_change_state(self):
        original = Feature(1)
        handle = self.register(original)
        self.registry.register_dimension(self.entry, handle, object())
        before = self.state()
        for value in (None, True, 1.5, "1", 2**31, -(2**31) - 1):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.register(Feature(value))
            self.assertEqual(self.state(), before)
        with self.assertRaises(AttributeError):
            self.register(object())
        for hresult in (0x80010108, 0x80010001, 0x80004005):

            def read_error(hresult=hresult):
                raise ComError(hresult)

            with self.subTest(hresult=hresult), self.assertRaises(ComError):
                self.register(SimpleNamespace(GetID=read_error))
            self.assertEqual(self.state(), before)
        self.app.IsSame.assert_not_called()

    def test_busy_unknown_invalid_and_unavailable_com_comparison_preserve_owner(self):
        original = Feature(1)
        handle = self.register(original)
        self.registry.register_dimension(self.entry, handle, object())
        before = self.state()
        for hresult in (0x80010001, 0x80004005):
            self.app.IsSame.side_effect = ComError(hresult)
            with self.subTest(hresult=hresult), self.assertRaises(ComError):
                self.register(Feature(1, identity=original.identity))
            self.assertEqual(self.state(), before)
        self.app.IsSame.side_effect = None
        self.app.IsSame.return_value = 2
        with self.assertRaises(RuntimeError):
            self.register(Feature(1, identity=original.identity))
        self.assertEqual(self.state(), before)
        del self.app.IsSame
        with self.assertRaises(AttributeError):
            self.register(Feature(1, identity=original.identity))
        self.assertEqual(self.state(), before)

    def test_disconnected_previous_proxy_expires_only_its_index_and_dimensions(self):
        old, unaffected = Feature(1), Feature(2)
        old_id, unaffected_id = self.register(old), self.register(unaffected)
        old_dimension = self.registry.register_dimension(self.entry, old_id, object())
        unaffected_dimension = self.registry.register_dimension(
            self.entry, unaffected_id, object()
        )
        self.app.IsSame.side_effect = ComError(-2147417848)
        fresh_wrapper = Feature(1, identity=old.identity)
        new_id = self.register(fresh_wrapper)
        self.assertNotEqual(new_id, old_id)
        self.assertNotIn(old_id, self.entry.sketches)
        self.assertNotIn(old_dimension, self.entry.dimensions)
        self.assertEqual(
            self.entry.sketch_ids_by_native_id, {1: new_id, 2: unaffected_id}
        )
        self.assertIs(self.entry.sketches[new_id], fresh_wrapper)
        self.assertIs(self.entry.sketches[unaffected_id], unaffected)
        self.assertEqual(
            self.entry.dimensions[unaffected_dimension].sketch_id, unaffected_id
        )
        with self.assertRaises(SketchNotFound):
            self.registry.resolve_sketch(self.entry, old_id)
        with self.assertRaises(DimensionNotFound):
            self.registry.resolve_dimension(self.entry, old_dimension)

    def test_close_and_reopen_clear_index_sketches_and_dimension_owners(self):
        sketch_id = self.register(Feature(1))
        dimension_id = self.registry.register_dimension(self.entry, sketch_id, object())
        self.registry.forget(self.entry.document_id)
        self.assertEqual(self.state(), ({}, {}, {}))
        with self.assertRaises(DocumentNotFound):
            self.register(object())
        fresh = self.registry.register(self.document)
        fresh_id = self.registry.register_sketch(fresh, Feature(1))
        self.assertEqual(fresh.sketch_ids_by_native_id, {1: fresh_id})
        with self.assertRaises(SketchNotFound):
            self.registry.resolve_sketch(fresh, sketch_id)
        with self.assertRaises(DimensionNotFound):
            self.registry.resolve_dimension(fresh, dimension_id)

    def test_disconnected_replacement_cannot_immediately_reuse_the_old_handle(self):
        original = Feature(1)
        old_id = self.register(original)
        dimension_id = self.registry.register_dimension(self.entry, old_id, object())
        new_suffix = "111111" if old_id != "s-111111" else "222222"
        self.app.IsSame.side_effect = ComError(-2147417848)
        with mock.patch(
            "swcli.daemon.documents.secrets.choice",
            side_effect=list(old_id[2:] + new_suffix),
        ) as choose:
            replacement_id = self.register(Feature(1, identity=original.identity))
        self.assertEqual(choose.call_count, 12)
        self.assertEqual(replacement_id, "s-" + new_suffix)
        self.assertNotIn(old_id, self.entry.sketches)
        self.assertNotIn(dimension_id, self.entry.dimensions)
        self.assertEqual(self.entry.sketch_ids_by_native_id, {1: replacement_id})
        with self.assertRaises(SketchNotFound):
            self.registry.resolve_sketch(self.entry, old_id)


if __name__ == "__main__":
    unittest.main()
