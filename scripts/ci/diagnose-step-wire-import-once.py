"""Single AP203 wire import hypothesis prepared for root review. Zero save/new/export/select.

No CI entry or VM control. Existing owned harness, same600s/1800s deadlines.
Every diagnostic error stops the case; only owned cleanup may follow.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import importlib.util
import json
import ntpath
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
SOURCE_ROOT = HERE.parent.parent
if not (SOURCE_ROOT / 'src/swcli/hosts/windows_step_export.py').is_file():
    raise RuntimeError('Run from the reviewed isolated STEP source snapshot, never a partial script copy')
sys.path.insert(0, str(SOURCE_ROOT / 'src'))
sys.path.insert(0, str(HERE))
from gate_support.step_import_observation import TOGGLES, INTEGERS, error
from swcli.hosts.windows_step_export import _native_windows_runtime, _read_native_enum_constants

spec = importlib.util.spec_from_file_location('_step_wire_once_owned', HERE / 'verify-through-all-calibration.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
reader_spec = importlib.util.spec_from_file_location('_step_wire_observer', HERE / 'verify-step-export-calibration.py')
reader = importlib.util.module_from_spec(reader_spec)
reader_spec.loader.exec_module(reader)
INPUT = r'C:\Workspace\SWCLI-series-20261111\step-qi-input\ap203-wireframe.step'
EVIDENCE_ROOT = r'C:\Workspace\SWCLI-series-20261111\step-wire-import-evidence'
NEUTRAL_3D_EVIDENCE_ROOT = r'C:\Workspace\SWCLI-series-20261111\step-wire-neutral-3d-evidence'
INPUT_SHA = '3a4f032699665f22b6ee40b4b552fed904c6297c56aecf310e4645b70ed72c90'
STEP_IID = '{AD749A73-9AA2-4A3E-BCA5-8FC012114BB0}'
LIBRARY_HASHES = {
    'swconst.tlb': '95e36f79890b9dcfb6048218af1f46e2244df60e689a7fba62091e37d47005d6',
    'sldworks.tlb': '585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159',
}
SOURCE = dict(run_id=42413805736, head='060f26178b4deabc330ef0959b9ec0f1704159cf', artifact_id=13591430613,
              zip_sha256='de9e6312b9fbfa0c4b0001ae1f54ce5c36d24ea3f59ee435b691716bef1666e7')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def plain(path):
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            st = item.lstat()
            require(not item.is_symlink() and not getattr(st, 'st_file_attributes', 0) & 0x400,
                    'Path contains a link/reparse point')


def input_metadata():
    path = Path(INPUT)
    plain(path)
    require(path.is_file() and ntpath.normcase(str(path.resolve())) == ntpath.normcase(INPUT), 'Fixed input path differs')
    def snapshot():
        st = path.stat()
        return dict(size=st.st_size, device=st.st_dev, file_id=st.st_ino,
                    mtime_ns=st.st_mtime_ns, ctime_ns=st.st_ctime_ns,
                    attributes=getattr(st, 'st_file_attributes', 0))
    before = snapshot()
    require(before['attributes'] & 1, 'Fixed input must already have Windows READONLY attribute')
    # No chmod/attribute setter, copy, extraction, repair or source write.
    with path.open('rb') as stream:
        digest = hashlib.sha256(stream.read()).hexdigest()
    require(snapshot() == before and digest == INPUT_SHA, 'Fixed input metadata/hash differs')
    return dict(path=INPUT, sha256=digest, readonly=True, metadata=before, original_source=SOURCE)


def native_pids():
    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, timeout=10, check=True)
    rows = list(csv.reader(result.stdout.splitlines()))
    require(rows and all(len(row) >= 2 and row[1].isdecimal() for row in rows), 'Native process inventory is unknown')
    return [int(row[1]) for row in rows if ntpath.basename(row[0]).lower() == 'sldworks.exe']


class ReadOnlyDocument:
    ALLOWED = frozenset(('GetTitle', 'GetType', 'GetPathName', 'GetBodies2', 'FirstFeature'))
    def __init__(self, document):
        self.raw = document
        self.title = None
    def __getattr__(self, name):
        require(name in self.ALLOWED and self.raw is not None, 'Forbidden/released document member: ' + name)
        if name == 'GetTitle':
            def title():
                self.title = harness._com_value(self.raw, 'GetTitle')
                require(isinstance(self.title, str) and self.title, 'Owned import title is unavailable')
                return self.title
            return title
        return getattr(self.raw, name)
    def release(self):
        self.raw = None


class ImportOnceApp:
    ALLOWED = frozenset(('GetDocumentCount', 'GetProcessID', 'RevisionNumber', 'Visible', 'StartupProcessCompleted',
                         'ExitApp', 'GetUserPreferenceToggle', 'GetUserPreferenceIntegerValue',
                         'SetUserPreferenceToggle', 'SetUserPreferenceIntegerValue'))
    def __init__(self, app, constants, *, neutral_3d_candidate=False):
        object.__setattr__(self, '_app', app)
        object.__setattr__(self, '_constants', dict(constants))
        object.__setattr__(self, '_neutral_3d_candidate', neutral_3d_candidate)
        object.__setattr__(self, '_data_attempted', False)
        object.__setattr__(self, '_load_attempted', False)
        object.__setattr__(self, '_close_attempted', False)
        object.__setattr__(self, '_data', None)
        object.__setattr__(self, '_document', None)
        object.__setattr__(self, '_raw_document_type', None)
    def __getattr__(self, name):
        require(name in self.ALLOWED, 'Forbidden CAD member: ' + name)
        if name in ('SetUserPreferenceToggle','SetUserPreferenceIntegerValue'):
            allowed = PreferenceTransaction.GENERAL + (PreferenceTransaction.EXTRA,)
            if self._neutral_3d_candidate:
                allowed += (PreferenceTransaction.CURVE,)
            ids = {self._constants[key] for key in allowed if (key in TOGGLES) == (name == 'SetUserPreferenceToggle')}
            def write(code, value):
                require(code in ids, 'Unowned diagnostic preference setter is forbidden')
                return getattr(self._app,name)(code,value)
            return write
        return getattr(self._app, name)
    def __setattr__(self, name, value):
        raise RuntimeError('Host property writes are forbidden')
    def GetImportFileData(self, path):
        require(path == INPUT and not self._data_attempted, 'GetImportFileData requires fixed input and one attempt')
        object.__setattr__(self, '_data_attempted', True)
        data = self._app.GetImportFileData(path)
        object.__setattr__(self, '_data', data)
        return data
    def LoadFile4(self, path, arguments, data, errors):
        require(path == INPUT and arguments == 'r' and data is self._data and data is not None and not self._load_attempted,
                'LoadFile4 requires the same data object/fixed arguments and one attempt')
        object.__setattr__(self, '_load_attempted', True)
        document = self._app.LoadFile4(path, arguments, data, errors)
        object.__setattr__(self, '_raw_document_type', type(document).__module__ + '.' + type(document).__name__)
        wrapped = ReadOnlyDocument(document) if document is not None else None
        object.__setattr__(self, '_document', wrapped)
        return wrapped
    def release_data(self):
        object.__setattr__(self, '_data', None)
    def CloseDoc(self, title):
        document = self._document
        require(document is not None and document.title == title and not self._close_attempted,
                'CloseDoc only permits this owned imported document once')
        object.__setattr__(self, '_close_attempted', True)
        try:
            return self._app.CloseDoc(title)
        finally:
            document.release()


def strict(case, call, label, function, predicate=lambda value: True):
    row = case[label] = dict(status='started')
    try:
        value = call(label, function)
        require(predicate(value), 'Diagnostic value is unknown/invalid: ' + label)
    except BaseException as exc:
        row.update(status='unknown', error=error(exc))
        raise
    row.update(status='observed', value=value)
    return value


class PreferenceTransaction:
    """Eight-value CAS; restore only this transaction's attempted writes."""
    GENERAL = ('swMultiCAD_Enable3DInterconnect', 'swImportSolidSurface', 'swImportFreeCurves', 'swImportCurvePreference')
    EXTRA = 'swImportNeutral_FreeCurvesAndPoints'
    CURVE = 'swImportNeutral_CurvesAndPointsOption'
    def __init__(self, app, constants, call, case, report, output):
        self.app, self.constants, self.call = app, constants, call
        self.neutral_3d_candidate = app._neutral_3d_candidate
        self.writable = self.GENERAL + (self.EXTRA,) + ((self.CURVE,) if self.neutral_3d_candidate else ())
        self.case, self.report, self.output = case, report, output
        self.evidence = case['preferences'] = dict(snapshot=None, stages=[], reads=[], writes=[], restore=[], restored=False)
        self.before, self.expected = None, None
        self.owned = []
    def persist(self):
        write_json(self.output / 'report.json', self.report)
    def get(self, name, label):
        expected = bool if name in TOGGLES else int
        kind = 'Toggle' if expected is bool else 'IntegerValue'
        row = dict(label=label,name=name,status='started')
        self.evidence['reads'].append(row);self.persist()
        try:
            value = self.call(label + '.' + name, lambda: getattr(self.app, 'GetUserPreference' + kind)(self.constants[name]))
            row['value'] = value if type(value) in (bool,int,str,float,type(None)) else dict(python_type=type(value).__name__)
            self.persist()
            require(type(value) is expected, 'Preference type unknown: ' + name)
        except BaseException as exc:
            row.update(status='unknown',error=error(exc));self.persist();raise
        row['status'] = 'observed';self.persist()
        return value
    def snapshot(self, label):
        row = dict(label=label, status='started', values={})
        self.evidence['stages'].append(row);self.persist()
        try:
            for name in TOGGLES + INTEGERS:
                row['values'][name] = self.get(name, label);self.persist()
        except BaseException as exc:
            row.update(status='unknown', error=error(exc));self.persist();raise
        row['status'] = 'observed';self.persist()
        return dict(row['values'])
    def setter(self, name, value, label, row):
        require(name in self.writable, 'Not a writable diagnostic preference')
        kind = 'Toggle' if name in TOGGLES else 'IntegerValue'
        row.update(status='attempted', possible_mutation=True);self.persist()
        try:
            returned = self.call(label + '.' + name, lambda: getattr(self.app, 'SetUserPreference' + kind)(self.constants[name], value))
            row['returned'] = returned if type(returned) in (bool,int,str,float,type(None)) else dict(python_type=type(returned).__name__)
            self.persist()
            require(returned is None if kind == 'Toggle' else returned is True, 'Preference setter refused/unknown: ' + name)
        except BaseException as exc:
            row.update(status='failed', error=error(exc));self.persist();raise
        row['status'] = 'returned';self.persist()
    def apply(self, name, value):
        require(self.snapshot('cas-before-set') == self.expected, 'Complete preference CAS mismatch')
        if self.expected[name] == value:
            return
        row = dict(name=name, original=self.before[name], requested=value)
        self.evidence['writes'].append(row);self.owned.append((name,value))
        self.setter(name,value,'set-owned-option',row)
        self.expected[name] = value
        observed = self.snapshot('readback-after-set')
        row['readback'] = observed;self.persist()
        require(observed == self.expected, 'Complete preference setter readback mismatch')
        row['status'] = 'verified';self.persist()
    def enter(self):
        before = self.snapshot('snapshot-original')
        self.before = before;self.expected = dict(before);self.evidence['snapshot'] = dict(before);self.persist()
        g0,g1 = (self.constants[n] for n in ('swGeneralImportAsSketches','swGeneralImportAs3dCurves'))
        n0,n1 = (self.constants[n] for n in ('swImportNeutralCurvesAndPointsOptions_AsSketches','swImportNeutralCurvesAndPointsOptions_As3DCurves'))
        if self.neutral_3d_candidate:
            require(type(n0) is int and type(n1) is int and (n0,n1) == (0,1), 'Official Neutral 0/1 enum contract differs')
        require(before['swImportCurvePreference'] in (g0,g1) and before['swImportNeutral_CurvesAndPointsOption'] in (n0,n1), 'Original curve modes unknown')
        require(before['swImportNeutral_SolidandSurface'] is True and before[self.EXTRA] is False
                and before['swImportNeutral_CurvesAndPointsOption'] == n0 and before['swImportStepConfigData'] is False,
                'Unowned/default values differ from the reviewed CI baseline; no normalization')
        require(self.snapshot('cas-original') == before, 'Initial complete preference CAS mismatch')
        for name,value in zip(self.GENERAL,(False,True,True,g1)):
            self.apply(name,value)
        ci = {**before, **dict(zip(self.GENERAL,(False,True,True,g1)))}
        self.evidence['ci_general_readback'] = self.snapshot('verify-exact-ci-general')
        require(self.evidence['ci_general_readback'] == ci, 'Old CI General profile readback mismatch')
        self.apply(self.EXTRA,True)
        previous = {**ci,self.EXTRA:True}
        if self.neutral_3d_candidate:
            # Verify the prepared previous vector without importing the baseline.
            self.evidence['d232e35_vector_readback'] = self.snapshot('verify-d232e35-vector-without-import')
            require(self.evidence['d232e35_vector_readback'] == previous, 'Previous diagnostic vector differs')
            self.apply(self.CURVE,n1)
        self.evidence['candidate_readback'] = self.snapshot('verify-candidate')
        expected_candidate = {**previous,self.CURVE:n1} if self.neutral_3d_candidate else previous
        require(self.evidence['candidate_readback'] == expected_candidate, 'Candidate differs beyond one reviewed value')
        if self.neutral_3d_candidate:
            self.evidence['changed_from_d232e35'] = [key for key in previous if previous[key] != expected_candidate[key]]
            require(self.evidence['changed_from_d232e35'] == [self.CURVE], 'Neutral candidate changes more than one value')
        self.persist()
    def restore(self):
        errors = self.evidence['restore_errors'] = []
        if not self.owned:
            self.evidence.update(restored=None,not_required_no_owned_writes=True)
            self.persist();return
        for name,requested in reversed(self.owned):
            row = dict(name=name, original=self.before[name], requested=requested)
            self.evidence['restore'].append(row);self.persist()
            try:
                current = self.get(name,'restore-owned-cas')
                row['current'] = current;self.persist()
                require(current in (self.before[name],requested), 'Owned restore value changed externally')
                if current == self.before[name]:
                    row['status'] = 'already-original';self.persist();continue
                self.setter(name,self.before[name],'restore-owned-option',row)
                row['readback'] = self.get(name,'restore-owned-readback');self.persist()
                require(row['readback'] == self.before[name], 'Owned restore readback mismatch')
                row['status'] = 'verified';self.persist()
            except Exception as exc:
                row.update(status='failed', error=error(exc));errors.append(dict(name=name, **error(exc)));self.persist()
        try:
            self.evidence['after'] = self.snapshot('verify-full-original-restored')
            require(self.evidence['after'] == self.before, 'Complete original vector did not restore; never write unowned fields')
        except Exception as exc:
            errors.append(error(exc))
        self.evidence['restored'] = not errors
        self.persist()


