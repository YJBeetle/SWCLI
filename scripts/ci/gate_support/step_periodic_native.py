"""Native adapter for the independent public periodic readback; imports do not start COM/CAD."""
from contextlib import contextmanager
import hashlib
import importlib.metadata
import importlib.util
import math
from pathlib import Path
import sys

from .step_periodic_driver import DriverFailure, require, digest
from .step_periodic_evidence import verify_cylinder_mass
from .step_feature_inventory import walk_features
from . import step_null_binding, step_explicit_null_binding
from .step_import_observation import read_interface_contract, observe_dispatch
from .step_sketch_readback_candidate import NON_GEOMETRY_TYPES, preferences


# Exact direct children of the observed root containers in the native 33.5.0 tree.
# This policy applies only to the independent cylinder calibration.
PERIODIC_NON_GEOMETRY_TYPES = NON_GEOMETRY_TYPES | {'ConfigTableFolder'}
PERIODIC_CONTAINER_CHILDREN = {
    'DetailCabinet': frozenset({'AnnotationViewFeat', 'FtrFolder'}),
    'ConfigTableFolder': frozenset({'NativeConfigurationTableFeature'}),
}


def validate_setter_contract(methods):
    toggle=methods['SetUserPreferenceToggle'];integer=methods['SetUserPreferenceIntegerValue']
    for row,dispid in ((toggle,45),(integer,51)):
        require(row['interface']['name']=='ISldWorks' and row['interface']['guid']==step_explicit_null_binding.ISLDWORKS_IID
                and row['dispid']==dispid and row['optional_count']==0 and row['return_type']['type']=='VT_HRESULT','installed setter identity differs')
    def signature(row):return [(p['name'],p['flags'],p['datatype']['type']) for p in row['parameters']]
    require(signature(toggle)==[('UserPreferenceValue',1,'VT_I4'),('OnFlag',1,'VT_BOOL')],'toggle must have two inputs and no retval')
    require(signature(integer)==[('UserPreferenceValue',1,'VT_I4'),('Value',1,'VT_I4'),('Retval',10,'VT_PTR')]
            and integer['parameters'][2]['datatype']['target']['type']=='VT_BOOL','integer setter BOOL retval differs')
    return dict(verified=True,methods={name:methods[name] for name in ('SetUserPreferenceToggle','SetUserPreferenceIntegerValue')},
                toggle_python_return='None (void; native HRESULT is not a BOOL retval)',integer_python_return='strict True; reject False/unknown')


def installed_setter_contract(path):
    parser_path=Path(__file__).resolve().parents[1]/'inspect-step-loadfile4-metadata.py'
    spec=importlib.util.spec_from_file_location('_periodic_setter_tlb_parser',parser_path)
    parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
    methods=parser.typelib(Path(path).read_bytes(),('LoadFile4','GetImportFileData','SetUserPreferenceToggle','SetUserPreferenceIntegerValue'))
    result=validate_setter_contract(methods)
    result.update(tlb_sha256=digest(path),parser_sha256=digest(parser_path),scope='static pinned installed TLB parse; no native setter or COM invocation')
    return result


