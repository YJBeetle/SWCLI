"""Modern active-configuration observation must not activate, fall back or retry."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from swcli.hosts.windows_configurations import active_configuration_name
from swcli.hosts.windows_custom_properties import _state


class ConfigurationObservationTests(unittest.TestCase):
    def document(self, active):
        return SimpleNamespace(ConfigurationManager=SimpleNamespace(ActiveConfiguration=active),
            GetActiveConfiguration=Mock(side_effect=AssertionError("obsolete API must not be called")),
            ShowConfiguration2=Mock(side_effect=AssertionError("observation must not switch configuration")),
            GetType=lambda:1, GetUpdateStamp=lambda:7, GetSaveFlag=lambda:False)

    def test_get_only_property_returns_exact_name_without_switch_or_legacy_call(self):
        doc=self.document(SimpleNamespace(Name=" 当前配置 "))
        self.assertEqual(active_configuration_name(doc)," 当前配置 ")
        self.assertEqual(_state(doc),(1,7,False," 当前配置 "))
        doc.GetActiveConfiguration.assert_not_called();doc.ShowConfiguration2.assert_not_called()

    def test_missing_modern_configuration_never_uses_available_legacy_method(self):
        for active in (None, SimpleNamespace(Name=""), SimpleNamespace(Name=" "),
                       SimpleNamespace(Name=None), SimpleNamespace(Name=True), SimpleNamespace(Name=3)):
            with self.subTest(active=active):
                doc=self.document(active)
                with self.assertRaises(RuntimeError): active_configuration_name(doc)
                doc.GetActiveConfiguration.assert_not_called();doc.ShowConfiguration2.assert_not_called()
        doc=self.document(None);del doc.ConfigurationManager
        with self.assertRaises(AttributeError): active_configuration_name(doc)
        doc.GetActiveConfiguration.assert_not_called()

    def test_modern_property_failure_is_read_once_and_preserves_first_error(self):
        failure=RuntimeError("manager property unavailable")
        class Document:
            reads=0
            @property
            def ConfigurationManager(self):
                self.reads+=1
                raise failure
        doc=Document()
        with self.assertRaises(RuntimeError) as caught:active_configuration_name(doc)
        self.assertIs(caught.exception,failure)
        self.assertEqual(doc.reads,1)

    def test_drawings_allow_absent_configuration_only_when_explicit(self):
        doc=self.document(None)
        self.assertIsNone(active_configuration_name(doc,allow_absent=True))
        with self.assertRaises(RuntimeError):active_configuration_name(doc)
        doc.GetType=lambda:3
        self.assertEqual(_state(doc),(3,7,False,None))
        doc.GetActiveConfiguration.assert_not_called()


if __name__=="__main__":unittest.main()
