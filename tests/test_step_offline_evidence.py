"""Portable evidence-parser/provenance regressions; no native acceptance claim."""
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/ci'))
from gate_support.step_wire_evidence import audit_wire, byte_compare, parse
from gate_support.step_import_observation import observe_dispatch, observe_preferences, read_interface_contract


def wire_fixture():
    return b"""ISO-10303-21;
HEADER;FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));ENDSEC;
DATA;
#1=PRODUCT_DEFINITION_SHAPE('','',$);
#2=SHAPE_DEFINITION_REPRESENTATION(#1,#3);
#3=GEOMETRICALLY_BOUNDED_WIREFRAME_SHAPE_REPRESENTATION('quoted;name',(#4),#5);
#4=GEOMETRIC_CURVE_SET('',(#8));
#5=(GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNIT_ASSIGNED_CONTEXT((#6)) REPRESENTATION_CONTEXT('',''));
#6=(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.));
#7=CARTESIAN_POINT('',(0.,0.,0.));
#8=B_SPLINE_CURVE_WITH_KNOTS('',1,(#7,#9),.UNSPECIFIED.,.F.,.F.,(2,2),(0.,1.),.UNSPECIFIED.);
#9=CARTESIAN_POINT('',(10.,0.,0.));
ENDSEC;END-ISO-10303-21;"""


