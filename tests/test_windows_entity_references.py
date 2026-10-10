"""Exact reference binding failures never become guessed topology identity."""

import sys
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts import windows_entity_references as references


class EntityReferenceTests(unittest.TestCase):
    def setUp(self):
        self.entity, self.resolved = object(), object()
        self.app = SimpleNamespace(IsSame=mock.Mock(return_value=1))
        self.extension = SimpleNamespace(
            GetPersistReference3=mock.Mock(return_value=(0, 255, 1))
        )

    def test_round_trip_requires_native_identity_not_python_wrapper_identity(self):
        with mock.patch.object(
            references, "_resolve_native", return_value=(self.resolved, 0)
        ) as resolve:
            result = references.capture_verified_reference(
                self.app, self.extension, self.entity
            )
        self.assertEqual(result, b"\x00\xff\x01")
        resolve.assert_called_once_with(self.extension, result)
        self.app.IsSame.assert_called_once_with(self.entity, self.resolved)

    def test_supported_byte_shapes_are_copied_without_coercion(self):
        for raw in (b"\x00\xff", bytearray((0, 255)), (0, 255), [0, 255]):
            with self.subTest(raw=raw):
                result = references._reference_bytes(raw)
                self.assertIsInstance(result, bytes)
                self.assertEqual(result, b"\x00\xff")
        raw = bytearray((1, 2))
        captured = references._reference_bytes(raw)
        raw[0] = 3
        self.assertEqual(captured, b"\x01\x02")

    def test_invalid_reference_never_attempts_resolution(self):
        invalid = (
            None,
            2,
            True,
            "12",
            {1, 2},
            iter((1, 2)),
            b"",
            [],
            (),
            b"x" * (references.MAX_REFERENCE_BYTES + 1),
            [True],
            [False],
            [1.0],
            ["1"],
            [-1],
            [256],
            [None],
            [[1]],
        )
        with mock.patch.object(references, "_resolve_native") as resolve:
            for raw in invalid:
                with (
                    self.subTest(raw_type=type(raw).__name__),
                    self.assertRaises(references.EntityReferenceUnavailable),
                ):
                    references.resolve_verified_reference(self.extension, raw)
            resolve.assert_not_called()
        self.app.IsSame.assert_not_called()

    def test_maximum_reference_is_bounded_and_zero_bytes_are_not_absence(self):
        encoded = references._reference_bytes(b"\0" * references.MAX_REFERENCE_BYTES)
        self.assertEqual(len(encoded), references.MAX_REFERENCE_BYTES)
        with mock.patch.object(
            references, "_resolve_native", return_value=(self.resolved, 0)
        ):
            self.assertIs(
                references.resolve_verified_reference(self.extension, b"\0"),
                self.resolved,
            )

    def test_non_ok_or_unwritten_status_never_compares_identity(self):
        for status in (None, True, False, "0", 0.0, -1, 1, 2, 3, 4, 8, 16, 2147483647):
            with (
                self.subTest(status=status),
                mock.patch.object(
                    references, "_resolve_native", return_value=(self.resolved, status)
                ),
            ):
                with self.assertRaises(references.EntityReferenceUnavailable):
                    references.capture_verified_reference(
                        self.app, self.extension, self.entity
                    )
        self.app.IsSame.assert_not_called()

    def test_ok_without_object_fails_before_identity(self):
        with mock.patch.object(references, "_resolve_native", return_value=(None, 0)):
            with self.assertRaises(references.EntityReferenceUnavailable):
                references.capture_verified_reference(
                    self.app, self.extension, self.entity
                )
        self.app.IsSame.assert_not_called()

    def test_absent_input_never_calls_native(self):
        with self.assertRaises(references.EntityReferenceUnavailable):
            references.capture_verified_reference(self.app, self.extension, None)
        self.extension.GetPersistReference3.assert_not_called()

    def test_different_unsupported_and_malformed_identity_do_not_publish_reference(
        self,
    ):
        with mock.patch.object(
            references, "_resolve_native", return_value=(self.entity, 0)
        ):
            for status in (0, 2, 3, -1, None, True, False, 1.0, "1"):
                self.app.IsSame.return_value = status
                with (
                    self.subTest(status=status),
                    self.assertRaises(references.EntityReferenceUnavailable),
                ):
                    references.capture_verified_reference(
                        self.app, self.extension, self.entity
                    )

    def test_native_exceptions_preserve_first_failure(self):
        failure = RuntimeError("host disconnected")
        self.extension.GetPersistReference3.side_effect = failure
        with mock.patch.object(references, "_resolve_native") as resolve:
            with self.assertRaises(RuntimeError) as caught:
                references.capture_verified_reference(
                    self.app, self.extension, self.entity
                )
            self.assertIs(caught.exception, failure)
            resolve.assert_not_called()
        self.extension.GetPersistReference3.side_effect = None
        with mock.patch.object(references, "_resolve_native", side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                references.capture_verified_reference(
                    self.app, self.extension, self.entity
                )
            self.assertIs(caught.exception, failure)
        self.app.IsSame.side_effect = failure
        with mock.patch.object(
            references, "_resolve_native", return_value=(self.resolved, 0)
        ):
            with self.assertRaises(RuntimeError) as caught:
                references.capture_verified_reference(
                    self.app, self.extension, self.entity
                )
            self.assertIs(caught.exception, failure)

    def test_binding_uses_unsigned_byte_array_and_byref_i4_sentinel(self):
        pythoncom = SimpleNamespace(
            VT_BYREF=0x4000, VT_I4=3, VT_ARRAY=0x2000, VT_UI1=17
        )
        client = SimpleNamespace(
            VARIANT=lambda kind, value: SimpleNamespace(varianttype=kind, value=value)
        )
        win32com = SimpleNamespace(client=client)
        seen = []

        def resolve(encoded, status):
            seen.append(
                (encoded.varianttype, encoded.value, status.varianttype, status.value)
            )
            status.value = 0
            return self.resolved

        extension = SimpleNamespace(GetObjectByPersistReference3=resolve)
        with mock.patch.dict(
            sys.modules,
            {"pythoncom": pythoncom, "win32com": win32com, "win32com.client": client},
        ):
            result = references.resolve_verified_reference(extension, b"\0\xff")
        self.assertIs(result, self.resolved)
        self.assertEqual(seen, [(0x2011, b"\0\xff", 0x4003, 2147483647)])

    def test_binding_unwritten_byref_is_not_default_success(self):
        pythoncom = SimpleNamespace(
            VT_BYREF=0x4000, VT_I4=3, VT_ARRAY=0x2000, VT_UI1=17
        )
        client = SimpleNamespace(
            VARIANT=lambda kind, value: SimpleNamespace(value=value)
        )
        extension = SimpleNamespace(
            GetObjectByPersistReference3=lambda encoded, status: self.resolved
        )
        with mock.patch.dict(
            sys.modules,
            {
                "pythoncom": pythoncom,
                "win32com": SimpleNamespace(client=client),
                "win32com.client": client,
            },
        ):
            with self.assertRaises(references.EntityReferenceUnavailable):
                references.resolve_verified_reference(extension, b"x")


if __name__ == "__main__":
    unittest.main()
