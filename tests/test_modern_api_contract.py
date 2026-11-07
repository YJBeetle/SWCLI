import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/verify-modern-api-contract.py"
spec = importlib.util.spec_from_file_location("modern_api_contract", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ModernApiContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.sldworks = Path(self.temporary.name) / "sldworks.tlb"
        self.swconst = Path(self.temporary.name) / "swconst.tlb"
        for path in (self.sldworks, self.swconst):
            path.write_bytes(b"official typelib fixture")
        self.infos = []
        for name, members in gate.REQUIRED.items():
            info = Mock()
            info.GetTypeAttr.return_value = SimpleNamespace(typekind=4, iid="mock-"+name, cFuncs=1)
            info.GetFuncDesc.return_value = (0,)
            member, count = next(iter(members.items()))
            info.GetNames.return_value = [member] + ["arg"+str(n) for n in range(count)]
            self.infos.append(info)
        library = Mock()
        library.GetTypeInfoCount.return_value = len(self.infos)
        library.GetDocumentation.side_effect = lambda index: (list(gate.REQUIRED)[index],)
        library.GetTypeInfo.side_effect = lambda index: self.infos[index]
        library.GetLibAttr.return_value = ("mock-lib", 0, 3, 33, 0)
        self.enum = Mock()
        self.enum.GetTypeAttr.return_value = SimpleNamespace(typekind=0, cVars=2)
        # VarDesc supports both indexed MEMBERID and the named value.
        class Desc:
            def __init__(self, index): self.index, self.value = index, list(gate.ENUMS.values())[index]
            def __getitem__(self, index): return self.index
        self.enum.GetVarDesc.side_effect = Desc
        self.enum.GetDocumentation.side_effect = lambda index: (list(gate.ENUMS)[index],)
        enums = Mock()
        enums.GetTypeInfoCount.return_value = 1
        enums.GetTypeInfo.return_value = self.enum
        enums.GetLibAttr.return_value = ("mock-const", 0, 3, 33, 0)
        self.com = SimpleNamespace(TKIND_INTERFACE=3, TKIND_DISPATCH=4, TKIND_ENUM=0,
                                   LoadTypeLib=Mock(side_effect=[library, enums]))

    def test_real_named_parameter_lists_and_enums_are_retained_without_model_calls(self):
        evidence = {}
        gate.read_contracts(self.sldworks, self.swconst, self.com, evidence)
        self.assertEqual(self.com.LoadTypeLib.call_args_list[0].args, (str(self.sldworks),))
        self.assertEqual(evidence["swconst"]["constants"], gate.ENUMS)
        self.assertEqual(set(evidence["sldworks"]["interfaces"]), set(gate.REQUIRED))
        self.assertEqual(len(evidence["sldworks"]["sha256"]), 64)

    def test_missing_absolute_path_refuses_before_native_library_load(self):
        with self.assertRaises(RuntimeError):
            gate.read_contracts(Path("sldworks.tlb"), self.swconst, self.com, {})
        self.com.LoadTypeLib.assert_not_called()

    def test_wrong_installed_signature_retains_actual_parameter_list_and_stops(self):
        self.infos[1].GetNames.return_value = ["GetSystemValue3", "WhichConfigurations"]
        evidence = {}
        with self.assertRaisesRegex(RuntimeError, "GetSystemValue3"):
            gate.read_contracts(self.sldworks, self.swconst, self.com, evidence)
        self.assertEqual(evidence["sldworks"]["interfaces"]["IDimension"]["members"]["GetSystemValue3"],
                         [["WhichConfigurations"]])
        self.assertEqual(self.com.LoadTypeLib.call_count, 1)

    def test_official_name_as_coclass_is_not_accepted(self):
        self.infos[0].GetTypeAttr.return_value.typekind = 5
        with self.assertRaisesRegex(RuntimeError, "not an interface"):
            gate.read_contracts(self.sldworks, self.swconst, self.com, {})

    def test_wrong_enum_cannot_be_reported_as_verified(self):
        self.enum.GetVarDesc.side_effect = lambda index: type("Desc", (), {
            "value":99,"__getitem__":lambda self,key:index})()
        evidence = {}
        with self.assertRaisesRegex(RuntimeError, "enums differ"):
            gate.read_contracts(self.sldworks, self.swconst, self.com, evidence)
        self.assertEqual(evidence["swconst"]["constants"], {name:99 for name in gate.ENUMS})


if __name__ == "__main__":
    unittest.main()
