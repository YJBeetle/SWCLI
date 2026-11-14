"""Public readonly gate around the unchanged native37 complete census."""
from copy import deepcopy

from ..assembly_target_contracts import canonical, census_value
from ..hosts import windows_assembly_target_observation as native
from ..hosts.native_trace import native_call
from .assembly_targets import AssemblyTargetStale

OPERATIONS = frozenset(('assembly.targets.list', 'assembly.targets.validate'))


def _require(condition, message):
    if not condition:
        raise AssemblyTargetStale(message)


def current_context(registry, value, bindings, expected_sources=None):
    """Observe cheap full scope before owner traversal and after registry checks.

    Kept separate from the native37 observer: no relaxation of its readonly
    policy, no owner getters, no reference/geometry shortcut for a fresh census.
    """
    registry.live()
    app, document = registry.app, registry.document
    native.require_active_assembly(app, document)
    _require(canonical(native.document_state(document)) == canonical(value['assembly']), 'assembly configuration/stamp/path/state changed')
    _require(registry.same(native.value(document, 'GetEditTarget'), document), 'assembly edit target changed')
    edit = native.value(document, 'GetEditTargetComponent')
    _require(edit is None or native.value(edit, 'IsRoot') is True, 'component editing in progress')
    _require(native.value(native.value(document, 'SketchManager'), 'ActiveSketch') is None, 'assembly sketch editing in progress')
    components = native.sequence(native_call('assembly-target-scope', 'Assembly.GetComponents',
        lambda: document.GetComponents(True)), 'assembly components', 2)
    _require(len(components) == native.integer(native_call('assembly-target-scope', 'Assembly.GetComponentCount',
        lambda: document.GetComponentCount(True)), 'component count') == 2, 'component set changed')
    sources, offset = [], 0
    for index, row in enumerate(value['components']):
        planned = bindings[offset].component
        matches = [component for component in components if registry.same(planned, component)]
        _require(len(matches) == 1, 'exact native component instance changed')
        component = matches[0]
        source = native.value(component, 'GetModelDoc2')
        _require(source is not None, 'source document unavailable')
        if expected_sources is not None:
            _require(registry.same(expected_sources[index], source), 'source document native identity changed')
        _require(canonical(native.document_state(source)) == canonical(row['source_state']), 'source configuration/stamp/path/state changed')
        _require(native.value(native.value(source, 'SketchManager'), 'ActiveSketch') is None, 'source sketch editing in progress')
        observed = dict(name=native.value(component, 'Name2'), path=native.value(component, 'GetPathName'),
                        configuration=native.value(component, 'ReferencedConfiguration'),
                        transform=native.transform(component), fixed=native.value(component, 'IsFixed'),
                        suppression=native.value(component, 'GetSuppression2'), virtual=native.value(component, 'IsVirtual'))
        expected = dict(name=row['name'], path=row['path'], configuration=row['source_state']['configuration'],
                        transform=row['transform'], fixed=row['fixed'], suppression=row['suppression'], virtual=False)
        _require(canonical(observed) == canonical(expected), 'component source/pose/fixed/suppression scope changed')
        _require(registry.same(source, native.value(component, 'GetModelDoc2')), 'source document changed during context read')
        sources.append(source)
        offset += len(row['faces'])
    native.require_active_assembly(app, document)
    return tuple(sources)


