"""Unsupported CAD comparison is not evidence of different dimension identity."""

from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts import windows_dimension_identity as identity


class DimensionIdentityTests(unittest.TestCase):
    def setUp(self):
        self.first, self.second = object(), object()
        self.app = SimpleNamespace(IsSame=mock.Mock())

    def test_supported_native_states_do_not_query_com_or_use_python_identity(self):
        with mock.patch.object(identity, "_query_iunknown") as query:
            for status in (0, 1):
                self.app.IsSame.return_value = status
                self.assertIs(
                    identity.same_dimension(self.app, self.first, self.first),
                    status == 1,
                )
                self.assertIs(
                    identity.same_dimension(self.app, self.first, self.second),
                    status == 1,
                )
            query.assert_not_called()

    def test_unsupported_uses_canonical_com_equal_or_distinct_interfaces(self):
        self.app.IsSame.return_value = 2
        for same in (False, True):
            with self.subTest(same=same):
                first_unknown = object()
                second_unknown = first_unknown if same else object()
                with mock.patch.object(
                    identity,
                    "_query_iunknown",
                    side_effect=[first_unknown, second_unknown],
                ) as query:
                    self.assertIs(
                        identity.same_dimension(self.app, self.first, self.second), same
                    )
                    self.assertEqual(
                        query.call_args_list,
                        [mock.call(self.first), mock.call(self.second)],
                    )

    def test_canonical_equality_not_interface_python_wrapper_identity(self):
        class Interface:
            def __eq__(self, other):
                return True

        self.app.IsSame.return_value = 2
        with mock.patch.object(
            identity, "_query_iunknown", side_effect=[Interface(), Interface()]
        ):
            self.assertTrue(identity.same_dimension(self.app, self.first, self.second))

    def test_invalid_native_states_fail_without_querying_com(self):
        with mock.patch.object(identity, "_query_iunknown") as query:
            for status in (None, True, False, 0.0, 1.0, 2.0, "2", -1, 3):
                with self.subTest(status=status):
                    self.app.IsSame.return_value = status
                    with self.assertRaises(identity.DimensionIdentityUnavailable):
                        identity.same_dimension(self.app, self.first, self.second)
            query.assert_not_called()

    def test_native_exception_is_preserved_not_reinterpreted_as_unsupported(self):
        for failure in (RuntimeError("busy"), AttributeError("missing CAD comparison")):
            self.app.IsSame.side_effect = failure
            with mock.patch.object(identity, "_query_iunknown") as query:
                with self.assertRaises(type(failure)) as caught:
                    identity.same_dimension(self.app, self.first, self.second)
                self.assertIs(caught.exception, failure)
                query.assert_not_called()

    def test_query_or_equality_failure_is_not_different(self):
        self.app.IsSame.return_value = 2
        failure = RuntimeError("query busy")
        with mock.patch.object(identity, "_query_iunknown", side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                identity.same_dimension(self.app, self.first, self.second)
            self.assertIs(caught.exception.__cause__, failure)

        class Interface:
            def __eq__(self, other):
                raise failure

        with mock.patch.object(identity, "_query_iunknown", return_value=Interface()):
            with self.assertRaises(RuntimeError) as caught:
                identity.same_dimension(self.app, self.first, self.second)
            self.assertIs(caught.exception.__cause__, failure)

    def test_nonboolean_canonical_comparison_fails_closed(self):
        self.app.IsSame.return_value = 2

        class Interface:
            def __eq__(self, other):
                return 1

        with mock.patch.object(identity, "_query_iunknown", return_value=Interface()):
            with self.assertRaises(identity.DimensionIdentityUnavailable):
                identity.same_dimension(self.app, self.first, self.second)

    def test_actual_query_uses_only_iunknown_and_rejects_absence(self):
        iid, unknown = object(), object()
        native = SimpleNamespace(QueryInterface=mock.Mock(return_value=unknown))
        dimension = SimpleNamespace(_oleobj_=native)
        with mock.patch.dict(
            "sys.modules", {"pythoncom": SimpleNamespace(IID_IUnknown=iid)}
        ):
            self.assertIs(identity._query_iunknown(dimension), unknown)
            native.QueryInterface.assert_called_once_with(iid)
            native.QueryInterface.return_value = None
            with self.assertRaises(identity.DimensionIdentityUnavailable):
                identity._query_iunknown(dimension)
            with self.assertRaises(identity.DimensionIdentityUnavailable):
                identity._query_iunknown(object())


if __name__ == "__main__":
    unittest.main()
