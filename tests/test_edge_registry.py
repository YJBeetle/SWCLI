"""Faces and edges share scope/lifetime, never type or complete-set identity."""

from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.daemon.documents import DocumentRegistry
from swcli.daemon.entities import (
    EntityRegistry, EntityBindingConflict, EntityNotFound, EntityReferenceStale,
)
from swcli.hosts.windows_edge_observation import EdgeBinding
from swcli.hosts.windows_entity_observation import FaceBinding


class EdgeRegistryTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(IsSame=lambda first, second: int(first is second))
        self.issued = set()
        self.registry = EntityRegistry(self.app, "d-first", issued_ids=self.issued)
        self.body = object()
        self.edges = [EdgeBinding(object(), self.body, b"edge" + bytes((i,))) for i in range(3)]
        self.faces = [FaceBinding(object(), self.body, b"face" + bytes((i,))) for i in range(2)]

    def register(self, bindings=None, *, kind="edge", stamp=12, configuration="default"):
        method = self.registry.register_edges if kind == "edge" else self.registry.register_faces
        values = self.edges if kind == "edge" else self.faces
        return method(values if bindings is None else bindings,
                      configuration=configuration, update_stamp=stamp)

    def resolve(self, token, *, kind="edge", stamp=12, configuration="default"):
        return self.registry.resolve(token, kind=kind, configuration=configuration, update_stamp=stamp)

    def snapshot(self):
        return self.registry._entries.copy(), self.registry._complete_kinds.copy(), self.issued.copy()

    def test_short_edges_and_faces_coexist_and_repeat_per_complete_kind(self):
        face_ids = self.register(kind="face")
        edge_ids = self.register()
        self.assertTrue(set(face_ids).isdisjoint(edge_ids))
        self.assertEqual(self.registry._complete_kinds, {"face", "edge"})
        self.assertEqual(self.issued, set(face_ids + edge_ids))
        self.assertEqual(self.register(), edge_ids)
        self.assertEqual(self.register(kind="face"), face_ids)
        self.assertEqual(self.register(list(reversed(self.edges))), list(reversed(edge_ids)))
        for token, binding in zip(edge_ids, self.edges):
            self.assertRegex(token, r"^e-[a-z0-9]{6}$")
            self.assertIs(self.resolve(token).binding, binding)
            self.assertEqual(self.resolve(token).kind, "edge")
        self.assertEqual(self.resolve(face_ids[0], kind="face").kind, "face")

    def test_other_kind_tokens_and_default_face_resolver_never_coerce_edges(self):
        edge = self.register()[0]
        face = self.register(kind="face")[0]
        with self.assertRaises(EntityNotFound):
            self.resolve(edge, kind="face")
        with self.assertRaises(EntityNotFound):
            self.resolve(face)
        with self.assertRaises(EntityNotFound):
            self.registry.resolve(edge, configuration="default", update_stamp=12)
        with self.assertRaises(EntityBindingConflict):
            self.resolve(edge, kind="vertex")
        other = EntityRegistry(self.app, "d-other", issued_ids=self.issued)
        with self.assertRaises(EntityNotFound):
            other.resolve(edge, kind="edge", configuration="default", update_stamp=12)

    def test_scope_change_seen_by_either_kind_permanently_retires_both(self):
        for change in ({"stamp": 13}, {"configuration": "other"}):
            with self.subTest(change=change):
                self.registry = EntityRegistry(self.app, "d-first", issued_ids=self.issued)
                old_face = self.register(kind="face")
                old_edge = self.register()
                new_face = self.register(kind="face", **change)
                self.assertTrue(set(new_face).isdisjoint(old_face + old_edge))
                for kind, tokens in (("face", old_face), ("edge", old_edge)):
                    for token in tokens:
                        with self.assertRaises(EntityReferenceStale):
                            self.resolve(token, kind=kind, **change)
                        with self.assertRaises(EntityReferenceStale):
                            self.resolve(token, kind=kind)
                new_edge = self.register()
                self.assertTrue(set(new_edge).isdisjoint(old_face + old_edge + new_face))

    def test_scope_only_observation_retires_every_kind_without_native_calls(self):
        face_ids, edge_ids = self.register(kind="face"), self.register()
        issued = self.issued.copy()
        self.app.IsSame = mock.Mock(side_effect=AssertionError("scope check is not COM"))
        self.registry.observe_scope(configuration="other", update_stamp=12)
        self.registry.observe_scope(configuration="default", update_stamp=12)
        self.assertEqual(self.registry._complete_kinds, set())
        for kind, tokens in (("face", face_ids), ("edge", edge_ids)):
            with self.assertRaises(EntityReferenceStale):
                self.resolve(tokens[0], kind=kind)
        self.app.IsSame.assert_not_called()
        self.assertEqual(self.issued, issued)

    def test_new_kind_with_foreign_body_or_cross_kind_reference_is_rejected(self):
        face_ids = self.register(kind="face")
        before = self.snapshot()
        for edge in (EdgeBinding(object(), object(), b"edge"),
                     EdgeBinding(object(), self.body, self.faces[0].reference)):
            with self.subTest(edge=edge), self.assertRaises(EntityBindingConflict):
                self.register([edge])
            self.assertEqual(self.snapshot(), before)
        self.assertIs(self.resolve(face_ids[0], kind="face").binding, self.faces[0])

    def test_wrong_binding_kind_or_malformed_edge_cannot_issue_or_retire_tokens(self):
        self.register(kind="face")
        self.register()
        before = self.snapshot()
        for bindings in (self.faces, [None], [], self.edges * 22,
                         [EdgeBinding(None, self.body, b"x")],
                         [EdgeBinding(object(), None, b"x")],
                         [EdgeBinding(object(), self.body, b"")],
                         [EdgeBinding(object(), self.body, bytearray(b"x"))],
                         [EdgeBinding(object(), self.body, b"x" * 65537)]):
            with self.subTest(bindings=type(bindings).__name__), self.assertRaises(EntityBindingConflict):
                self.register(bindings)
            self.assertEqual(self.snapshot(), before)
        with self.assertRaises(EntityBindingConflict):
            self.register(self.edges, kind="face")
        self.assertEqual(self.snapshot(), before)

    def test_incomplete_or_replaced_same_scope_edge_batch_preserves_both_kinds(self):
        face_ids, edge_ids = self.register(kind="face"), self.register()
        before = self.snapshot()
        replacements = [EdgeBinding(object(), self.body, binding.reference) for binding in self.edges]
        for bindings in (self.edges[:-1], replacements, [self.edges[0], self.edges[0]],
                         [self.edges[0], EdgeBinding(object(), self.body, self.edges[0].reference)],
                         [EdgeBinding(binding.edge, object(), binding.reference) for binding in self.edges]):
            with self.subTest(bindings=bindings), self.assertRaises(EntityBindingConflict):
                self.register(bindings)
            self.assertEqual(self.snapshot(), before)
        self.assertIs(self.resolve(face_ids[0], kind="face").binding, self.faces[0])
        self.assertIs(self.resolve(edge_ids[0]).binding, self.edges[0])

    def test_fresh_wrappers_reuse_only_exact_native_edges_with_new_private_bytes(self):
        original = self.register()
        replacements = [EdgeBinding(object(), self.body, b"new" + b.reference) for b in self.edges]
        mapping = {id(a.edge): id(b.edge) for a, b in zip(self.edges, replacements)}
        self.app.IsSame = lambda a, b: int(a is b or mapping.get(id(a)) == id(b))
        self.assertEqual(self.register(replacements), original)
        self.assertIs(self.resolve(original[0]).binding, replacements[0])

    def test_native_identity_never_compares_an_edge_with_a_face(self):
        kinds = {id(self.body): "body"}
        kinds.update({id(b.face): "face" for b in self.faces})
        kinds.update({id(b.edge): "edge" for b in self.edges})
        def compare(first, second):
            self.assertEqual(kinds[id(first)], kinds[id(second)])
            return int(first is second)
        self.app.IsSame = compare
        face_ids, edge_ids = self.register(kind="face"), self.register()
        self.assertEqual(self.register(kind="face"), face_ids)
        self.assertEqual(self.register(), edge_ids)

    def test_native_error_preserves_both_groups_and_first_exception(self):
        self.register(kind="face")
        self.register()
        before = self.snapshot()
        failure = RuntimeError("native identity failed")
        def fail(first, second):
            raise failure
        self.app.IsSame = fail
        with self.assertRaises(RuntimeError) as caught:
            self.register()
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.snapshot(), before)

    def test_failed_new_scope_edge_read_retires_old_faces_without_partial_commit(self):
        old_face, old_edge = self.register(kind="face"), self.register()
        issued = self.issued.copy()
        for status in (None, True, False, 2, 3, "1", 1.0):
            self.app.IsSame = lambda a, b: status
            with self.subTest(status=status), self.assertRaises(EntityBindingConflict):
                self.register(stamp=13)
            self.assertEqual(self.registry._entries, {})
            self.assertEqual(self.registry._complete_kinds, set())
            self.assertEqual(self.issued, issued)
        for kind, ids in (("face", old_face), ("edge", old_edge)):
            with self.assertRaises(EntityReferenceStale):
                self.resolve(ids[0], kind=kind)

    def test_close_and_worker_shared_issued_set_prevent_cross_kind_token_reuse(self):
        face_ids, edge_ids = self.register(kind="face"), self.register()
        self.registry.close()
        for kind, ids in (("face", face_ids), ("edge", edge_ids)):
            with self.assertRaises(EntityNotFound):
                self.resolve(ids[0], kind=kind)
        with self.assertRaises(EntityNotFound):
            self.register()
        self.registry = EntityRegistry(self.app, "d-new", issued_ids=self.issued)
        old = face_ids[0]
        suffix = next(s for s in ("111111", "222222", "333333") if "e-" + s not in self.issued)
        with mock.patch("swcli.daemon.entities.secrets.choice", side_effect=list(old[2:] + suffix)):
            new_edge = self.register(self.edges[:1])
        self.assertEqual(new_edge, ["e-" + suffix])
        self.assertTrue(set(new_edge).isdisjoint(face_ids + edge_ids))


class EdgeDocumentLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(IsSame=lambda a, b: int(
            getattr(a, "identity", a) is getattr(b, "identity", b)))
        self.documents = DocumentRegistry(self.app)
        self.document = self.document_object()
        self.entry = self.documents.register(self.document)
        self.body = object()
        self.faces = [FaceBinding(object(), self.body, b"face")]
        self.edges = [EdgeBinding(object(), self.body, b"edge")]

    @staticmethod
    def document_object(identity=None):
        return SimpleNamespace(identity=object() if identity is None else identity,
                               GetTitle=lambda: "part.SLDPRT", GetPathName=lambda: "C:\\part.SLDPRT",
                               GetType=lambda: 1, GetSaveFlag=lambda: False)

    def register(self, entry):
        return (entry.entities.register_faces(self.faces, configuration="default", update_stamp=12)[0],
                entry.entities.register_edges(self.edges, configuration="default", update_stamp=12)[0])

    def test_live_wrapper_reuses_one_shared_document_scope_for_both_kinds(self):
        ids = self.register(self.entry)
        repeated = self.documents.register(self.document_object(self.document.identity))
        self.assertIs(repeated.entities, self.entry.entities)
        self.assertEqual(self.register(repeated), ids)

    def test_external_same_path_reopen_closes_both_kinds_and_allocates_fresh_ids(self):
        old = self.register(self.entry)
        fresh = self.documents.register(self.document_object())
        for kind, token in zip(("face", "edge"), old):
            with self.assertRaises(EntityNotFound):
                self.entry.entities.resolve(token, kind=kind, configuration="default", update_stamp=12)
        self.assertTrue(set(old).isdisjoint(self.register(fresh)))

    def test_external_close_sync_invalidates_both_even_if_old_registry_is_retained(self):
        old = self.register(self.entry)
        retained = self.entry.entities
        self.app.GetDocuments = lambda: ()
        self.documents.sync()
        for kind, token in zip(("face", "edge"), old):
            with self.assertRaises(EntityNotFound):
                retained.resolve(token, kind=kind, configuration="default", update_stamp=12)


if __name__ == "__main__":
    unittest.main()
