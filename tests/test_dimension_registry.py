"""Worker-local dimension handles retain exact owner and document boundaries."""

import unittest
from types import SimpleNamespace
from unittest import mock

from swcli.daemon.documents import (
    DimensionNotFound,
    DocumentNotFound,
    DocumentRegistry,
    SketchNotFound,
)


class Document:
    def __init__(self, title, path=""):
        self.title, self.path = title, path

    def GetTitle(self):
        return self.title

    def GetPathName(self):
        return self.path

    def GetType(self):
        return 1

    def GetSaveFlag(self):
        return False


class Dimension:
    def __init__(self, *, identity=None):
        self.identity = identity if identity is not None else object()

    @property
    def FullName(self):
        raise AssertionError("a dimension name must not be used for registry identity")

    def GetFeatureOwner(self):
        raise AssertionError("partial creation registration must not read native owner")


class ComError(Exception):
    def __init__(self, hresult):
        self.hresult = hresult
        super().__init__(hresult)


class DimensionRegistryTests(unittest.TestCase):
    def setUp(self):
        self.document = Document("Part1")
        self.other = Document("Part2")
        self.app = mock.Mock()
        self.app.GetDocuments = lambda: (self.document, self.other)
        self.app.IsSame.side_effect = lambda first, second: int(
            getattr(first, "identity", first) is getattr(second, "identity", second)
        )
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.document)
        self.other_entry = self.registry.register(self.other)
        self.sketch = SimpleNamespace(GetID=lambda: 1)
        self.sketch_id = self.registry.register_sketch(self.entry, self.sketch)
        self.dimension = Dimension()
        self.dimension_id = self.registry.register_dimension(
            self.entry, self.sketch_id, self.dimension
        )

    def state(self):
        return (
            {
                dimension_id: (item.sketch_id, item.dimension)
                for dimension_id, item in self.entry.dimensions.items()
            },
            {
                sketch_id: {
                    dimension_id: (item.sketch_id, item.dimension)
                    for dimension_id, item in dimensions.items()
                }
                for sketch_id, dimensions in self.entry.dimensions_by_sketch.items()
            },
        )

    def test_short_id_preserves_exact_native_dimension_and_sketch(self):
        self.assertRegex(self.dimension_id, r"^m-[0-9a-hjkmnp-tv-z]{6}$")
        item = self.registry.resolve_dimension(self.entry, self.dimension_id)
        self.assertIs(item.dimension, self.dimension)
        self.assertEqual(item.sketch_id, self.sketch_id)
        self.assertIs(
            self.registry.resolve_sketch(self.entry, item.sketch_id), self.sketch
        )
        self.assertIs(
            self.entry.dimensions_by_sketch[self.sketch_id][self.dimension_id], item
        )

    def test_repeated_native_dimension_wrapper_reuses_id_and_refreshes_exact_proxy(
        self,
    ):
        wrapper = Dimension(identity=self.dimension.identity)
        reused = self.registry.register_dimension(self.entry, self.sketch_id, wrapper)
        self.assertEqual(reused, self.dimension_id)
        self.assertIs(self.entry.dimensions[reused].dimension, wrapper)
        self.assertIs(
            self.entry.dimensions_by_sketch[self.sketch_id][reused],
            self.entry.dimensions[reused],
        )
        self.app.IsSame.assert_called_once_with(self.dimension, wrapper)
        self.assertEqual(len(self.entry.dimensions), 1)

    def test_python_wrapper_identity_does_not_bypass_native_comparison(self):
        self.app.IsSame.side_effect = None
        self.app.IsSame.return_value = 0
        new_id = self.registry.register_dimension(
            self.entry, self.sketch_id, self.dimension
        )
        self.assertNotEqual(new_id, self.dimension_id)
        self.app.IsSame.assert_called_once_with(self.dimension, self.dimension)
        self.assertEqual(len(self.entry.dimensions_by_sketch[self.sketch_id]), 2)

    def test_unsupported_native_comparison_uses_canonical_identity_for_reuse(self):
        self.app.IsSame.side_effect = None
        self.app.IsSame.return_value = 2
        with mock.patch(
            "swcli.hosts.windows_dimension_identity._query_iunknown",
            side_effect=lambda dimension: dimension.identity,
        ):
            second = Dimension()
            second_id = self.registry.register_dimension(
                self.entry, self.sketch_id, second
            )
            self.assertNotEqual(second_id, self.dimension_id)
            wrapper = Dimension(identity=second.identity)
            self.assertEqual(
                self.registry.register_dimension(self.entry, self.sketch_id, wrapper),
                second_id,
            )
            self.assertIs(self.entry.dimensions[second_id].dimension, wrapper)
            self.assertEqual(len(self.entry.dimensions), 2)

    def test_unsupported_query_failure_preserves_all_registry_handles(self):
        before = self.state()
        self.app.IsSame.side_effect = None
        self.app.IsSame.return_value = 2
        for failure in (ComError(0x80010001), RuntimeError("unreadable identity")):
            with self.subTest(failure=failure), mock.patch(
                "swcli.hosts.windows_dimension_identity._query_iunknown",
                side_effect=failure,
            ):
                with self.assertRaises(RuntimeError) as caught:
                    self.registry.register_dimension(
                        self.entry, self.sketch_id, Dimension()
                    )
                self.assertIs(caught.exception.__cause__, failure)
                self.assertEqual(self.state(), before)

    def test_candidate_query_disconnect_does_not_expire_registered_proxy(self):
        before = self.state()
        self.app.IsSame.side_effect = None
        self.app.IsSame.return_value = 2
        failure = ComError(0x80010108)
        with mock.patch(
            "swcli.hosts.windows_dimension_identity._query_iunknown",
            side_effect=[self.dimension.identity, failure],
        ):
            with self.assertRaises(RuntimeError) as caught:
                self.registry.register_dimension(
                    self.entry, self.sketch_id, Dimension()
                )
            self.assertIs(caught.exception.__cause__, failure)
        self.assertEqual(self.state(), before)

    def test_different_native_dimensions_in_one_owner_do_not_reuse_by_name(self):
        second = Dimension()
        second_id = self.registry.register_dimension(self.entry, self.sketch_id, second)
        self.assertNotEqual(second_id, self.dimension_id)
        self.app.IsSame.assert_called_once_with(self.dimension, second)
        self.app.IsSame.reset_mock()
        wrapper = Dimension(identity=second.identity)
        self.assertEqual(
            self.registry.register_dimension(self.entry, self.sketch_id, wrapper),
            second_id,
        )
        self.assertEqual(self.app.IsSame.call_count, 2)
        self.assertEqual(len(self.entry.dimensions_by_sketch[self.sketch_id]), 2)

    def test_owner_and_document_buckets_are_separate_even_for_same_native_proxy(self):
        another_sketch = self.registry.register_sketch(
            self.entry, SimpleNamespace(GetID=lambda: 2)
        )
        other_sketch = self.registry.register_sketch(
            self.other_entry, SimpleNamespace(GetID=lambda: 1)
        )
        another_id = self.registry.register_dimension(
            self.entry, another_sketch, self.dimension
        )
        other_id = self.registry.register_dimension(
            self.other_entry, other_sketch, self.dimension
        )
        self.assertEqual(len({self.dimension_id, another_id, other_id}), 3)
        self.assertEqual(
            set(self.entry.dimensions_by_sketch), {self.sketch_id, another_sketch}
        )
        self.assertEqual(set(self.other_entry.dimensions_by_sketch), {other_sketch})
        self.app.IsSame.assert_not_called()

    def test_thousand_owners_avoid_global_pairs_and_repeat_once_per_owner(self):
        registry = DocumentRegistry(self.app)
        entry = registry.register(self.document)
        sketches = [
            registry.register_sketch(entry, SimpleNamespace(GetID=lambda i=i: i))
            for i in range(1000)
        ]
        originals = [Dimension() for _ in sketches]
        handles = [
            registry.register_dimension(entry, sketch, dimension)
            for sketch, dimension in zip(sketches, originals)
        ]
        self.app.IsSame.assert_not_called()
        self.assertEqual(len(set(handles)), 1000)
        wrappers = [Dimension(identity=original.identity) for original in originals]
        self.assertEqual(
            [
                registry.register_dimension(entry, sketch, wrapper)
                for sketch, wrapper in zip(sketches, wrappers)
            ],
            handles,
        )
        self.assertEqual(self.app.IsSame.call_count, 1000)
        self.app.IsSame.reset_mock()
        distinct = [Dimension() for _ in sketches]
        new_handles = [
            registry.register_dimension(entry, sketch, dimension)
            for sketch, dimension in zip(sketches, distinct)
        ]
        self.assertEqual(self.app.IsSame.call_count, 1000)
        self.assertFalse(set(handles) & set(new_handles))
        self.assertTrue(
            all(
                len(dimensions) == 2
                for dimensions in entry.dimensions_by_sketch.values()
            )
        )

    def test_busy_unknown_and_invalid_native_comparisons_preserve_registry(self):
        before = self.state()
        wrapper = Dimension(identity=self.dimension.identity)
        for hresult in (0x80010001, 0x8001010A, 0x80004005):
            self.app.IsSame.side_effect = ComError(hresult)
            with self.subTest(hresult=hresult), self.assertRaises(ComError):
                self.registry.register_dimension(self.entry, self.sketch_id, wrapper)
            self.assertEqual(self.state(), before)
        self.app.IsSame.side_effect = None
        for status in (-1, 2, None, True, 1.5, "1"):
            self.app.IsSame.return_value = status
            with self.subTest(status=status), self.assertRaises(RuntimeError):
                self.registry.register_dimension(self.entry, self.sketch_id, wrapper)
            self.assertEqual(self.state(), before)
        del self.app.IsSame
        with self.assertRaises(AttributeError):
            self.registry.register_dimension(self.entry, self.sketch_id, wrapper)
        self.assertEqual(self.state(), before)

    def test_disconnected_old_proxy_expires_only_its_dimension_not_other_owners(self):
        for hresult in (-2147417848, 0x800401FD):
            with self.subTest(hresult=hresult):
                self.setUp()
                live = Dimension()
                live_id = self.registry.register_dimension(
                    self.entry, self.sketch_id, live
                )
                other_sketch = self.registry.register_sketch(
                    self.entry, SimpleNamespace(GetID=lambda: 2)
                )
                other = Dimension()
                other_id = self.registry.register_dimension(
                    self.entry, other_sketch, other
                )
                wrapper = Dimension(identity=live.identity)

                def compare(first, second):
                    if first is self.dimension:
                        raise ComError(hresult)
                    return int(first.identity is second.identity)

                self.app.IsSame.side_effect = compare
                self.assertEqual(
                    self.registry.register_dimension(
                        self.entry, self.sketch_id, wrapper
                    ),
                    live_id,
                )
                self.assertNotIn(self.dimension_id, self.entry.dimensions)
                self.assertEqual(
                    set(self.entry.dimensions_by_sketch[self.sketch_id]), {live_id}
                )
                self.assertIs(self.entry.dimensions[live_id].dimension, wrapper)
                self.assertIs(self.entry.dimensions[other_id].dimension, other)
                self.assertEqual(
                    set(self.entry.dimensions_by_sketch[other_sketch]), {other_id}
                )
                self.assertIs(self.entry.sketches[self.sketch_id], self.sketch)
                with self.assertRaises(DimensionNotFound):
                    self.registry.resolve_dimension(self.entry, self.dimension_id)

    def test_later_com_failure_does_not_apply_staged_disconnected_cleanup(self):
        self.registry.register_dimension(self.entry, self.sketch_id, Dimension())
        before = self.state()
        for failure in (ComError(0x80010001), ComError(0x80004005), 2):
            self.app.IsSame.side_effect = [ComError(0x80010108), failure]
            error = ComError if isinstance(failure, ComError) else RuntimeError
            with self.subTest(failure=failure), self.assertRaises(error):
                self.registry.register_dimension(
                    self.entry, self.sketch_id, Dimension()
                )
            self.assertEqual(self.state(), before)

    def test_disconnected_replacement_cannot_immediately_reuse_expired_id(self):
        self.app.IsSame.side_effect = ComError(0x80010108)
        new_suffix = "111111" if self.dimension_id != "m-111111" else "222222"
        with mock.patch(
            "swcli.daemon.documents.secrets.choice",
            side_effect=list(self.dimension_id[2:] + new_suffix),
        ) as choose:
            replacement_id = self.registry.register_dimension(
                self.entry, self.sketch_id, Dimension()
            )
        self.assertEqual(choose.call_count, 12)
        self.assertEqual(replacement_id, "m-" + new_suffix)
        self.assertNotIn(self.dimension_id, self.entry.dimensions)
        self.assertEqual(
            set(self.entry.dimensions_by_sketch[self.sketch_id]), {replacement_id}
        )
        with self.assertRaises(DimensionNotFound):
            self.registry.resolve_dimension(self.entry, self.dimension_id)

    def test_token_allocation_failure_does_not_apply_staged_cleanup(self):
        before = self.state()
        self.app.IsSame.side_effect = ComError(0x80010108)
        with (
            mock.patch(
                "swcli.daemon.documents.secrets.choice",
                side_effect=RuntimeError("entropy"),
            ),
            self.assertRaisesRegex(RuntimeError, "entropy"),
        ):
            self.registry.register_dimension(self.entry, self.sketch_id, Dimension())
        self.assertEqual(self.state(), before)

    def test_disconnected_sketch_replacement_clears_only_its_dimension_bucket(self):
        other_sketch = self.registry.register_sketch(
            self.entry, SimpleNamespace(GetID=lambda: 2)
        )
        other_dimension = Dimension()
        other_id = self.registry.register_dimension(
            self.entry, other_sketch, other_dimension
        )
        self.app.IsSame.side_effect = ComError(0x80010108)
        replacement = self.registry.register_sketch(
            self.entry, SimpleNamespace(GetID=lambda: 1)
        )
        self.assertNotEqual(replacement, self.sketch_id)
        self.assertNotIn(self.sketch_id, self.entry.dimensions_by_sketch)
        self.assertNotIn(self.dimension_id, self.entry.dimensions)
        self.assertEqual(set(self.entry.dimensions_by_sketch), {other_sketch})
        self.assertIs(self.entry.dimensions[other_id].dimension, other_dimension)
        self.assertEqual(set(self.entry.dimensions_by_sketch[other_sketch]), {other_id})

    def test_handle_never_resolves_in_another_document(self):
        with self.assertRaises(DimensionNotFound):
            self.registry.resolve_dimension(self.other_entry, self.dimension_id)
        with self.assertRaises(SketchNotFound):
            self.registry.register_dimension(self.other_entry, self.sketch_id, object())

    def test_absent_native_handle_and_unknown_sketch_are_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.register_dimension(self.entry, self.sketch_id, None)
        with self.assertRaises(SketchNotFound):
            self.registry.register_dimension(self.entry, "s-000000", object())

    def test_close_reopen_invalidates_old_handles(self):
        self.registry.forget(self.entry.document_id)
        self.assertFalse(self.entry.dimensions or self.entry.sketches)
        self.assertFalse(self.entry.dimensions_by_sketch)
        with self.assertRaises(DimensionNotFound):
            self.registry.resolve_dimension(self.entry, self.dimension_id)
        with self.assertRaises(DocumentNotFound):
            self.registry.register_sketch(self.entry, object())
        replacement = self.registry.register(self.document)
        self.assertNotEqual(replacement.document_id, self.entry.document_id)
        self.assertFalse(replacement.dimensions_by_sketch)
        with self.assertRaises(DimensionNotFound):
            self.registry.resolve_dimension(replacement, self.dimension_id)

    def test_save_as_keeps_live_handle_owner_session_and_lease(self):
        self.registry.set_current(self.entry, session_id="writer")
        lease = self.registry.acquire_lease(
            self.entry, session_id="writer", ttl_seconds=60
        )
        self.document.title = "Saved.SLDPRT"
        self.document.path = r"C:\Workspace\Saved.SLDPRT"
        self.registry.refresh_key(self.entry)
        self.registry.sync()
        self.assertEqual(
            set(self.entry.dimensions_by_sketch[self.sketch_id]), {self.dimension_id}
        )
        self.assertIs(self.registry.resolve(None, session_id="writer"), self.entry)
        self.assertIs(
            self.registry.resolve_dimension(self.entry, self.dimension_id).dimension,
            self.dimension,
        )
        self.assertEqual(
            self.registry.active_lease(self.entry)["lease_id"], lease["lease_id"]
        )

    def test_external_close_and_worker_replacement_drop_dimension_handles(self):
        self.app.GetDocuments = lambda: (self.other,)
        self.registry.sync()
        self.assertFalse(self.entry.dimensions_by_sketch)
        with self.assertRaises(DimensionNotFound):
            self.registry.resolve_dimension(self.entry, self.dimension_id)
        replacement = DocumentRegistry(self.app)
        new_entry = replacement.register(self.document)
        with self.assertRaises(DimensionNotFound):
            replacement.resolve_dimension(new_entry, self.dimension_id)

    def test_external_reopen_with_same_path_expires_handles_and_lease(self):
        self.document.path = r"C:\Workspace\Same.SLDPRT"
        self.registry.refresh_key(self.entry)
        self.registry.set_current(self.entry, session_id="writer")
        self.registry.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)
        reopened = Document("Same.SLDPRT", self.document.path)
        self.app.IsSame = lambda first, second: 1 if first is second else 0
        self.app.GetDocuments = lambda: (reopened, self.other)
        self.registry.sync()
        replacement = self.registry.register(reopened)
        self.assertNotEqual(replacement.document_id, self.entry.document_id)
        self.assertFalse(self.entry.dimensions or self.entry.sketches)
        self.assertFalse(self.entry.dimensions_by_sketch)
        self.assertIsNone(self.registry.active_lease(replacement))
        with self.assertRaises(DimensionNotFound):
            self.registry.resolve_dimension(replacement, self.dimension_id)

    def test_another_com_wrapper_for_same_native_document_keeps_handles(self):
        wrapper = Document(self.document.title)
        self.app.IsSame = lambda first, second: 1
        registered = self.registry.register(wrapper)
        self.assertIs(registered, self.entry)
        self.assertIs(registered.document, wrapper)
        self.assertIs(
            self.registry.resolve_dimension(registered, self.dimension_id).dimension,
            self.dimension,
        )

    def test_known_disconnected_proxy_expires_but_busy_and_unknown_preserve_state(self):
        class ComError(Exception):
            def __init__(self, hresult):
                self.hresult = hresult
                super().__init__(hresult)

        for hresult, disconnected in (
            (-2147417848, True),
            (0x800401FD, True),
            (0x80010001, False),
            (0x80004005, False),
        ):
            with self.subTest(hresult=hresult):
                self.setUp()
                wrapper = Document(self.document.title)
                self.app.IsSame = mock.Mock(side_effect=ComError(hresult))
                if disconnected:
                    replacement = self.registry.register(wrapper)
                    self.assertNotEqual(replacement.document_id, self.entry.document_id)
                    self.assertFalse(self.entry.dimensions)
                else:
                    with self.assertRaises(ComError):
                        self.registry.register(wrapper)
                    self.assertIs(
                        self.registry.resolve_dimension(
                            self.entry, self.dimension_id
                        ).dimension,
                        self.dimension,
                    )


if __name__ == "__main__":
    unittest.main()
