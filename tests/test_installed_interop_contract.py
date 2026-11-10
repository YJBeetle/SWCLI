"""Offline metadata collector checks; no installed interop or CAD host is used."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ci/inspect-installed-interop-contract.py"
spec = importlib.util.spec_from_file_location("installed_interop_contract_test", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def attribute(name, value):
    return dict(type=gate.ATTRIBUTE+name, constructor_arguments=[dict(type="fixture", value=value)], named_arguments={})


def native_fixture():
    return dict(execution_kind="local-installed-typelib-only-zero-CAD",
                library_attributes="(IID('{83A33D31-27C5-11CE-BFD4-00400513BB57}'), 0, 3, 33, 0, 8)", interfaces=[
        dict(name="IModelDocExtension", guid="{99F4D4AF-F268-4EE1-8C55-041F7BECF879}", functions=[
            dict(name="SaveAs3", memid=315, args_repr=repr(((8,1,None),(3,1,None),(3,1,None),(9,1,None),(9,1,None),((26,3),3,None),((26,3),3,None))), rettype_repr=repr((11,0,None)))]),
        dict(name="IDimension", guid="{83A33D3A-27C5-11CE-BFD4-00400513BB57}", functions=[
            dict(name="SetSystemValue3", memid=44, args_repr=repr(((5,1,None),(3,1,None),(12,1,None))), rettype_repr=repr((3,0,None))),
            dict(name="GetSystemValue3", memid=46, args_repr=repr(((3,1,None),(12,1,None))), rettype_repr=repr((12,0,None)))])])


def managed_fixture(native):
    result = dict(success=True, assembly=dict(reflection_only=True, attributes=[
        attribute("GuidAttribute", "83A33D31-27C5-11CE-BFD4-00400513BB57"), attribute("TypeLibVersionAttribute",33)]),
        interop_file=dict(file_version="33.5.0.53"), solidworks_exe=dict(file_version="33.5.0.53"), interfaces={})
    for interface in native["interfaces"]:
        row = dict(is_interface=True, attributes=[attribute("GuidAttribute",interface["guid"])], methods={})
        result["interfaces"][interface["name"]] = row
        for method in interface["functions"]:
            parameters = gate.literal(method["args_repr"])
            row["methods"][method["name"]] = dict(return_type=gate.native_type(gate.literal(method["rettype_repr"])[0]),
                attributes=[attribute("DispIdAttribute",method["memid"])], return_attributes=[attribute("MarshalAsAttribute",37)],
                parameters=[dict(position=i,type=gate.native_type(p[0]),is_in=bool(p[1]&1),is_out=bool(p[1]&2),
                                 attributes=[attribute("MarshalAsAttribute",26)]) for i,p in enumerate(parameters)])
    return result


class InstalledInteropContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.args = SimpleNamespace(output_dir=self.root/"output")
        self.args.output_dir.mkdir()
        for name in ("typelib_evidence","sldworks","interop","solidworks_exe","powershell"):
            path = self.root/(name+".fixture");path.write_bytes(b"pinned metadata fixture")
            setattr(self.args,name,path)
        self.native = native_fixture()
        self.native["sha256"] = hashlib.sha256(self.args.sldworks.read_bytes()).hexdigest()
        self.args.typelib_evidence.write_text(json.dumps(self.native))
        self.managed = managed_fixture(self.native)
        for key,name in (("interop_file","interop"),("solidworks_exe","solidworks_exe")):
            self.managed[key]["sha256"] = hashlib.sha256(getattr(self.args,name).read_bytes()).hexdigest()

    def runner(self, command, **options):
        self.assertIs(type(command),list)
        self.assertNotIn("shell",options)
        self.assertEqual(options,dict(capture_output=True,timeout=120,check=False))
        self.assertEqual(command[1:5],["-NoLogo","-NoProfile","-NonInteractive","-File"])
        Path(command[command.index("-OutputPath")+1]).write_text(json.dumps(self.managed))
        return SimpleNamespace(returncode=0,stdout=b"metadata only\n",stderr=b"")

    def test_retained_typelib_and_reflection_compare_without_accepting_native_binding(self):
        report = {}
        gate.collect(self.args,report,runner=self.runner)
        self.assertTrue(report["success"])
        self.assertTrue(all(check["matches"] for check in report["contract_checks"]))
        self.assertFalse(report["native_binding_accepted"] or report["null_marshaling_accepted"])
        self.assertTrue(report["marshaling_review_required"])
        self.assertEqual(report["reflection"]["interfaces"]["IModelDocExtension"]["methods"]["SaveAs3"]["return_attributes"][0]["constructor_arguments"][0]["value"],37)
        self.assertEqual(report["inputs"],report["inputs_after"])

    def test_missing_marshalas_is_retained_as_absent_and_never_accepted_implicitly(self):
        for interface in self.managed["interfaces"].values():
            for method in interface["methods"].values():
                method["return_attributes"] = []
                for param in method["parameters"]: param["attributes"] = []
        report = {};gate.collect(self.args,report,runner=self.runner)
        self.assertTrue(report["marshaling_review_required"])
        self.assertFalse(report["null_marshaling_accepted"])

    def test_wrong_type_dispid_arity_guid_or_version_retains_actual_mismatch(self):
        original = copy.deepcopy(self.managed)
        for kind in ("type","dispid","arity","guid","version","typelib-version"):
            with self.subTest(kind=kind):
                self.managed = copy.deepcopy(original)
                interface = self.managed["interfaces"]["IModelDocExtension"]
                method = interface["methods"]["SaveAs3"]
                if kind == "type": method["parameters"][0]["type"] = "System.Int32"
                elif kind == "dispid": method["attributes"][0]["constructor_arguments"][0]["value"] = 314
                elif kind == "arity": method["parameters"].pop()
                elif kind == "guid": interface["attributes"][0]["constructor_arguments"][0]["value"] = "wrong"
                elif kind == "version": self.managed["solidworks_exe"]["file_version"] = "34.0.0"
                else: self.managed["assembly"]["attributes"][1]["constructor_arguments"][0]["value"] = 34
                report = {}
                with self.assertRaisesRegex(RuntimeError,"metadata differs"):
                    gate.collect(self.args,report,runner=self.runner)
                self.assertTrue(any(not check["matches"] for check in report["contract_checks"]))
                self.assertNotIn("success",report)
                self.assertEqual(report["reflection"],self.managed)

    def test_unknown_native_type_cannot_match_a_missing_managed_type(self):
        self.native["interfaces"][0]["functions"][0]["rettype_repr"] = "(99, 0, None)"
        self.managed["interfaces"]["IModelDocExtension"]["methods"]["SaveAs3"]["return_type"] = None
        with self.assertRaisesRegex(RuntimeError,"unresolved native return"):
            gate.compare_contracts(self.native,self.managed,{})

    def test_wrong_typelib_bytes_stop_before_metadata_process(self):
        self.args.sldworks.write_bytes(b"changed typelib")
        runner = mock.Mock();report = {}
        with self.assertRaisesRegex(RuntimeError,"typelib bytes differ"):
            gate.collect(self.args,report,runner=runner)
        runner.assert_not_called()
        self.assertNotIn("reflection_attempted",report)

    def test_missing_or_relative_input_stops_before_metadata_process(self):
        for path in (Path("relative.dll"),self.root/"missing.dll"):
            with self.subTest(path=path):
                self.args.interop = path;runner = mock.Mock()
                with self.assertRaisesRegex(RuntimeError,"absolute input"):
                    gate.collect(self.args,{},runner=runner)
                runner.assert_not_called()

    def test_child_failure_retains_first_error_and_original_logs(self):
        self.managed = dict(success=False,first_error=dict(type="MetadataFailure",message="first metadata error"))
        def failure(command,**options):
            self.runner(command,**options)
            return SimpleNamespace(returncode=1,stdout=b"partial output",stderr=b"first error")
        report = {}
        with self.assertRaisesRegex(RuntimeError,"metadata process failed"):
            gate.collect(self.args,report,runner=failure)
        self.assertEqual(report["reflection"]["first_error"]["message"],"first metadata error")
        self.assertEqual((self.args.output_dir/"reflection.stderr.log").read_bytes(),b"first error")

    def test_child_timeout_retains_partial_output_without_retry(self):
        error = subprocess.TimeoutExpired("metadata",120,output=b"partial",stderr=b"timeout context")
        runner = mock.Mock(side_effect=error);report = {}
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            gate.collect(self.args,report,runner=runner)
        self.assertIs(caught.exception,error);runner.assert_called_once()
        self.assertTrue(report["reflection_timeout"])
        self.assertEqual((self.args.output_dir/"reflection.stdout.log").read_bytes(),b"partial")

    def test_input_race_is_rejected_after_retaining_reflection(self):
        def changed(command,**options):
            result = self.runner(command,**options)
            self.args.sldworks.write_bytes(b"intervening native typelib change")
            return result
        report = {}
        with self.assertRaisesRegex(RuntimeError,"input changed"):
            gate.collect(self.args,report,runner=changed)
        self.assertIn("reflection",report);self.assertIn("inputs_after",report)

    def test_literal_parser_never_executes_receipt_text_and_bounds_depth(self):
        with self.assertRaises(ValueError): gate.literal("__import__('os').getcwd()")
        with self.assertRaisesRegex(RuntimeError,"depth bound"):
            gate.native_type((26,(26,(26,(26,(26,(26,(26,(26,(26,3))))))))))
        with self.assertRaisesRegex(RuntimeError,"identity receipt"):
            gate.library_identity(dict(library_attributes="__import__('os').getcwd()"))

    def test_main_never_overwrites_an_existing_output(self):
        marker = self.args.output_dir/"original";marker.write_bytes(b"preserve")
        argv = ["--output-dir",str(self.args.output_dir)]
        for name in ("typelib-evidence","sldworks","interop","solidworks-exe","powershell"):
            argv += ["--"+name,str(getattr(self.args,name.replace("-","_")))]
        with self.assertRaises(FileExistsError): gate.main(argv)
        self.assertEqual(marker.read_bytes(),b"preserve")

    def test_collector_has_no_CAD_activation_or_call_path(self):
        import ast
        tree = ast.parse(SCRIPT.read_text())
        forbidden = {"LoadTypeLib","LoadTypeLibEx","Dispatch","DispatchEx","GetActiveObject","CoCreateInstance","SaveAs3","GetSystemValue3","SetSystemValue3","CoMarshalInterface"}
        invoked = {node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)}
        self.assertFalse(invoked & forbidden)
        powershell = SCRIPT.with_name("inspect-installed-interop-metadata.ps1").read_text()
        for text in ("-ComObject","Activator]","GetActiveObject","CoCreateInstance","MethodInfo.Invoke","Assembly]::LoadFrom"):
            self.assertNotIn(text,powershell)
        self.assertIn("Assembly]::ReflectionOnlyLoadFrom",powershell)
        self.assertIn("CustomAttributeData]::GetCustomAttributes",powershell)


if __name__ == "__main__": unittest.main()