def case_runner(app, output, constants, plane, reverse, call, case, report, live, *, profile_kind):
    require(profile_kind == 'single-wire-import' and live['document'] is None, 'Unexpected diagnostic plan/document')
    case.update(scope='single-variable import diagnostic hypothesis, not acceptance',
                neutral_3d_candidate=app._neutral_3d_candidate, geometry=dict(status='unavailable', value=None),
                load_return=dict(state='not-attempted', document_returned=None, errors=None))
    case['input_before'] = call('verify-readonly-input-before', input_metadata)
    strict(case,call,'host-hidden',lambda:harness._com_value(app,'Visible'),lambda x:x is False)
    strict(case,call,'host-revision',lambda:harness._com_value(app,'RevisionNumber'),lambda x:x=='33.5.0')
    strict(case,call,'empty-catalog-before',lambda:harness._com_value(app,'GetDocumentCount'),lambda x:type(x) is int and x==0)
    transaction = PreferenceTransaction(app,constants,call,case,report,output)
    first = None;data = None
    try:
        transaction.enter()
        require(call('verify-input-before-load',input_metadata)==case['input_before'], 'Input changed before data/load')
        case['GetImportFileData'] = dict(status='started',returned=None);transaction.persist()
        try:
            data = call('GetImportFileData',lambda:app.GetImportFileData(INPUT))
        except BaseException as exc:
            case['GetImportFileData'].update(status='unknown',error=error(exc));transaction.persist();raise
        case['GetImportFileData'].update(status='observed',returned=data is not None,python_type=type(data).__module__+'.'+type(data).__name__)
        transaction.persist();require(data is not None, 'GetImportFileData returned None')
        import pythoncom
        from win32com.client import VARIANT
        def query():
            found = getattr(data,'_oleobj_',data).QueryInterface(constants['step_interface']['iid'],pythoncom.IID_IUnknown)
            require(found is not None, 'STEP QueryInterface returned None');return True
        strict(case,call,'IImportStepData.QueryInterface',query,lambda x:x is True);transaction.persist()
        strict(case,call,'MapConfigurationData',lambda:data.MapConfigurationData,lambda x:type(x) is bool);transaction.persist()
        require(transaction.snapshot('cas-before-one-load') == transaction.expected, 'Candidate preference CAS changed before LoadFile4')
        errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4,0)
        case['load_return'].update(state='started',arg_string='r',import_data='same factory object',possible_document_mutation=True);transaction.persist()
        try:
            document = call('LoadFile4',lambda:app.LoadFile4(INPUT,'r',data,errors))
        except BaseException as exc:
            case['load_return'].update(state='raised',errors=errors.value,error=error(exc));transaction.persist();raise
        live['document'] = document
        case['load_return'].update(state='returned',document_returned=document is not None,errors=errors.value,python_type=app._raw_document_type)
        transaction.persist()
        require(type(errors.value) is int and errors.value==0 and document is not None, 'STEP geometry readback failed')
        strict(case,call,'imported-document-type',lambda:harness._com_value(document,'GetType'),lambda x:type(x) is int and x==1)
        strict(case,call,'imported-document-title',lambda:harness._com_value(document,'GetTitle'),lambda x:isinstance(x,str) and bool(x))
        strict(case,call,'owned-import-count',lambda:harness._com_value(app,'GetDocumentCount'),lambda x:type(x) is int and x==1)
        raw = case['geometry']['raw_observation'] = {}
        transaction.persist()
        call('read-imported-wireframe',lambda:reader.read_wireframe(document,raw,representation='reference-curves'))
        reader.verify_wire_geometry(raw,'wireframe')
        case['geometry'].update(status='observed',value=dict(raw));transaction.persist()
        require(call('verify-input-after-observation',input_metadata)==case['input_before'], 'Input changed during import')
        case['success'] = True
    except BaseException as exc:
        first = exc
        case['first_error'] = error(exc);case['success'] = False
        transaction.persist();raise
    finally:
        data = None;app.release_data()
        transaction.restore()
        if not transaction.evidence['restored']:
            case['success'] = False
            if first is None:
                raise RuntimeError('Owned diagnostic preferences did not restore')


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def worker(args):
    output = args.output_dir
    acquisition = dict(created=None, returned=False)
    partial_errors = []
    original_acquire = harness.acquire_resident_app
    original_com_value = harness._com_value
    def observed_value(obj, name):
        with (output / 'observation-trace.jsonl').open('a', encoding='utf-8', buffering=1) as stream:
            stream.write(json.dumps(dict(call=name, phase='begin', time=time.time())) + '\n')
            try:
                value = original_com_value(obj, name)
            except BaseException:
                stream.write(json.dumps(dict(call=name, phase='error', time=time.time())) + '\n')
                raise
            stream.write(json.dumps(dict(call=name, phase='end', time=time.time())) + '\n')
            return value
    harness._com_value = observed_value
    original_reader_value = reader._com_value
    reader._com_value = observed_value
    neutral_3d_candidate = bool(getattr(args,'neutral_3d_candidate',False))
    diagnostic_case = 'step-wire-neutral-3d-once' if neutral_3d_candidate else 'step-wire-import-once'
    context = dict(neutral_3d_candidate=neutral_3d_candidate, production_public_acceptance=False, diagnostic_hypothesis=True, max_loadfile4=1, zero_save=True, zero_new=True, zero_select=True)
    try:
        require(_native_windows_runtime(), 'Verified native Windows is required')
        require(importlib.metadata.version('pywin32') == '312', 'Only reviewed pywin32312 wrapper semantics are allowed')
        context['input'] = input_metadata()
        require(args.swconst.name.casefold() == 'swconst.tlb', 'Enum library must be the hash-verified swconst.tlb')
        context['libraries'] = {}
        for name, expected in LIBRARY_HASHES.items():
            path = args.swconst.with_name(name)
            plain(path)
            observed = hashlib.sha256(path.read_bytes()).hexdigest()
            require(observed == expected, 'Installed library hash differs: ' + name)
            context['libraries'][name] = dict(path=str(path), sha256=observed)
        context['code'] = {str(p.relative_to(SOURCE_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                           (Path(__file__).resolve(), Path(harness.__file__).resolve(), HERE / 'gate_support/step_import_observation.py', HERE / 'verify-step-export-calibration.py',
                            HERE / 'gate_support/step_fixture_checks.py', SOURCE_ROOT / 'src/swcli/hosts/windows_step_export.py')}
        context['source_snapshot'] = str(SOURCE_ROOT)
        context['python'] = sys.version
        context['pywin32'] = '312'
        context['nohost_before'] = native_pids()
        require(not context['nohost_before'], 'Pre-existing SOLIDWORKS processes; no attachment/termination')
        write_json(output / 'preflight.json', context)

        resolved_constants = {}
        def constants(pythoncom, path):
            library = pythoncom.LoadTypeLib(str(path.with_name('sldworks.tlb')))
            info = library.GetTypeInfoOfGuid(STEP_IID)  # One expected official IID, never an IID scan.
            require(info.GetDocumentation(-1)[0] == 'IImportStepData' and str(info.GetTypeAttr()[0]).upper() == STEP_IID,
                    'Installed STEP interface name/IID differs')
            found = _read_native_enum_constants(path, {'swUserPreferenceToggle_e': set(TOGGLES), 'swUserPreferenceIntegerValue_e': set(INTEGERS),
                'swGeneralImportFreePointCurveEntityOptions_e': {'swGeneralImportAs3dCurves', 'swGeneralImportAsSketches'},
                'swImportNeutralCurvesAndPointsOptions_e': {'swImportNeutralCurvesAndPointsOptions_AsSketches', 'swImportNeutralCurvesAndPointsOptions_As3DCurves'}})
            resolved_constants.update(found)
            return {**found, 'step_interface': dict(name='IImportStepData', iid=STEP_IID, wrapper='IUnknown')}
        harness.read_constants = constants

        def acquire(client, *, visible):
            import pythoncom
            require(not visible and not native_pids(), 'Host appeared before activation')
            try:
                client.GetActiveObject('SldWorks.Application')
            except pythoncom.com_error as exc:
                if exc.hresult & 0xFFFFFFFF not in (0x800401E3, 0x80040154):
                    raise  # Unknown ROT errors are not absence.
                absence = exc
            else:
                raise RuntimeError('Existing COM host; do not attach')
            class CheckedClient:
                def GetActiveObject(self, name):
                    raise absence  # Reuse the one checked ROT result, not another COM request.
                def DispatchEx(self, name):
                    app = client.DispatchEx(name)
                    acquisition['created'] = app
                    return app
            try:
                app, owned = original_acquire(CheckedClient(), visible=False)
            except BaseException as first:
                context['partial_acquisition_first_failure'] = error(first)
                write_json(output / 'partial-acquire-first-failure.json', context['partial_acquisition_first_failure'])
                # Clean a known newly created object before the harness calls
                # CoUninitialize. Never replace the activation/configuration error.
                app, handle = acquisition['created'], None
                def cleanup_call(label, function):
                    with (output / 'partial-acquisition-trace.jsonl').open('a', encoding='utf-8', buffering=1) as stream:
                        stream.write(json.dumps(dict(call=label, phase='begin', time=time.time())) + '\n')
                        try:
                            value = function()
                            stream.write(json.dumps(dict(call=label, phase='end', time=time.time())) + '\n')
                            return value
                        except Exception as exc:
                            partial_errors.append(dict(stage=label, **error(exc)))
                            stream.write(json.dumps(dict(call=label, phase='error', time=time.time())) + '\n')
                if app is not None:
                    def capture():
                        pid = harness._com_value(app, 'GetProcessID')
                        context['partial_owned_pid'] = pid
                        write_json(output / 'partial-owned-host.json', dict(process_id=pid, owned_by_probe=True))
                        return harness.capture_process(pid)
                    handle = cleanup_call('partial-acquire.capture-owned-process', capture)
                    cleanup_call('partial-acquire.ExitApp', lambda: harness._com_value(app, 'ExitApp'))
                    if handle is not None:
                        cleanup_call('partial-acquire.WaitForOwnedProcess', lambda: harness.wait_process(handle))
                        cleanup_call('partial-acquire.CloseProcessHandle', handle.Close)
                raise
            acquisition['returned'] = True
            return ImportOnceApp(app, resolved_constants, neutral_3d_candidate=neutral_3d_candidate), owned
        harness.acquire_resident_app = acquire
        result = harness.run(output, args.swconst, False, case_runner=case_runner,
                             case_plan=[('single-wire-import', 'front', False)], diagnostic_case=diagnostic_case)
    except BaseException as exc:
        write_json(output / 'report.json', dict(success=False, diagnostic_case=diagnostic_case, full_acceptance_eligible=False,
                   cases=[], cleanup_errors=[], failure=dict(**error(exc), traceback=traceback.format_exc())))
        result = 1
    finally:
        harness.acquire_resident_app = original_acquire
        harness._com_value = original_com_value
        reader._com_value = original_reader_value
    report = json.loads((output / 'report.json').read_text(encoding='utf-8'))
    report['cleanup_errors'].extend(partial_errors)
    # Read-only postflight checks are evidence/cleanup, never more CAD work.
    if 'input' in context:
        try:
            context['input_final'] = input_metadata()
            require(context['input_final'] == context['input'], 'Input changed across diagnostic/cleanup')
        except Exception as exc:
            report['cleanup_errors'].append(dict(stage='input-postflight', **error(exc)))
    if acquisition['created'] is not None:
        try:
            context['remaining_native_pids'] = native_pids()
            require(not context['remaining_native_pids'], 'Native processes remain; no global termination')
        except Exception as exc:
            report['cleanup_errors'].append(dict(stage='host-postflight', **error(exc)))
    if report['cleanup_errors']:
        report['success'] = False
        result = 1
    report.update(context)
    write_json(output / 'report.json', report)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--swconst', type=Path, default=Path(r'C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\swconst.tlb'))
    parser.add_argument('--neutral-3d-candidate', action='store_true',
                        help='Review-only single import: retain NeutralFree=true; change only Neutral curve enum to official As3DCurves')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.output_dir = args.output_dir.resolve()
    evidence_root = NEUTRAL_3D_EVIDENCE_ROOT if args.neutral_3d_candidate else EVIDENCE_ROOT
    require(ntpath.normcase(str(args.output_dir.parent)) == ntpath.normcase(evidence_root), 'Evidence must be a new direct child of the fixed Workspace evidence root')
    plain(args.output_dir)
    if args.worker:
        return worker(args)
    args.output_dir.mkdir()  # Root prepares parent; never reuse a prior report.
    started = time.monotonic()
    with (args.output_dir / 'worker.stdout.log').open('wb') as stdout, (args.output_dir / 'worker.stderr.log').open('wb') as stderr:
        command = [sys.executable, '-I', __file__, '--worker', '--output-dir', str(args.output_dir), '--swconst', str(args.swconst)]
        if args.neutral_3d_candidate:
            command.append('--neutral-3d-candidate')
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        while process.poll() is None:
            time.sleep(0.25)
            active = None
            for filename in ('trace.jsonl', 'observation-trace.jsonl', 'partial-acquisition-trace.jsonl'):
                trace = args.output_dir / filename
                latest = None
                if trace.exists():
                    for line in trace.read_text(encoding='utf-8').splitlines():
                        try:
                            latest = json.loads(line)
                        except ValueError:
                            continue
                if latest and latest.get('phase') == 'begin' and (active is None or latest['time'] < active['time']):
                    active = latest
            if time.monotonic() - started >= 1800 or active and time.time() - active['time'] >= 600:
                write_json(args.output_dir / 'timeout.json', dict(success=False, active=active, reason='native-600s-or-group-1800s', owned_exit='unknown; root cleanup required'))
                process.kill()  # No process-name/global CAD termination or host restart.
                process.wait()
                return 124
    return process.returncode


if __name__ == '__main__':
    raise SystemExit(main())
