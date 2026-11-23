"""Strict OLE GetSystemValue3 shape/configuration/units; portable, never native proof."""
from decimal import Decimal
from types import SimpleNamespace
import math
import unittest
from unittest.mock import Mock
from swcli.hosts import windows_dimensions as adapter


class DimensionValue3Tests(unittest.TestCase):
    def fixture(self, values=(0.02,), configuration="Current"):
        doc=SimpleNamespace(ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name=configuration)),
            ShowConfiguration2=Mock(side_effect=AssertionError("must not switch configuration")))
        dimension=SimpleNamespace(DrivenState=2, ReadOnly=False, FullName="D1@Sketch@Part",
            GetSystemValue3=Mock(return_value=values),
            GetSystemValue2=Mock(side_effect=AssertionError("obsolete API must not be called")))
        return doc,dimension

    def test_named_current_configuration_and_single_value_meters_to_millimeters(self):
        for values in [(0.02,),[0.02],(1,)]:
            with self.subTest(values=values):
                doc,dimension=self.fixture(values,configuration=" 当前配置 ")
                result=adapter._descriptor(doc,dimension)
                self.assertEqual(result["value"],values[0]*1000)
                self.assertEqual(result["unit"],"millimeter")
                self.assertEqual(result["configuration"]," 当前配置 ")
                self.assertEqual(result["native_name"],dimension.FullName)
                self.assertEqual(result["driven_state"],2)
                self.assertFalse(result["read_only"])
                dimension.GetSystemValue3.assert_called_once_with(3," 当前配置 ")
                dimension.GetSystemValue2.assert_not_called();doc.ShowConfiguration2.assert_not_called()

    def test_empty_multiple_scalar_nested_and_invalid_values_never_select_first(self):
        bad=[None,0.02,True,"0.02",{},(),[],(0.02,0.03),[0.02,0.02],[[0.02]],
             [None],[True],[False],["0.02"],[Decimal("0.02")],[complex(.02)],
             [0],[-1],[math.nan],[math.inf],[-math.inf],[1e308],[10**1000],iter([.02])]
        for values in bad:
            with self.subTest(values=str(values)[:40]):
                doc,dimension=self.fixture(values)
                with self.assertRaises(adapter._DimensionError) as caught:adapter._descriptor(doc,dimension)
                self.assertEqual(caught.exception.code,"DimensionObservationUnavailable")
                dimension.GetSystemValue3.assert_called_once_with(3,"Current")
                dimension.GetSystemValue2.assert_not_called()

    def test_com_failure_has_one_attempt_and_no_fallback_or_configuration_change(self):
        doc,dimension=self.fixture()
        failure=RuntimeError("first GetSystemValue3 failure")
        dimension.GetSystemValue3.side_effect=failure
        with self.assertRaises(RuntimeError) as caught:adapter._descriptor(doc,dimension)
        self.assertIs(caught.exception,failure)
        dimension.GetSystemValue3.assert_called_once_with(3,"Current")
        dimension.GetSystemValue2.assert_not_called();doc.ShowConfiguration2.assert_not_called()

    def test_unknown_configuration_refuses_before_dimension_getter(self):
        for configuration in [None,False,1,""," "]:
            with self.subTest(configuration=configuration):
                doc,dimension=self.fixture(configuration=configuration)
                with self.assertRaises(adapter._DimensionError):adapter._descriptor(doc,dimension)
                dimension.GetSystemValue3.assert_not_called();dimension.GetSystemValue2.assert_not_called()

    def test_bad_name_and_driven_state_still_fail_before_getter(self):
        for member,value in [("FullName",""),("FullName",None),("DrivenState",True),("DrivenState",7)]:
            doc,dimension=self.fixture();setattr(dimension,member,value)
            with self.assertRaises(adapter._DimensionError):adapter._descriptor(doc,dimension)
            dimension.GetSystemValue3.assert_not_called()
        doc,dimension=self.fixture();dimension.ReadOnly=True;dimension.DrivenState=1
        result=adapter._descriptor(doc,dimension)
        self.assertTrue(result["read_only"])
        self.assertEqual(result["driven_state"],1)


if __name__=="__main__":unittest.main()