class StepOfflineEvidenceTests(unittest.TestCase):
    def test_root_reachable_geometry_and_units_not_global_entity_count(self):
        raw=wire_fixture()
        report=audit_wire(raw)
        self.assertEqual(report['represented_curve_count'],1)
        self.assertEqual(report['total_length_mm'],10)
        self.assertEqual(report['orphan_curves'],[])
        self.assertEqual(report['full_express_conformance'],'unknown')
        self.assertEqual(report['native_import_support'],'unknown')
        with self.assertRaisesRegex(ValueError,'orphan'):
            audit_wire(raw.replace(b"GEOMETRIC_CURVE_SET('',(#8))",b"GEOMETRIC_CURVE_SET('',())"))
        with self.assertRaisesRegex(ValueError,'dangling'):
            audit_wire(raw.replace(b'(#7,#9)',b'(#7,#999)'))
        with self.assertRaisesRegex(ValueError,'unsupported unit'):
            audit_wire(raw.replace(b'.MILLI.',b'.INCH.'))
        self.assertEqual(audit_wire(raw.replace(b'.MILLI.',b'$'))['total_length_mm'],10000)

    def test_bytes_differ_but_renumbered_geometry_is_identical(self):
        raw=wire_fixture()
        changed=raw.replace(b'#9',b'#90').replace(b'quoted;name',b'other;name')
        self.assertFalse(byte_compare(raw,changed)['equal'])
        self.assertEqual(audit_wire(raw)['geometry_signature'],audit_wire(changed)['geometry_signature'])
        self.assertEqual(len(parse(raw)[1]),9)
        with self.assertRaisesRegex(ValueError,'duplicate'):
            parse(raw.replace(b'ENDSEC;END-ISO',b'#9=CARTESIAN_POINT(\'\',(1.,0.,0.));ENDSEC;END-ISO'))
        with self.assertRaisesRegex(ValueError,'regular'):
            audit_wire(raw.replace(b"('',1,(#7,#9)",b"('',2,(#7,#9)"))

    def test_returned_interface_observations_are_explicit_and_read_only(self):
        iid='expected-step-iid'
        info=SimpleNamespace(GetDocumentation=lambda index:('IImportStepData','','',0),GetTypeAttr=lambda:(iid,))
        def query(requested,wrapper=None):
            if wrapper is None:
                raise TypeError("There is no interface object registered that supports this IID")
            self.assertEqual((requested,wrapper),(iid,'IUnknown-wrapper'))
            return object()
        dispatch=SimpleNamespace(GetTypeInfoCount=lambda:1,GetTypeInfo=lambda:info,QueryInterface=mock.Mock(side_effect=query))
        value=SimpleNamespace(_oleobj_=dispatch,MapConfigurationData=False)
        with mock.patch.dict('sys.modules',{'pythoncom':SimpleNamespace(IID_IUnknown='IUnknown-wrapper')}):
            result=observe_dispatch(value,{'IImportStepData':iid},lambda label,fn:fn(),'data',step_mapping=True)
        self.assertTrue(result['returned'])
        self.assertEqual(result['typeinfo']['value']['iid'],iid)
        self.assertTrue(result['interfaces']['IImportStepData']['value'])
        self.assertIs(result['map_configuration_data']['value'],False)
        dispatch.QueryInterface.assert_called_once_with(iid,'IUnknown-wrapper')
        self.assertEqual(result['interface_query_wrapper'],'IUnknown')
        none=observe_dispatch(None,{},lambda label,fn:fn(),'model')
        self.assertFalse(none['returned'])
        self.assertNotIn('typeinfo',none)

    def test_unknown_probe_does_not_replace_first_native_error_or_retry(self):
        module_name='step_diagnostic_failure_test'
        spec=importlib.util.spec_from_file_location(module_name,ROOT/'scripts/ci/verify-step-export-calibration.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        first=RuntimeError('first LoadFile4 native failure')
        bad=SimpleNamespace(_oleobj_=SimpleNamespace(GetTypeInfoCount=mock.Mock(side_effect=ValueError('no metadata')),
            QueryInterface=mock.Mock(side_effect=RuntimeError('diagnostic interface failure'))))
        class Variant:
            value=0
            def __init__(self,*args):pass
        app=SimpleNamespace(GetImportFileData=mock.Mock(return_value=bad),LoadFile4=mock.Mock(side_effect=first),
            SetUserPreferenceToggle=mock.Mock(),SetUserPreferenceIntegerValue=mock.Mock())
        codes={name:i for i,name in enumerate(module.IMPORT_PROFILE)}
        app.GetUserPreferenceToggle=lambda code:True
        app.GetUserPreferenceIntegerValue=lambda code:0
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict('sys.modules',{
                'pythoncom':SimpleNamespace(VT_BYREF=1,VT_I4=2,IID_IUnknown='IUnknown-wrapper'),
                'win32com':SimpleNamespace(client=SimpleNamespace(VARIANT=Variant)),
                'win32com.client':SimpleNamespace(VARIANT=Variant)}):
            root=Path(directory); target=root/'part.step';target.write_bytes(wire_fixture())
            (root/'import-interface-contract.json').write_text('{"interfaces": {"IImportStepData": "installed-step-iid"}}')
            case={}
            with self.assertRaises(RuntimeError) as caught:
                module._verify_imported_geometry(app,target,root,'part','wireframe',codes,lambda label,fn:fn(),case,{'document':None})
            self.assertIs(caught.exception,first)
            self.assertEqual(case['import_return']['state'],'raised')
            self.assertEqual(case['import_return']['error']['message'],'first LoadFile4 native failure')
            self.assertEqual(case['import_data_observation']['typeinfo']['status'],'unknown')
            self.assertEqual(case['actual_import_preferences']['swMultiCAD_Enable3DInterconnect']['status'],'observed')
            self.assertEqual(case['actual_import_preferences']['swImportNeutral_FreeCurvesAndPoints']['status'],'unknown')
            app.SetUserPreferenceToggle.assert_not_called()
            app.SetUserPreferenceIntegerValue.assert_not_called()
            app.GetImportFileData.assert_called_once_with(str(target))
            app.LoadFile4.assert_called_once()
            self.assertEqual(case['import_data_observation']['interfaces']['IImportStepData']['status'],'unknown')
            bad._oleobj_.QueryInterface.assert_called_once_with('installed-step-iid','IUnknown-wrapper')

    def test_null_failed_import_is_explicitly_unavailable_not_zero_geometry(self):
        spec=importlib.util.spec_from_file_location('step_null_import_test',ROOT/'scripts/ci/verify-step-export-calibration.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        class Variant:
            def __init__(self,*args):self.value=0
        def load(path,arg,data,errors):
            errors.value=1
            return None
        app=SimpleNamespace(GetImportFileData=mock.Mock(return_value=object()),LoadFile4=mock.Mock(side_effect=load),
            GetUserPreferenceToggle=lambda code:False,GetUserPreferenceIntegerValue=lambda code:0)
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict('sys.modules',{
                'pythoncom':SimpleNamespace(VT_BYREF=1,VT_I4=2),
                'win32com':SimpleNamespace(client=SimpleNamespace(VARIANT=Variant)),
                'win32com.client':SimpleNamespace(VARIANT=Variant)}):
            root=Path(directory);target=root/'part.step';target.write_bytes(wire_fixture());case={};live={}
            with self.assertRaisesRegex(RuntimeError,'STEP geometry readback failed'):
                module._verify_imported_geometry(app,target,root,'part','wireframe',{},lambda label,fn:fn(),case,live)
            self.assertEqual(case['import_return']['state'],'returned')
            self.assertFalse(case['import_return']['document_returned'])
            self.assertEqual(case['import_return']['errors'],1)
            self.assertNotIn('imported_geometry',case)
            self.assertNotIn('imported_save',case)
            self.assertIsNone(live['document'])
            app.LoadFile4.assert_called_once_with(str(target),'r',app.GetImportFileData.return_value,mock.ANY)

    def test_representation_assertion_follows_all_supported_geometry_observation(self):
        spec=importlib.util.spec_from_file_location('step_complete_inventory_test',ROOT/'scripts/ci/verify-step-export-calibration.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        edges=[SimpleNamespace(GetCurve=SimpleNamespace(GetLength3=lambda low,high:high-low),
            GetCurveParams3=SimpleNamespace(UMinValue=0.0,UMaxValue=value/1000,Sense=True)) for value in [30]*4+[40]*4]
        reference=SimpleNamespace(GetID=27,Name='Curve',GetTypeName2='ImportedCurve',
            GetSpecificFeature2=SimpleNamespace(GetSegmentCount=8,GetSegments=edges),GetNextFeature=None,
            GetFirstSubFeature=None,GetNextSubFeature=None)
        sketch=SimpleNamespace(GetID=26,Name='Sketch',GetTypeName2='3DProfileFeature',
            GetSpecificFeature2=SimpleNamespace(GetSketchSegments=[SimpleNamespace(GetLength=0.01)]*4),
            GetNextFeature=reference,GetFirstSubFeature=None,GetNextSubFeature=None)
        partial={}
        with self.assertRaisesRegex(RuntimeError,'unexpectedly produced sketch'):
            module.read_wireframe(SimpleNamespace(FirstFeature=sketch,GetBodies2=lambda *args:()),partial,
                                  representation='reference-curves')
        self.assertEqual(partial['segment_count'],12)
        self.assertEqual(partial['total_length_mm'],320)
        self.assertEqual(partial['representation_mismatches'],[26])
        self.assertFalse(partial['complete'])
        self.assertEqual(len(partial['feature_inventory']),2)

    def test_typelib_contract_uses_installed_interface_ids(self):
        names=['IImportStepData','IImportIgesData']
        library=SimpleNamespace(GetTypeInfoCount=lambda:2,GetTypeInfo=lambda index:SimpleNamespace(
            GetDocumentation=lambda member:(names[index],),GetTypeAttr=lambda:('iid-'+names[index],)))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sldworks.tlb';path.write_bytes(b'library bytes')
            result=read_interface_contract(path,SimpleNamespace(LoadTypeLib=lambda value:library))
            self.assertEqual(result['interfaces'],{name:'iid-'+name for name in names})
            self.assertEqual(len(result['sha256']),64)

    def test_document_diagnostics_preserve_each_case_native_save_name(self):
        spec=importlib.util.spec_from_file_location('step_success_import_test',ROOT/'scripts/ci/verify-step-export-calibration.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        class Variant:
            def __init__(self,*args):self.value=0
        document=SimpleNamespace(GetType=1,GetTitle='Imported',GetPathName='',GetSaveFlag=False)
        app=SimpleNamespace(GetImportFileData=mock.Mock(return_value=object()),LoadFile4=mock.Mock(return_value=document),
            GetUserPreferenceToggle=lambda code:False,GetUserPreferenceIntegerValue=lambda code:0,
            CloseDoc=mock.Mock(),GetDocumentCount=0)
        def save(path,**kwargs):
            Path(path).write_bytes(b'native bytes')
            return {'ok':True}
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict('sys.modules',{
                'pythoncom':SimpleNamespace(VT_BYREF=1,VT_I4=2),
                'win32com':SimpleNamespace(client=SimpleNamespace(VARIANT=Variant)),
                'win32com.client':SimpleNamespace(VARIANT=Variant)}), \
                mock.patch.object(module,'check_box',return_value={}), \
                mock.patch.object(module,'verify_reopened_geometry'), \
                mock.patch.object(module,'save_as_native_windows',side_effect=save) as saved, \
                mock.patch.object(module,'open_windows_document_with_handle',return_value=(
                    {'ok':True,'api_errors':0,'api_warnings':0},document)):
            root=Path(directory)
            for name in ('ap203-solid-surface','sdk-ap214-solid-surface'):
                target=root/(name+'.step');target.write_bytes(wire_fixture());case={};live={}
                module._verify_imported_geometry(app,target,root,name,'solid-surface',{},lambda label,fn:fn(),case,live)
                self.assertEqual(saved.call_args.args[0],str(root/(name+'-imported.SLDPRT')))
                self.assertTrue(case['success'])
                self.assertEqual(case['import_document_observation']['GetType']['value'],1)
                self.assertIsNone(live['document'])
            self.assertEqual(app.LoadFile4.call_count,2)
            self.assertEqual(len(list(root.glob('*-imported.SLDPRT'))),2)

    def test_query_interface_keeps_com_refusal_separate_from_unknown_diagnostics(self):
        class ComError(Exception):
            def __init__(self,code):self.hresult=code
        for failure,expected in ((ComError(-2147467262),{'status':'observed','value':False}),
                                 (ComError(-2147467259),None),(TypeError('wrapper failure'),None)):
            dispatch=SimpleNamespace(GetTypeInfoCount=lambda:0,QueryInterface=mock.Mock(side_effect=failure))
            value=SimpleNamespace(_oleobj_=dispatch)
            with mock.patch.dict('sys.modules',{'pythoncom':SimpleNamespace(IID_IUnknown='IUnknown-wrapper')}):
                result=observe_dispatch(value,{'IImportStepData':'installed-step-iid'},lambda label,fn:fn(),'data',step_mapping=True)
            observed=result['interfaces']['IImportStepData']
            if expected is not None:
                self.assertEqual(observed,expected)
            else:
                self.assertEqual(observed['status'],'unknown')
                self.assertEqual(observed['error']['type'],type(failure).__name__)
            self.assertEqual(result['map_configuration_data']['status'],'unknown')
            dispatch.QueryInterface.assert_called_once_with('installed-step-iid','IUnknown-wrapper')