class NativeAPI:
    def __init__(self, recorder):
        from swcli.daemon import server, operations
        from swcli.hosts import windows, windows_step_export, windows_step_periodic, windows_documents, windows_measurements, windows_native_files, windows_save_as
        spec=importlib.util.spec_from_file_location('_periodic_reader_tools',Path(__file__).resolve().parents[1]/'verify-step-export-calibration.py')
        self.reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.reader)
        self.recorder=recorder
        self.server,self.operations=server,operations
        self.windows,self.step,self.periodic=windows,windows_step_export,windows_step_periodic
        self.docs,self.measurements,self.files=windows_documents,windows_measurements,windows_native_files
        self.save_adapter = windows_save_as
        self.constants={};self.interfaces={};self.health_records=[]

    def value(self,obj,name):return self.windows._com_value(obj,name)
    def same(self,app,first,second):return self.reader.harness._same(app,first,second)

    def proof(self,swconst):
        from swcli.hosts import step_part21

        require(self.step._native_windows_runtime() is True,'native Windows required before host acquisition')
        require(importlib.metadata.version('pywin32')=='312','only reviewed pywin32 b312 is accepted')
        swconst = Path(swconst).resolve(strict=True)
        sldworks_tlb = swconst.with_name('sldworks.tlb')
        require(sldworks_tlb.resolve(strict=True) == sldworks_tlb, 'sldworks.tlb must be beside swconst.tlb')
        package=step_null_binding.attest_package()
        contract=step_explicit_null_binding.installed_contract(sldworks_tlb)
        setters=installed_setter_contract(sldworks_tlb)
        scripts=Path(__file__).resolve().parents[1]
        modules = [self.step, self.periodic, self.docs, self.operations, self.reader, self.files,
                   self.save_adapter, step_part21, step_explicit_null_binding, step_null_binding]
        sources={str(Path(module.__file__).resolve()):digest(module.__file__) for module in modules}
        for relative in ('gate_support/step_periodic_driver.py','gate_support/step_periodic_native.py','gate_support/step_periodic_supervisor.py','gate_support/step_periodic_launch.py','gate_support/step_periodic_evidence.py','gate_support/step_wire_evidence.py','gate_support/step_feature_inventory.py','gate_support/step_periodic_public.py','verify-step-export-public.py','verify-step-periodic-readback.py','gate_support/step_sketch_readback_candidate.py'):
            file=scripts/relative;sources[str(file)]=digest(file)
        sources[str(swconst)] = digest(swconst)
        sources[str(sldworks_tlb)] = digest(sldworks_tlb)
        require(sources[str(sldworks_tlb)] == contract['tlb_sha256'], 'sldworks.tlb changed after ABI validation')
        sources[str((scripts/'inspect-step-loadfile4-metadata.py').resolve())]=digest(scripts/'inspect-step-loadfile4-metadata.py')
        self.fingerprints=sources
        return dict(native_windows_observed=True,pywin32_version_observed='312',binding_package=package,installed_invocation_contract=contract,setter_contract=setters,source_files_sha256=sources,
                    swconst_sha256=sources[str(swconst)],requested_swconst_path=str(swconst),
                    source_hash_scope='effective runtime Python and installed TLB bytes; coordinator must compare checkout CRLF/package bytes to exact head; not native DLL memory attestation',
                    import_selection='one preselected explicit NULL IDispatch with fixed eight-value import profile; no fallback or cross-head causality claim')

    def tracing(self):return instrument(self,self.recorder)

    def assert_sources(self):
        for path,expected in self.fingerprints.items():
            observed=digest(path)
            if observed!=expected:
                self.recorder.report['source_fingerprint_conflict']=dict(file=path,expected=expected,observed=observed)
                raise DriverFailure('runtime source file changed after preflight')

    def initialize(self):
        import pythoncom
        import win32com.client as client
        self.pythoncom,self.client=pythoncom,client;pythoncom.CoInitialize()
    def uninitialize(self):self.pythoncom.CoUninitialize()
    def verify_installation(self, app, requested):
        installed = self.step.resolve_step_swconst(app)
        observation = {'requested_swconst_path': str(requested), 'host_swconst_path': str(installed)}
        self.recorder.report['host_installation'] = observation
        require(installed == Path(requested).resolve(strict=True), 'host swconst.tlb path differs from the inspected installation')
        sibling = installed.with_name('sldworks.tlb')
        require(sibling.resolve(strict=True) == sibling, 'host sldworks.tlb path changed after inspection')
        self.assert_sources()
        observation.update(
            swconst_sha256=self.fingerprints[str(installed)],
            sldworks_tlb_sha256=self.fingerprints[str(sibling)],
            verified=True,
        )
        return installed

    def read_constants(self, path):
        sibling = path.with_name('sldworks.tlb')
        contract = read_interface_contract(sibling, self.pythoncom)
        require(contract['sha256'] == self.fingerprints[str(sibling)], 'import interface type library changed')
        self.interfaces = contract['interfaces']
        self.recorder.report['host_import_interfaces'] = contract
        self.constants = {**self.step.read_step_constants(path), **self.reader.read_import_constants(path)}
        self.constants['swStepExportSplitPeriodic'] = self.periodic.read_periodic_constant(path)
        self.assert_sources()
        return self.constants
    def acquire(self):return self.server.acquire_resident_app(self.client,visible=False)
    def ready(self,app):return self.windows.wait_windows_host_ready(app,timeout_seconds=120)
    def capture(self,pid):return self.reader.harness.capture_process(pid)
    def wait(self,handle):return self.reader.harness.wait_process(handle)
    def close_handle(self,handle):handle.Close()
    def exit(self,app):return self.value(app,'ExitApp')
    def save(self,path,document):return self.files.save_as_native_windows(str(path),document=document)
    def open(self,path,app):return self.docs.open_windows_document_with_handle(str(path),read_only=True,app=app)
    def mass(self,document):return self.measurements.measure_part_windows(document=document)
    def topology(self,document):
        bodies=tuple(self.recorder.call('GetBodies2.native-topology',lambda:document.GetBodies2(0,False)) or ())
        require(len(bodies)==1,'native topology requires one solid body')
        faces=self.value(bodies[0],'GetFaceCount');edges=self.value(bodies[0],'GetEdgeCount')
        require(type(faces) is int and faces in (3,4) and type(edges) is int and edges>0,'native cylinder topology unknown')
        return dict(solid_body_count=1,face_count=faces,edge_count=edges)



    def health(self, document, scope, app):
        require(scope in ('source', 'imported'), 'unknown periodic feature scope')
        expected = {'ProfileFeature', 'Extrusion'} if scope == 'source' else {'Imported'}
        result = dict(complete=False, scope=scope, features=[])
        self.health_records.append(result)
        observed = {}
        sketch_alias_seen = False
        try:
            for feature, index, parent_index, depth in walk_features(document, self.value):
                identity = self.value(feature, 'GetID')
                kind = self.value(feature, 'GetTypeName2')
                name = self.value(feature, 'Name')
                parent = result['features'][parent_index] if parent_index is not None else None
                row = dict(index=index, parent_index=parent_index, feature_id=identity,
                           parent_id=parent['feature_id'] if parent else None,
                           depth=depth, kind=kind, name=name)
                result['features'].append(row)
                self.recorder.persist()
                require(type(identity) is int and isinstance(kind, str) and kind and isinstance(name, str),
                        'unreadable native feature row')
                if kind in PERIODIC_NON_GEOMETRY_TYPES:
                    continue
                if depth == 1 and kind in PERIODIC_CONTAINER_CHILDREN.get(parent['kind'], ()):
                    row['role'] = 'container-metadata'
                    continue
                # The known NULL-STEP readback showed BaseBody. It still counts
                # as the one imported geometry producer and must pass health.
                role = 'Imported' if scope == 'imported' and depth == 0 and kind == 'BaseBody' else kind
                require(role in expected and (scope == 'source' or depth == 0),
                        'unknown geometry feature type: ' + kind)
                require(identity > 0, 'business feature identity is not positive')
                warning = self.client.VARIANT(self.pythoncom.VT_BYREF | self.pythoncom.VT_BOOL, False)
                code = self.recorder.call('feature.GetErrorCode2', lambda: feature.GetErrorCode2(warning))
                row['health'] = dict(code=code, is_warning=warning.value if code != 0 else None)
                require(type(code) is int and code == 0, 'nonzero/unknown feature health')
                if role in observed:
                    original, original_row = observed[role]
                    top_level, absorbed = sorted((original_row, row), key=lambda entry: entry['depth'])
                    require(role == 'ProfileFeature' and identity == original_row['feature_id']
                            and top_level['depth'] == 0 and absorbed['depth'] == 1
                            and result['features'][absorbed['parent_index']]['kind'] == 'Extrusion'
                            and not sketch_alias_seen
                            and self.recorder.call('feature.IsSame', lambda: self.same(app, original, feature)),
                            'incomplete/extra cylinder business features')
                    row['same_feature_as'] = original_row['index']
                    sketch_alias_seen = True
                else:
                    require(all(identity != existing['feature_id'] for _, existing in observed.values()),
                            'distinct business feature types share an ID')
                    observed[role] = (feature, row)
                row['role'] = role
            require(set(observed) == expected, 'incomplete/extra cylinder business features')
            result['complete'] = True
            return result
        except BaseException as exc:
            result['first_error'] = dict(type=type(exc).__name__, message=str(exc))
            raise

    def compare_mass(self,before,after):
        verify_cylinder_mass(before);verify_cylinder_mass(after)
        require(type(before['bodies'][0].get('index')) is int and type(after['bodies'][0].get('index')) is int and before['bodies'][0]['index']==after['bodies'][0]['index']==0,'native body index changed/unknown')
        for first,last in ((before['metrics'],after['metrics']),(before['bodies'][0],after['bodies'][0])):
            for key in ('volume_mm3','surface_area_mm2'):require(math.isclose(first[key],last[key],rel_tol=1e-7,abs_tol=1e-5),'save/reopen physical quantity changed')
            for key in 'xyz':require(math.isclose(first['centroid_mm'][key],last['centroid_mm'][key],rel_tol=0,abs_tol=1e-9),'save/reopen centroid changed')

    def import_preferences(self,app,case,recorder):return preferences(app,self.constants,recorder.call,case,recorder.persist,neutral_free_candidate=True)

    def import_once(self,app,target,case,proof,verify,recorder):
        require('import_return' not in case,'one import only, no retry')
        case['import_return']=dict(state='started',document_returned=None,errors=None,arg_string='r',import_data='explicit NULL IDispatch')
        data=recorder.call('GetImportFileData',lambda:app.GetImportFileData(str(target)))
        case['import_data_observation']=observe_dispatch(data,self.interfaces,recorder.call,'observe-import-data',step_mapping=True)
        observation=case['import_data_observation']
        require(observation.get('returned') is True and observation.get('interfaces',{}).get('IImportStepData')==dict(status='observed',value=True),'STEP factory interface is unknown')
        require(observation.get('map_configuration_data',{}).get('status')=='observed','STEP factory mapping unknown')
        evidence=case['binding']=dict(scope='reuse of verified mechanism only; historical comparison labels are not a new causal experiment')
        binding=step_explicit_null_binding.InstalledTlbNullInvoke(app,self.client.VARIANT,self.pythoncom,
            proof['binding_package'],proof['installed_invocation_contract'],evidence,recorder.call,recorder.persist,comparison_baseline='f56f792')
        errors=self.client.VARIANT(self.pythoncom.VT_BYREF|self.pythoncom.VT_I4,0)
        require(self.value(app,'GetProcessID')==recorder.report['host']['process_id'] and self.value(app,'Visible') is False,'host changed before LoadFile4')
        require(digest(target)==case['sha256'],'STEP changed before unique import')
        verify()  # Final full-eight CAS, after all binding/owner/file observations.
        try:
            document=recorder.call('LoadFile4',lambda:binding.invoke_explicit(str(target),'r',binding.argument,errors))
        except BaseException as exc:
            case['import_return'].update(state='raised',errors=errors.value,error=dict(type=type(exc).__name__,message=str(exc)));raise
        case['import_return'].update(state='returned',errors=errors.value,document_returned=document is not None,python_type=type(document).__name__)
        return document


@contextmanager
def instrument(api,recorder):
    """Bound every imported COM observation/native_call, including existing helper aliases."""
    from swcli.hosts import windows,native_trace
    original_value,original_call=windows._com_value,native_trace.native_call
    def value(obj,name):return recorder.call('observe:'+name,lambda:original_value(obj,name))
    def call(stage,name,function):return recorder.call('native:'+stage+':'+name,function)
    changes=[];modules=list(sys.modules.values())+[api.reader,api.reader.harness]
    for module in modules:
        name=getattr(module,'__name__','')
        if not (name.startswith(('swcli.hosts','swcli.daemon','gate_support')) or module in (api.reader,api.reader.harness)):continue
        for attribute,original,replacement in (('_com_value',original_value,value),('native_call',original_call,call)):
            if getattr(module,attribute,None) is original:
                changes.append((module,attribute,original));setattr(module,attribute,replacement)
    try:yield
    finally:
        for module,attribute,original in reversed(changes):setattr(module,attribute,original)
