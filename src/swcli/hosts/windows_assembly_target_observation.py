"""Private active-assembly target census, before any public mate API is enabled.

Exactly two saved resolved single-solid parts, one fixed and one floating, with
at most 64 plane/cylinder faces each. Every face needs its own native owner;
reference/identity/body membership never replaces GetComponent. No CAD writes,
activation, fallback, public handles, mate inspection, or mate creation here.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .native_trace import native_call
from .windows import _com_value
from .windows_entity_geometry import _numbers, _direction
from .windows_entity_observation import _geometry
from .windows_entity_references import _reference_bytes
from .windows_feature_inspection import _same

MAX_FACES = 64
RESOLVE_DESCRIPTOR = [101, [], [[12, 1, None], [[26, 3], 2, None]], 4, 1, 4, 0, 880, [9, 0, None], 0]


class AssemblyTargetObservationError(RuntimeError):
    def __init__(self, message, code='AssemblyTargetsUnavailable'):
        self.code = code
        super().__init__(message)


def require(condition, message, code='AssemblyTargetsUnavailable'):
    if not condition:
        raise AssemblyTargetObservationError(message, code)


def value(native, name):
    return native_call('assembly-targets', name, lambda: _com_value(native, name))


def integer(raw, name):
    require(type(raw) is int and raw >= 0, name + ' is not a nonnegative integer')
    return raw


def text(raw, name):
    require(type(raw) is str and bool(raw.strip()), name + ' is unavailable')
    return raw


def sequence(raw, name, limit):
    require(raw is None or isinstance(raw, (tuple, list)), name + ' is not an array')
    result = tuple(raw or ())
    require(len(result) <= limit and all(item is not None for item in result), name + ' is incomplete or exceeds limit')
    return result


def require_active_assembly(app, document, *, stage='assembly-targets'):
    """Read/CAS entry contract: reject background before entity/owner access.

    This is also required before any future CAS re-observation or write setup;
    the function never changes ActiveDoc. Caller stays on its owning worker STA.
    """
    active = value(app, 'ActiveDoc')
    matches = document is not None and native_call(stage, 'Assembly.ActiveDoc-IsSame(target)', lambda: _same(app, active, document))
    require(matches,
            'Target assembly must already be active; activate it explicitly before retrying the request.',
            'AssemblyNotActive')
    require(integer(value(document, 'GetType'), 'document type') == 2, 'target must be an assembly', 'UnsupportedDocumentType')


def configuration(document):
    names = sequence(value(document, 'GetConfigurationNames'), 'configuration names', 1)
    manager = value(document, 'ConfigurationManager')
    require(manager is not None, 'configuration manager is unavailable')
    active_configuration = value(manager, 'ActiveConfiguration')
    require(active_configuration is not None, 'active configuration is unavailable')
    active = text(value(active_configuration, 'Name'), 'active configuration')
    require(len(names) == integer(value(document, 'GetConfigurationCount'), 'configuration count') == 1
            and names == (active,), 'exactly one active configuration required', 'UnsupportedAssemblyTargetScope')
    return active


def transform(component):
    data = _numbers(value(value(component, 'Transform2'), 'ArrayData'), 16, 'component transform')
    require(math.isclose(data[12], 1, abs_tol=1e-12, rel_tol=0), 'scaled components unsupported')
    rows = [data[i:i + 3] for i in (0, 3, 6)]
    for row in rows:
        _direction(row, 'component rotation')
    require(all(abs(sum(a * b for a, b in zip(rows[i], rows[j]))) < 1e-10 for i, j in ((0, 1), (0, 2), (1, 2))),
            'component rotation is not orthogonal')
    determinant = sum(rows[0][i] * (rows[1][(i+1)%3]*rows[2][(i+2)%3] - rows[1][(i+2)%3]*rows[2][(i+1)%3]) for i in range(3))
    require(math.isclose(determinant, 1, abs_tol=1e-10, rel_tol=0), 'mirrored components unsupported')
    return data


def document_state(document):
    state = dict(configuration=configuration(document), update_stamp=integer(value(document, 'GetUpdateStamp'), 'update stamp'),
                 path=text(value(document, 'GetPathName'), 'saved path'), modified=value(document, 'GetSaveFlag'),
                 readonly=value(document, 'IsOpenedReadOnly'), view_only=value(document, 'IsOpenedViewOnly'))
    require(all(type(state[key]) is bool for key in ('modified', 'readonly', 'view_only')), 'document flags are not native booleans')
    return state


def require_clean_readonly(document):
    state = document_state(document)
    require(state['modified'] is False and state['readonly'] is True and state['view_only'] is False,
            'this proof requires clean readonly non-view-only documents', 'UnsupportedAssemblyTargetScope')
    require(value(value(document, 'SketchManager'), 'ActiveSketch') is None, 'finish sketch editing first')
    return state


def _saved_part(path):
    source = Path(path)
    return source.suffix.casefold() == '.sldprt' and source.is_file() and source.stat().st_size > 0


class OfficialInterfaces:
    """Owning installation, official dual interface, retained queried pointer.

    Request-local cache only. Selected from the pinned 2025 native33 binding
    path; no generated factory, guessed IID, alternate installation or ROT.
    """
    def __init__(self, app):
        import pythoncom
        import win32api
        import win32con
        import win32process
        self.app, self.interfaces = app, {}
        pid = integer(value(app, 'GetProcessID'), 'host PID')
        require(pid > 0, 'host PID unavailable')
        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
        try:
            executable = Path(win32process.GetModuleFileNameEx(handle, 0))
        finally:
            handle.Close()
        require(executable.name.casefold() == 'sldworks.exe', 'host image is not SOLIDWORKS')
        path = executable.with_name('sldworks.tlb')
        require(path.is_file(), 'owning official library is unavailable')
        self.library = native_call('assembly-targets', 'LoadTypeLib(owning-installation)', lambda: pythoncom.LoadTypeLib(str(path)))
        attributes = self.library.GetLibAttr()
        require(str(attributes[0]).upper() == '{83A33D31-27C5-11CE-BFD4-00400513BB57}'
                and attributes[3:5] == (33, 0), 'unreviewed official library')

    def info(self, interface):
        import pythoncom
        if interface not in self.interfaces:
            count = integer(self.library.GetTypeInfoCount(), 'type-info count')
            require(count <= 4096, 'official type library count exceeds limit')
            matches = []
            for index in range(count):
                info = self.library.GetTypeInfo(index)
                if info.GetDocumentation(-1)[0] == interface:
                    require(info.GetTypeAttr().typekind == pythoncom.TKIND_DISPATCH, 'official interface is not dual dispatch')
                    matches.append(info)
            require(len(matches) == 1, 'official interface missing or ambiguous: ' + interface)
            self.interfaces[interface] = matches[0]
        return self.interfaces[interface]

    def bind(self, native, interface):
        import pythoncom
        from win32com.client.dynamic import Dispatch
        info = self.info(interface)
        queried = native_call('assembly-targets', 'QueryInterface.' + interface,
                              lambda: native._oleobj_.QueryInterface(info.GetTypeAttr().iid, pythoncom.IID_IDispatch))
        wrapped = native_call('assembly-targets', 'BindOfficialTypeInfo.' + interface, lambda: Dispatch(queried, typeinfo=info))
        require(wrapped._oleobj_ is queried, 'official factory replaced queried pointer')
        require(_same(self.app, native, wrapped), 'official interface changed native identity')
        return wrapped

    def check_resolver(self):
        info = self.info('IModelDocExtension')
        count = integer(info.GetTypeAttr().cFuncs, 'official cFuncs')
        require(count <= 2048, 'official function count exceeds limit')
        matches = []
        for index in range(count):
            desc = info.GetFuncDesc(index)
            if info.GetDocumentation(desc[0])[0] == 'GetObjectByPersistReference3':
                matches.append((desc, info.GetNames(desc[0])))
        require(len(matches) == 1, 'official resolver missing or ambiguous')
        desc, names = matches[0]
        require(json.dumps(tuple(desc)) == json.dumps(RESOLVE_DESCRIPTOR)
                and tuple(names) == ('GetObjectByPersistReference3', 'PersistId', 'ErrorCode'),
                'typed resolver differs from the reviewed installed 2025 descriptor')


def _resolve(extension, reference, *, stage='assembly-targets'):
    import pythoncom
    from win32com.client import VARIANT
    encoded = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, reference)
    result = native_call(stage, 'IModelDocExtension.GetObjectByPersistReference3',
                         lambda: extension.GetObjectByPersistReference3(encoded, 2147483647))
    require(type(result) is tuple and len(result) == 2, 'typed reference result is not a two-item tuple')
    entity, status = result
    require(type(status) is int and status == 0 and entity is not None, 'typed reference status is not written OK or entity is absent')
    return entity


@dataclass(frozen=True)
class AssemblyFaceBinding:
    """Private only: neither a public token nor a serializable persistent handle."""
    component: Any
    source: Any
    original_mapped: Any
    resolved: Any
    body: Any
    reference: bytes


@dataclass(frozen=True)
class AssemblyTargetCensus:
    value: dict
    bindings: tuple


def _component_inputs(app, component, name, max_faces):
    require(value(component, 'Name2') == name, 'component name changed')
    require(value(component, 'IsVirtual') is False, 'virtual components unsupported')
    suppression = integer(value(component, 'GetSuppression2'), 'suppression')
    require(suppression in (2, 3), 'component must be resolved')
    fixed = value(component, 'IsFixed')
    require(type(fixed) is bool, 'fixed flag is not a native boolean')
    source = value(component, 'GetModelDoc2')
    require(source is not None and integer(value(source, 'GetType'), 'source type') == 1, 'loaded part required')
    state = require_clean_readonly(source)
    require(text(value(component, 'ReferencedConfiguration'), 'referenced configuration') == state['configuration'], 'component configuration differs')
    path = text(value(component, 'GetPathName'), 'component path')
    require(_saved_part(path) and path.casefold() == state['path'].casefold(), 'saved external component/source path differs')
    bodies = sequence(source.GetBodies2(0, False), 'source solid bodies', 1)
    require(len(bodies) == 1 and not sequence(source.GetBodies2(1, False), 'source surface bodies', 1), 'one solid and no surface bodies required')
    faces = sequence(value(bodies[0], 'GetFaces'), 'source faces', max_faces)
    require(0 < len(faces) == integer(value(bodies[0], 'GetFaceCount'), 'source face count'), 'source face census incomplete')
    require(all(_same(app, value(face, 'GetBody'), bodies[0]) for face in faces), 'source face/body membership differs')
    import pythoncom
    from win32com.client import VARIANT
    info = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)
    raw_bodies = native_call('assembly-targets', 'Component2.GetBodies3', lambda: component.GetBodies3(0, info))
    component_bodies = sequence(raw_bodies, 'component bodies', 1)
    body_info = sequence(info.value, 'component body info', 1)
    require(len(component_bodies) == len(body_info) == 1 and type(body_info[0]) is int and body_info[0] == 1,
            'complete normal component solid required')
    body = component_bodies[0]
    body_faces = sequence(value(body, 'GetFaces'), 'component faces', max_faces)
    require(len(faces) == len(body_faces) == integer(value(body, 'GetFaceCount'), 'component face count'), 'component face census incomplete')
    require(all(_same(app, value(face, 'GetBody'), body) for face in body_faces), 'component face/body membership differs')
    pose = transform(component)
    return dict(native=component, source=source, state=state, name=name, path=path, transform=pose, fixed=fixed, suppression=suppression,
                source_faces=faces, body=body, body_faces=body_faces)


def observe_readonly_active_targets(*, app, document, components, max_faces=MAX_FACES):
    """All faces of both planned components or an exception; no partial bindings.

    This private Phase A entry deliberately supports clean readonly saved ASM
    only. Public writable snapshots/typed handles/CAS are later independent gates.
    """
    require_active_assembly(app, document)  # Before owner, references, binding or any write setup.
    require(type(max_faces) is int and 1 <= max_faces <= MAX_FACES, 'invalid face limit')
    require(isinstance(components, (tuple, list)) and len(components) == 2
            and all(type(name) is str and name.strip() for name in components) and len(set(components)) == 2,
            'two distinct planned component names required')
    require(value(app, 'RevisionNumber') == '33.5.0', 'unreviewed native revision')
    state = require_clean_readonly(document)
    require(_same(app, value(document, 'GetEditTarget'), document), 'in-context edit target unsupported')
    edit_component = value(document, 'GetEditTargetComponent')
    require(edit_component is None or value(edit_component, 'IsRoot') is True, 'finish component editing first')
    natives = sequence(document.GetComponents(True), 'assembly components', 2)
    require(len(natives) == integer(document.GetComponentCount(True), 'component count') == 2, 'complete two-component assembly required')
    ordered = []
    for name in components:
        matches = [component for component in natives if value(component, 'Name2') == name]
        require(len(matches) == 1, 'component is absent or ambiguous')
        ordered.append(matches[0])
    require(not _same(app, *ordered), 'component instances alias')
    require(value(ordered[0], 'IsFixed') is True and value(ordered[1], 'IsFixed') is False, 'first fixed/second floating scope required')
    inputs = [_component_inputs(app, native, name, max_faces) for name, native in zip(components, ordered)]
    require(inputs[0]['fixed'] is True and inputs[1]['fixed'] is False, 'fixed/floating scope changed before census')
    interfaces = OfficialInterfaces(app)
    extension = interfaces.bind(value(document, 'Extension'), 'IModelDocExtension')
    interfaces.check_resolver()
    rows, bindings, reference_hashes = [], [], set()
    for component_index, item in enumerate(inputs):
        faces, seen = [], []
        for index, source_face in enumerate(item['source_faces']):
            stage = 'assembly-targets.component[%d].face[%d]' % (component_index, index)
            require_active_assembly(app, document, stage=stage)
            mapped = native_call(stage, 'Component2.GetCorresponding(source-face)', lambda: item['native'].GetCorresponding(source_face))
            require(mapped is not None, 'source mapping returned null')
            matches = [face for face in item['body_faces'] if _same(app, mapped, face)]
            require(len(matches) == 1 and not any(_same(app, mapped, old) for old in seen), 'mapped face identity is absent, repeated or ambiguous')
            mapped_face = interfaces.bind(mapped, 'IFace2')
            require(_same(app, value(mapped_face, 'GetBody'), item['body']), 'mapped face body differs')
            geometry = _geometry(source_face)
            require(geometry['surface_kind'] in ('plane', 'cylinder'), 'unsupported face in complete census', 'UnsupportedAssemblyTargetScope')
            require(_geometry(mapped_face) == geometry, 'mapped face geometry differs')
            raw = native_call(stage, 'IModelDocExtension.GetPersistReference3', lambda: extension.GetPersistReference3(mapped))
            reference = _reference_bytes(raw)
            resolved = _resolve(extension, reference, stage=stage)
            require(_same(app, mapped, resolved), 'reference roundtrip changed native identity')
            resolved_face = interfaces.bind(resolved, 'IFace2')
            require(_same(app, value(resolved_face, 'GetBody'), item['body']) and _geometry(resolved_face) == geometry, 'resolved face body/geometry differs')
            entity = interfaces.bind(resolved, 'IEntity')
            require_active_assembly(app, document, stage=stage)
            owner = native_call(stage, 'IEntity(reference-resolved).GetComponent', lambda: value(entity, 'GetComponent'))
            require(owner is not None, 'resolved face has no component in the active assembly')
            require(native_call(stage, 'Resolved.owner-IsSame(target-component)', lambda: _same(app, owner, item['native'])),
                    'resolved face owner differs from exact planned component')
            reference_hash = hashlib.sha256(reference).hexdigest()
            require(reference_hash not in reference_hashes, 'ambiguous face references across complete target census')
            reference_hashes.add(reference_hash)
            faces.append(dict(index=index, geometry=geometry, reference_sha256=reference_hash, exact_native_owner=True))
            seen.append(mapped)
            bindings.append(AssemblyFaceBinding(item['native'], source_face, mapped, resolved, item['body'], reference))
        rows.append(dict(name=item['name'], path=item['path'], source_state=item['state'], transform=item['transform'],
                         fixed=item['fixed'], suppression=item['suppression'], source_face_count=len(item['source_faces']),
                         component_face_count=len(item['body_faces']), faces=faces))
    # Success-only postconditions. An owner error never starts another face/read.
    require_active_assembly(app, document)
    for item in inputs:
        require(document_state(item['source']) == item['state']
                and value(value(item['source'], 'SketchManager'), 'ActiveSketch') is None, 'source state changed during census')
        require(value(item['native'], 'Name2') == item['name'] and value(item['native'], 'GetPathName') == item['path']
                and value(item['native'], 'ReferencedConfiguration') == item['state']['configuration']
                and _same(app, value(item['native'], 'GetModelDoc2'), item['source']), 'component source context changed')
        require(transform(item['native']) == item['transform'], 'component transform changed during census')
        require(value(item['native'], 'IsFixed') is item['fixed']
                and integer(value(item['native'], 'GetSuppression2'), 'post suppression') == item['suppression']
                and value(item['native'], 'IsVirtual') is False, 'component fixed/suppression scope changed')
    require(document_state(document) == state, 'assembly state changed during census')
    require(_same(app, value(document, 'GetEditTarget'), document)
            and value(value(document, 'SketchManager'), 'ActiveSketch') is None, 'assembly edit state changed')
    after_edit_component = value(document, 'GetEditTargetComponent')
    require(_same(app, edit_component, after_edit_component), 'component edit context changed')
    require_active_assembly(app, document)
    return AssemblyTargetCensus(dict(scope='private readonly active-assembly complete target census', assembly=state, components=rows,
                                    face_count=len(bindings), all_faces_observed=True, public_handles_issued=False,
                                    write_CAS_executed=False, public_acceptance=False), tuple(bindings))
