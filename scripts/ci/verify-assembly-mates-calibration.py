"""Owned native calibration only; never public acceptance or a COM client bypass.

Four generated fixtures, one new host, first failure stops. Production writes
remain closed; only this owned-fixture script calls the private calibration
parameter. The external supervisor enforces 600/1800 second budgets.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

from swcli.daemon.documents import DocumentRegistry
from swcli.daemon.operations import execute_operation
from swcli.hosts.windows import _com_value
from swcli.hosts.windows_assemblies import create_assembly_windows_with_handle, add_part_component_windows
from swcli.hosts.windows_assembly_mates import read_mate_targets_windows, add_mate_windows, KINDS, ALIGNMENTS
from swcli.hosts.windows_documents import open_windows_document_with_handle
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.hosts.windows_sketches import create_circle_sketch_windows_with_handle
from swcli.hosts.windows_features import extrude_sketch_windows_with_handle
from swcli.hosts.windows_measurements import measure_part_windows
from swcli.result_schemas import validate_operation_result

spec = importlib.util.spec_from_file_location('_mates_owned_harness', Path(__file__).with_name('verify-through-all-calibration.py'))
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
checked = harness.checked

EXPECTED_ENUMS = dict(swMateCOINCIDENT=0, swMateCONCENTRIC=1, swMateAlignALIGNED=0,
    swMateAlignANTI_ALIGNED=1, swSolidBody=0, swComponentFullyResolved=2,
    swComponentResolved=3, swThisConfiguration=1)
REQUIRED_MEMBERS = {
    'IAssemblyDoc': {'CreateMateData', 'CreateMate', 'GetComponents', 'GetComponentCount', 'GetEditTarget', 'GetEditTargetComponent'},
    'IComponent2': {'GetID', 'GetCorresponding', 'ReferencedConfiguration', 'IsFixed', 'GetSuppression2', 'Transform2'},
    'IEntity': {'GetComponent'},
    'ICoincidentMateFeatureData': {'EntitiesToMate', 'MateAlignment'},
    'IConcentricMateFeatureData': {'EntitiesToMate', 'MateAlignment', 'LockRotation'},
    'IMate2': {'Type', 'Alignment', 'GetMateEntityCount', 'MateEntity'},
    'IMateEntity2': {'Reference', 'ReferenceComponent'},
    'IFeature': {'IsSuppressed2', 'GetErrorCode2', 'GetSpecificFeature2', 'GetDefinition'},
}


def read_official_types(pythoncom, swconst):
    library = pythoncom.LoadTypeLib(str(swconst))
    found = {}
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attributes = info.GetTypeAttr()
        if attributes.typekind == pythoncom.TKIND_ENUM:
            for offset in range(attributes.cVars):
                desc = info.GetVarDesc(offset)
                name = info.GetDocumentation(desc[0])[0]
                if name in EXPECTED_ENUMS:
                    checked(name not in found, 'duplicate required enum')
                    found[name] = desc.value
    checked(found == EXPECTED_ENUMS, 'installed official enums differ: ' + repr(found))
    path = swconst.with_name('sldworks.tlb')
    checked(path.is_file(), 'official sldworks.tlb is required')
    library = pythoncom.LoadTypeLib(str(path))
    members = {}
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        name = info.GetDocumentation(-1)[0]
        if name not in REQUIRED_MEMBERS:
            continue
        attributes = info.GetTypeAttr()
        functions = {info.GetDocumentation(info.GetFuncDesc(i)[0])[0] for i in range(attributes.cFuncs)}
        checked(REQUIRED_MEMBERS[name] <= functions, 'official member contract missing: ' + name + ' ' + str(REQUIRED_MEMBERS[name] - functions))
        members[name] = sorted(REQUIRED_MEMBERS[name])
    checked(set(members) == set(REQUIRED_MEMBERS), 'official type library lacks required interfaces: ' + str(set(REQUIRED_MEMBERS) - set(members)))
    return dict(enums=found, members=members, swconst_sha256=hashlib.sha256(swconst.read_bytes()).hexdigest(),
                sldworks_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def persistent_shape(snapshot):
    """Compare actual reopened content, not session stamps or reference bytes.

    References are re-resolved against exact faces in the fresh document; each
    reopened mate must still reference the same component and face geometry.
    """
    result = copy.deepcopy(snapshot)
    for key in ('title', 'path', 'update_stamp', 'modified'):
        result.pop(key)
    references = {}
    for component in result['components']:
        component.pop('source_update_stamp')
        component.pop('native_id', None)
        geometry_keys = set()
        for face in component['faces']:
            reference = face.pop('reference_sha256')
            face.pop('index')
            key = json.dumps(face, sort_keys=True, allow_nan=False)
            checked(key not in geometry_keys, 'reopen proof has ambiguous equal face geometry')
            geometry_keys.add(key)
            references[reference] = [component['name'], copy.deepcopy(face)]
        component['faces'].sort(key=lambda face: json.dumps(face, sort_keys=True))
    for mate in result['mates']:
        mate['references'] = [references[ref] for ref in mate['references']]
    return result


def equivalent(actual, expected):
    if type(actual) in (int, float) and type(expected) in (int, float):
        return math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10)
    if type(actual) is not type(expected): return False
    if isinstance(actual, dict):
        return set(actual) == set(expected) and all(equivalent(actual[k], expected[k]) for k in actual)
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(equivalent(a,b) for a,b in zip(actual,expected))
    return actual == expected


def calibrate_case(app, output, constants, plane, reverse, call, case, report, live, *, profile_kind):
    kind, alignment = profile_kind, plane
    prefix = kind + '-' + alignment
    case.update(kind=kind, alignment=alignment, success=False, public_acceptance_eligible=False)
    report['public_write_acceptance'] = 'not-run-production-write-fail-closed'
    report['scope'] = 'owned-native-calibration'
    made, source = call(prefix + '.create-part', lambda: create_part_windows_with_handle(app=app))
    live['document'] = source
    case['part_creation'] = made
    checked(made['ok'] and source is not None, 'part fixture creation failed')
    circle, sketch = call(prefix + '.circle', lambda: create_circle_sketch_windows_with_handle(
        app=app, document=source, plane='front', radius_mm=3))
    checked(circle['ok'] and sketch is not None and not circle.get('warnings'), 'circle fixture failed')
    boss, feature = call(prefix + '.boss', lambda: extrude_sketch_windows_with_handle(
        app=app, document=source, sketch_feature=sketch, depth_mm=10))
    checked(boss['ok'] and feature is not None and not boss.get('warnings'), 'cylinder fixture failed')
    metrics = call(prefix + '.measure-source', lambda: measure_part_windows(document=source))
    case['source_metrics'] = metrics
    checked(metrics['ok'] and metrics['metrics']['solid_body_count'] == 1, 'source metrics unavailable')
    checked(math.isclose(metrics['metrics']['volume_mm3'], math.pi * 3**2 * 10, rel_tol=1e-7, abs_tol=1e-5), 'source volume differs')
    part_path = output / (prefix + '.SLDPRT')
    case['part_save'] = call(prefix + '.save-part', lambda: save_as_native_windows(str(part_path), document=source))
    checked(case['part_save']['ok'], 'strict source part save failed')
    part_hash = hashlib.sha256(part_path.read_bytes()).hexdigest()
    cfg = _com_value(_com_value(source, 'GetActiveConfiguration'), 'Name')
    made, document = call(prefix + '.create-assembly', lambda: create_assembly_windows_with_handle(app=app))
    live['document'] = document
    case['assembly_creation'] = made
    checked(made['ok'] and document is not None, 'assembly fixture creation failed')
    insertions=[]
    for index in range(2):
        insertion = call(prefix + '.insert-' + str(index), lambda index=index: add_part_component_windows(
            app=app, document=document, path=str(part_path), configuration=cfg,
            x_mm=index*30, y_mm=index*10, z_mm=index*20))
        insertions.append(insertion)
        checked(insertion['ok'], 'component fixture insertion failed: ' + str(insertion))
    case['insertions'] = insertions
    names=[i['component']['name'] for i in insertions]
    read = call(prefix + '.observe-targets', lambda: read_mate_targets_windows(app=app, document=document, components=names))
    case['targets'] = read
    checked(read['ok'], 'target observation failed: ' + str(read))
    validate_operation_result('assembly.mate-targets',read)
    expected=read['snapshot']
    wanted = 'plane' if kind == 'coincident' else 'cylinder'
    targets=[]
    for component in expected['components']:
        candidates=[f for f in component['faces'] if f['surface_kind'] == wanted]
        if wanted == 'plane':
            candidates=[f for f in candidates if math.isclose(abs(f['parameters'][2]),1,abs_tol=1e-12) and math.isclose(f['parameters'][5],0,abs_tol=1e-12)]
        checked(len(candidates)==1, 'fixture does not have exactly one requested analytic face')
        targets.append(dict(component=component['name'],face_index=candidates[0]['index']))
    parameters=dict(kind=kind,alignment=alignment,targets=targets,expected_value=expected)
    # Exercise the public daemon dispatcher protection, without manufacturing a
    # public success from this internal permission. No public request flag exists.
    registry=DocumentRegistry(app);entry=registry.register(document)
    lease=registry.acquire_lease(entry,session_id='mate-calibration',ttl_seconds=600)
    refused=call(prefix + '.public-write-fail-closed', lambda: execute_operation(app,'assembly.add-mate',parameters,
        documents=registry,document_id=entry.document_id,session_id='mate-calibration',
        expected_update_stamp=expected['update_stamp'],lease_id=lease['lease_id']))
    case['public_write_refusal']=refused
    checked(not refused['ok'] and refused['error']['type']=='MateWriteNotCalibrated'
            and not refused['mutation']['attempted'], 'uncalibrated public write was not closed')
    checked(read_mate_targets_windows(app=app,document=document,components=names)['snapshot']==expected,
            'public refusal changed target state')
    result=call(prefix + '.create-standard-mate', lambda: add_mate_windows(app=app,document=document,
        **parameters,_calibration=True))
    case['creation']=result
    validate_operation_result('assembly.add-mate',result)
    checked(result['ok'] and result['mutation']['creation_returned'], 'native mate creation/solve failed: ' + str(result))
    path=output/(prefix+'.SLDASM')
    case['assembly_save']=call(prefix+'.save-assembly',lambda: save_as_native_windows(str(path),document=document))
    checked(case['assembly_save']['ok'], 'strict assembly save failed')
    saved=call(prefix+'.observe-saved',lambda:read_mate_targets_windows(app=app,document=document,components=names))
    case['saved_targets']=saved
    checked(saved['ok'] and not saved['snapshot']['modified'],'saved mate state is not clean')
    expected_content=persistent_shape(saved['snapshot'])
    case['saved_content']=expected_content
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    title=_com_value(document,'GetTitle');source_title=_com_value(source,'GetTitle')
    # Drop every retained document/feature binding before reopening; the source
    # must be loaded from disk through the assembly references.
    document=source=feature=sketch=registry=entry=None
    live['document']=None
    call(prefix+'.close-assembly',lambda:app.CloseDoc(title))
    loaded=app.GetOpenDocumentByName(str(part_path))
    if loaded is not None:
        loaded=None
        call(prefix+'.close-source',lambda:app.CloseDoc(source_title))
    checked(_com_value(app,'GetDocumentCount')==0,'documents remain before independent reopen')
    reopened,document=call(prefix+'.reopen-readonly',lambda:open_windows_document_with_handle(str(path),app=app,read_only=True))
    live['document']=document
    case['reopen']=reopened
    checked(reopened['ok'] and document is not None and reopened['api_errors']==0 and reopened['api_warnings'] in (0,2),
            'assembly reopen failed or has unexpected warnings')
    read=call(prefix+'.observe-reopened',lambda:read_mate_targets_windows(app=app,document=document,components=names))
    case['reopened_targets']=read
    checked(read['ok'] and not read['snapshot']['modified'],'reopened native mate observation failed: ' + str(read))
    actual_content=persistent_shape(read['snapshot'])
    case['reopened_content']=actual_content
    checked(equivalent(actual_content,expected_content),'saved/reopened component relations or native mate definitions differ')
    checked(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'read-only reopen changed assembly bytes')
    checked(hashlib.sha256(part_path.read_bytes()).hexdigest()==part_hash,'mate operations changed source bytes')
    case.update(assembly_sha256=digest,part_sha256=part_hash,assembly_size_bytes=path.stat().st_size,
                part_size_bytes=part_path.stat().st_size)
    title=_com_value(document,'GetTitle');document=live['document']=None
    call(prefix+'.close-reopened',lambda:app.CloseDoc(title))
    checked(_com_value(app,'GetDocumentCount')==0,'reopened references remain loaded')
    checked(_com_value(app,'GetProcessID')==report['host']['process_id'],'calibration host changed')
    case['success']=True


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--swconst',type=Path,required=True)
    args=parser.parse_args(argv)
    checked(args.swconst.is_file(),'official swconst.tlb is required')
    args.output_dir.mkdir()
    harness.read_constants=read_official_types
    return harness.run(args.output_dir.resolve(),args.swconst.resolve(),False,
        case_runner=calibrate_case,case_plan=[(kind,alignment,False) for kind in KINDS for alignment in ALIGNMENTS],
        diagnostic_case='assembly-standard-mates-calibration')


if __name__=='__main__':raise SystemExit(main())