def prepare_request(app, operation, parameters, *, documents, session_id,
                    document_id, expected_update_stamp, lease_id):
    """Worker pre-sequence checks: protocol/lease/kind/scope/active, no owners."""
    from ..operation_schemas import validate_operation_request
    from .operations import DocumentUpdateConflict, DocumentUpdateStampUnavailable

    values = validate_operation_request(operation, parameters, document_id=document_id,
        expected_update_stamp=expected_update_stamp, lease_id=lease_id)
    if documents is None:
        raise RuntimeError('document registry is unavailable')
    entry = documents.resolve(document_id, session_id=session_id)
    registry = entry.assembly_targets
    registry.live()
    documents.require_lease(entry, session_id=session_id, lease_id=lease_id)
    old = None
    if operation.endswith('.validate'):
        old = registry.lookup(session_id, values['snapshot_id'], values['target_ids'])
    else:
        registry.capacity(session_id)
    try:
        _require(registry.same(entry.document, registry.document), 'registered assembly native identity changed')
        native.require_active_assembly(app, entry.document)
        stamp = native.value(entry.document, 'GetUpdateStamp')
        if type(stamp) is not int or stamp < 0:
            raise DocumentUpdateStampUnavailable('assembly update stamp is not a native integer')
        if stamp != expected_update_stamp:
            raise DocumentUpdateConflict('assembly update stamp differs from expected_update_stamp')
        if old is not None:
            current_context(registry, old.value, old.bindings, old.source_documents)
    except Exception:
        registry.invalidate_after_failure()
        raise
    return entry, registry, old


def planned_sources(registry, names):
    """Retain exact component/source identities across the first complete pass."""
    native.require_active_assembly(registry.app, registry.document)
    components = native.sequence(native_call('assembly-target-plan', 'Assembly.GetComponents',
        lambda: registry.document.GetComponents(True)), 'assembly components', 2)
    _require(len(components) == 2, 'complete two-component plan required')
    planned = []
    for name in names:
        matches = [c for c in components if native.value(c, 'Name2') == name]
        _require(len(matches) == 1, 'component plan is absent or ambiguous')
        source = native.value(matches[0], 'GetModelDoc2')
        _require(source is not None, 'planned source document unavailable')
        planned.append((matches[0], source))
    return tuple(planned)


def run(context, values):
    from ..result_schemas import validate_operation_result
    from .operations import _with_document

    entry, registry, old = prepare_request(context.app, context.operation, values,
        documents=context.documents, session_id=context.session_id, document_id=context.document_id,
        expected_update_stamp=context.expected_update_stamp, lease_id=context.lease_id)
    try:
        names = values['components'] if old is None else [c['name'] for c in old.value['components']]
        plan = planned_sources(registry, names) if old is None else None
        # One explicitly planned full pass; a failure never triggers another pass.
        census = native.observe_readonly_active_targets(app=context.app, document=entry.document, components=names)
        value = census_value(census.value)
        if plan is not None:
            offset = 0
            for row, (component, _) in zip(value['components'], plan):
                _require(registry.same(component, census.bindings[offset].component), 'planned component native identity changed during census')
                offset += len(row['faces'])
        expected_sources = tuple(source for _, source in plan) if plan is not None else old.source_documents
        sources = current_context(registry, value, census.bindings, expected_sources)
        result = dict(ok=True, action=context.operation, scope='active-assembly-readonly-targets-v1',
                      census=deepcopy(value), read_gate=dict(scope='complete-readonly-target-census',
                          mate_tree_compared=False, write_authorized=False))
        staged = None
        if old is None:
            # A scope/identity change observed by any session permanently retires
            # all previously issued snapshots, even if state later returns.
            for previous in tuple(registry.snapshots.values()):
                try:
                    registry.compare(previous, census, sources)
                except AssemblyTargetStale:
                    registry.invalidate_all()
                    break
            staged = registry.stage(context.session_id, census, sources)
            result.update(snapshot_id=staged.snapshot_id, targets=deepcopy(list(staged.targets)))
        else:
            registry.compare(old, census, sources)
            result.update(snapshot_id=old.snapshot_id, target_ids=list(values['target_ids']), unchanged=True)
        result = _with_document(result, context.documents, entry, session_id=context.session_id)
        validate_operation_result(context.operation, result)
        # No COM/state reads follow this final full cheap scope/active guard.
        current_context(registry, value, census.bindings, sources)
        context.documents.require_lease(entry, session_id=context.session_id, lease_id=context.lease_id)
        if staged is not None:
            registry.publish(context.session_id, staged)
        return result
    except Exception:
        # Preserve the original native/business error, retire old grants, and
        # publish neither partial handles nor silently refreshed replacements.
        registry.invalidate_after_failure()
        raise


def error_code(exc):
    return exc.code if isinstance(exc, native.AssemblyTargetObservationError) else type(exc).__name__
