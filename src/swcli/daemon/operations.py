"""Typed operations executed by the resident COM worker."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..operation_schemas import (
    OPERATIONS,
    OPERATION_SCHEMAS,
    OPERATION_CATALOG,
    validate_operation_request,
)
from ..hosts.windows_documents import (
    open_windows_document_with_handle,
    close_active_windows_document,
    diagnose_active_windows_document,
    export_active_windows_document,
    inspect_active_windows_document,
    rebuild_active_windows_document,
    render_active_windows_document,
    save_active_windows_document,
)
from ..hosts.windows_parts import (
    create_box_part_windows_with_handle,
    create_part_windows_with_handle,
)
from ..hosts.windows_sketches import (
    create_rectangle_sketch_windows_with_handle,
    create_circle_sketch_windows_with_handle,
)
from ..hosts.windows_rectangle_constraints import (
    fix_rectangle_center_windows_with_handle,
)
from ..hosts.windows_rectangle_dimensions import (
    create_rectangle_dimensions_windows_with_handles,
)
from ..hosts.windows_linear_dimensions import (
    inspect_rectangle_dimension_windows,
    set_rectangle_dimension_windows,
)
from ..hosts.windows_features import extrude_sketch_windows_with_handle
from ..hosts.windows_native_files import save_as_part_windows
from ..hosts.windows_measurements import measure_part_windows
from ..hosts.windows_cuts import cut_extrude_sketch_windows_with_handle
from ..hosts.windows_sketch_inspection import inspect_sketch_windows
from ..hosts.windows_dimensions import (
    create_circle_diameter_windows_with_handle,
    inspect_dimension_windows,
    set_dimension_windows,
)
from ..hosts.windows_dimension_discovery import (
    discover_circle_diameter_windows_with_handle,
)
from ..hosts.windows_rectangle_dimension_discovery import (
    discover_rectangle_dimensions_windows_with_handles,
)
from ..result_schemas import (
    OperationResultInvalid,
    validate_dimension_discovery_observation,
    validate_rectangle_creation_observation,
    validate_rectangle_discovery_observation,
    validate_feature_observation,
    validate_entity_observation,
)
from .documents import (
    DEFAULT_SESSION_ID,
    DocumentEntry,
    DocumentRegistry,
)

LEASE_GUARDED_OPERATIONS = frozenset(
    name for name, spec in OPERATION_CATALOG.items() if spec.lease_guarded
)
LEASE_TOKEN_OPERATIONS = frozenset(
    name
    for name, schema in OPERATION_SCHEMAS.items()
    if schema["x-swcli-context"]["lease_id"] != "forbidden"
)
UPDATE_STAMP_OPERATIONS = frozenset(
    name
    for name, schema in OPERATION_SCHEMAS.items()
    if schema["x-swcli-context"]["expected_update_stamp"] != "forbidden"
)


class DocumentUpdateConflict(RuntimeError):
    """The selected document changed after the caller last observed it."""


class DocumentUpdateStampUnavailable(RuntimeError):
    """The selected host cannot provide a native document update stamp."""


class UnsupportedDimensionKind(RuntimeError):
    """The registered native dimension/profile pair has no public adapter."""


def _lease_ttl(parameters: Dict[str, Any]) -> float:
    value = parameters.get("ttl_seconds", 60)
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not 1 <= value <= 3600
    ):
        raise ValueError("ttl_seconds must be between 1 and 3600")
    return float(value)


def _with_document(
    result: Dict[str, Any],
    documents: DocumentRegistry,
    entry: DocumentEntry,
    *,
    session_id: str,
    descriptor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if descriptor is None:
        descriptor = documents.describe(entry, session_id=session_id)
    if isinstance(result.get("document"), dict):
        result["document"].update(
            {
                "document_id": descriptor["document_id"],
                "current": descriptor["current"],
                "active": descriptor["active"],
            }
        )
    else:
        result["document"] = descriptor
    result["session_id"] = session_id
    return result


@dataclass
class OperationContext:
    app: Any
    operation: str
    documents: Optional[DocumentRegistry]
    session_id: str
    document_id: Optional[str]
    lease_id: Optional[str]
    entry: Optional[DocumentEntry] = None


_HANDLERS = {}


def _register_handler(handler):
    if handler.__name__ in _HANDLERS:
        raise RuntimeError(f"duplicate operation handler: {handler.__name__}")
    _HANDLERS[handler.__name__] = handler
    return handler


@_register_handler
def document_create(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    result, created_document = create_part_windows_with_handle(
        app=context.app, template=values.get("template")
    )
    if context.documents is not None and created_document is not None:
        context.entry = context.documents.register(created_document)
        context.documents.set_current(context.entry, session_id=context.session_id)
        return _with_document(
            result, context.documents, context.entry, session_id=context.session_id
        )
    return result


@_register_handler
def document_open(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    result, opened_document = open_windows_document_with_handle(
        str(values["path"]),
        read_only=bool(values.get("read_only", False)),
        configuration=str(values.get("configuration", "")),
        app=context.app,
    )
    if context.documents is not None and result.get("ok"):
        if opened_document is None:
            raise RuntimeError(
                "SOLIDWORKS returned no document after a successful open"
            )
        context.entry = context.documents.register(opened_document)
        context.documents.set_current(context.entry, session_id=context.session_id)
        return _with_document(
            result, context.documents, context.entry, session_id=context.session_id
        )
    return result


@_register_handler
def document_list(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    if context.documents is None:
        raise RuntimeError("document registry is unavailable")
    return context.documents.list(session_id=context.session_id)


@_register_handler
def document_use(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    if context.documents is None:
        raise RuntimeError("document registry is unavailable")
    if context.document_id is None:
        raise ValueError("document.use requires document_id")
    context.entry = context.documents.use(
        context.document_id, session_id=context.session_id
    )
    return {
        "ok": True,
        "action": "document.use",
        "session_id": context.session_id,
        "document": context.documents.describe(
            context.entry, session_id=context.session_id
        ),
    }


@_register_handler
def document_lease_renew(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None:
        raise RuntimeError("document registry is unavailable")
    if context.lease_id is None:
        raise ValueError("document.lease.renew requires lease_id")
    lease = context.documents.renew_lease(
        context.lease_id,
        session_id=context.session_id,
        ttl_seconds=_lease_ttl(values),
    )
    return {
        "ok": True,
        "action": context.operation,
        "session_id": context.session_id,
        "lease": lease,
    }


@_register_handler
def document_lease_release(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None:
        raise RuntimeError("document registry is unavailable")
    if context.lease_id is None:
        raise ValueError("document.lease.release requires lease_id")
    lease = context.documents.release_lease(
        context.lease_id, session_id=context.session_id
    )
    return {
        "ok": True,
        "action": context.operation,
        "session_id": context.session_id,
        "released": True,
        "lease": lease,
    }


@_register_handler
def document_lease_acquire(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    lease = context.documents.acquire_lease(
        context.entry,
        session_id=context.session_id,
        ttl_seconds=_lease_ttl(values),
    )
    return {
        "ok": True,
        "action": context.operation,
        "session_id": context.session_id,
        "lease": lease,
        "document": context.documents.describe(
            context.entry, session_id=context.session_id
        ),
    }


@_register_handler
def document_lease_status(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    lease = context.documents.active_lease(context.entry)
    if lease is not None and lease["session_id"] != context.session_id:
        lease = {key: value for key, value in lease.items() if key != "lease_id"}
    return {
        "ok": True,
        "action": context.operation,
        "session_id": context.session_id,
        "leased": lease is not None,
        "owned_by_session": lease is not None
        and lease["session_id"] == context.session_id,
        "lease": lease,
        "document": context.documents.describe(
            context.entry, session_id=context.session_id
        ),
    }


@_register_handler
def document_inspect(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    result = inspect_active_windows_document(
        detail=str(values.get("detail", "summary")),
        max_features=int(values.get("max_features", 500)),
        app=context.app,
        document=context.entry.document if context.entry is not None else None,
    )
    return (
        _with_document(
            result, context.documents, context.entry, session_id=context.session_id
        )
        if context.documents is not None and context.entry is not None
        else result
    )


@_register_handler
def document_measure(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    result = measure_part_windows(
        document=context.entry.document, max_bodies=values.get("max_bodies", 1000)
    )
    return _with_document(
        result, context.documents, context.entry, session_id=context.session_id
    )


@_register_handler
def document_close(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    descriptor = (
        context.documents.describe(context.entry, session_id=context.session_id)
        if context.documents is not None and context.entry is not None
        else None
    )
    result = close_active_windows_document(
        discard=bool(values.get("discard", False)),
        app=context.app,
        document=context.entry.document if context.entry is not None else None,
    )
    if context.documents is not None and context.entry is not None:
        if result.get("ok") and descriptor is not None:
            descriptor = dict(descriptor)
            descriptor.update({"active": False, "current": False})
        result = _with_document(
            result,
            context.documents,
            context.entry,
            session_id=context.session_id,
            descriptor=descriptor,
        )
        if result.get("ok"):
            context.documents.forget(context.entry.document_id)
    return result


@_register_handler
def document_save(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    result = save_active_windows_document(
        app=context.app,
        document=context.entry.document if context.entry is not None else None,
    )
    return (
        _with_document(
            result, context.documents, context.entry, session_id=context.session_id
        )
        if context.documents is not None and context.entry is not None
        else result
    )


@_register_handler
def document_diagnose(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    result = diagnose_active_windows_document(
        max_features=int(values.get("max_features", 500)),
        app=context.app,
        document=context.entry.document if context.entry is not None else None,
    )
    return (
        _with_document(
            result, context.documents, context.entry, session_id=context.session_id
        )
        if context.documents is not None and context.entry is not None
        else result
    )


@_register_handler
def document_rebuild(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    result = rebuild_active_windows_document(
        force=bool(values.get("force", False)),
        top_only=bool(values.get("top_only", False)),
        max_features=int(values.get("max_features", 500)),
        app=context.app,
        document=context.entry.document if context.entry is not None else None,
    )
    return (
        _with_document(
            result, context.documents, context.entry, session_id=context.session_id
        )
        if context.documents is not None and context.entry is not None
        else result
    )


@_register_handler
def document_render(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    kwargs = {
        "width": int(values.get("width", 1024)),
        "height": int(values.get("height", 768)),
        "view": str(values.get("view", "current")),
        "fit": bool(values.get("fit", True)),
        "overwrite": bool(values.get("overwrite", False)),
        "app": context.app,
        "document": context.entry.document if context.entry is not None else None,
    }
    return render_active_windows_document(str(values["output"]), **kwargs)


@_register_handler
def document_save_as(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    output = str(Path(values["output"]).expanduser().resolve())
    context.documents.require_new_path(context.entry, output)
    try:
        return save_as_part_windows(output, document=context.entry.document)
    finally:
        # COM may have adopted the filename even when a later check failed.
        # Refresh before the next sync so references and leases are not lost.
        context.documents.refresh_key(context.entry)


@_register_handler
def document_export(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    kwargs = {
        "overwrite": bool(values.get("overwrite", False)),
        "strict": bool(values.get("strict", False)),
        "app": context.app,
        "document": context.entry.document if context.entry is not None else None,
    }
    return export_active_windows_document(str(values["output"]), **kwargs)


@_register_handler
def sketch_rectangle(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    result, feature = create_rectangle_sketch_windows_with_handle(
        app=context.app,
        document=context.entry.document,
        plane=values["plane"],
        width_mm=float(values["width_mm"]),
        height_mm=float(values["height_mm"]),
        center_x_mm=float(values.get("center_x_mm", 0.0)),
        center_y_mm=float(values.get("center_y_mm", 0.0)),
    )
    if feature is not None and isinstance(result.get("sketch"), dict):
        result["sketch"]["sketch_id"] = context.documents.register_sketch(
            context.entry, feature
        )
    return result


@_register_handler
def sketch_list(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    from ..hosts.windows_sketch_inspection import list_sketches_windows_with_handles

    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    result, features = list_sketches_windows_with_handles(
        app=context.app,
        document=context.entry.document,
        max_sketches=values.get("max_sketches", 1000),
    )
    if result.get("ok"):
        sketches = result["sketches"]
        if len(sketches) != len(features) or result["count"] != len(sketches):
            raise RuntimeError("native sketch discovery returned inconsistent handles")
        if any(feature is None for feature in features):
            raise RuntimeError("native sketch discovery returned an absent feature")
        for sketch, feature in zip(result["sketches"], features):
            sketch["sketch_id"] = context.documents.register_sketch(
                context.entry, feature
            )
    return _with_document(
        result, context.documents, context.entry, session_id=context.session_id
    )


@_register_handler
def feature_list(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    from ..hosts.windows_feature_inspection import (
        list_extrusion_features_windows_with_handles,
    )

    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    result, features = list_extrusion_features_windows_with_handles(
        app=context.app,
        document=context.entry.document,
        max_features=values.get("max_features", 1000),
    )
    result = _with_document(
        result, context.documents, context.entry, session_id=context.session_id
    )
    validate_feature_observation("feature.list", result)
    if result["ok"]:
        if len(features) != result["count"] or any(
            feature is None for feature in features
        ):
            raise OperationResultInvalid(
                "feature.list: inconsistent exact native handles"
            )
        for descriptor, feature in zip(result["features"], features):
            descriptor["feature_id"] = context.documents.register_feature(
                context.entry, feature
            )
    return result


def _observe_entities(context: OperationContext, kind: str, limit: int = 64):
    from ..hosts.windows_entity_observation import observe_part_faces_with_handles
    from ..hosts.windows_edge_observation import observe_part_edges_with_handles

    if (
        context.documents is None
        or context.entry is None
        or context.entry.entities is None
    ):
        raise RuntimeError("document entity registry is unavailable")
    observe = (
        observe_part_faces_with_handles if kind == "face"
        else observe_part_edges_with_handles
    )
    result, bindings = observe(
        context.app, context.entry.document, **{f"max_{kind}s": limit}
    )
    result["action"] = "entity.list"
    if result.get("ok"):
        result["scope"] = f"single-solid-part-{kind}s"
        result["entities"] = result.pop(f"{kind}s")
    result = _with_document(
        result, context.documents, context.entry, session_id=context.session_id
    )
    validate_entity_observation("entity.list", result)
    # Both native state reads can be valid even when geometry or the unchanged
    # check failed. Retire observed scopes in order, but never register partial
    # bindings or replace the first native failure with a successful result.
    observation = result.get("observation", {})
    for boundary in ("before", "after"):
        if boundary in observation:
            state = observation[boundary]
            context.entry.entities.observe_scope(
                configuration=state["configuration"],
                update_stamp=state["update_stamp"],
            )
    if result["ok"] and len(bindings) != result[f"{kind}_count"]:
        raise OperationResultInvalid("entity.list: inconsistent exact native bindings")
    return result, bindings


def _register_entities(context: OperationContext, result, bindings, kind):
    state = result["observation"]["after"]
    register = (
        context.entry.entities.register_faces if kind == "face"
        else context.entry.entities.register_edges
    )
    return register(
        bindings,
        configuration=state["configuration"],
        update_stamp=state["update_stamp"],
    )


@_register_handler
def entity_list(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    kind = values.get("kind", "face")
    result, bindings = _observe_entities(context, kind, values.get(f"max_{kind}s", 64))
    if result["ok"]:
        tokens = _register_entities(context, result, bindings, kind)
        for entity, token in zip(result["entities"], tokens):
            entity["entity_id"] = token
    return result


@_register_handler
def entity_inspect(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    from ..hosts.windows_feature_inspection import _state

    if (
        context.documents is None
        or context.entry is None
        or context.entry.entities is None
    ):
        raise RuntimeError("document entity registry is unavailable")
    # Unknown/stale targets fail before a full native traversal. Fresh scope is
    # mandatory; an old handle must never be silently rebound after an edit.
    state, _, _ = _state(context.app, context.entry.document)
    token = values["entity_id"]
    kind = values.get("kind", "face")
    context.entry.entities.resolve(
        token, kind=kind, configuration=state["configuration"],
        update_stamp=state["update_stamp"],
    )
    result, bindings = _observe_entities(context, kind)
    result["action"] = "entity.inspect"
    if result["ok"]:
        state = result["observation"]["after"]
        context.entry.entities.resolve(
            token,
            kind=kind,
            configuration=state["configuration"],
            update_stamp=state["update_stamp"],
        )
        tokens = _register_entities(context, result, bindings, kind)
        result["entity"] = result.pop("entities")[tokens.index(token)]
        result["entity"]["entity_id"] = token
    return result


@_register_handler
def feature_inspect(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    from ..hosts.windows_feature_inspection import (
        inspect_extrusion_feature_windows,
    )

    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    feature_id = values["feature_id"]
    feature = context.documents.resolve_feature(context.entry, feature_id)
    result = inspect_extrusion_feature_windows(
        app=context.app, document=context.entry.document, feature=feature
    )
    result = _with_document(
        result, context.documents, context.entry, session_id=context.session_id
    )
    validate_feature_observation("feature.inspect", result)
    if result["ok"]:
        result["feature"]["feature_id"] = feature_id
    return result


@_register_handler
def feature_set_depth(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    from ..hosts.windows_feature_depth_edits import set_extrusion_depth_windows
    from .feature_depth_results import feature_depth_result

    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    feature_id = values["feature_id"]
    feature = context.documents.resolve_feature(context.entry, feature_id)
    native = set_extrusion_depth_windows(
        app=context.app,
        document=context.entry.document,
        feature=feature,
        depth_mm=values["depth_mm"],
    )
    return feature_depth_result(native, feature_id)


@_register_handler
def sketch_inspect(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    sketch_id = values["sketch_id"]
    feature = context.documents.resolve_sketch(context.entry, sketch_id)
    result = inspect_sketch_windows(
        app=context.app,
        document=context.entry.document,
        sketch_feature=feature,
        max_segments=values.get("max_segments", 1000),
    )
    if isinstance(result.get("sketch"), dict):
        result["sketch"]["sketch_id"] = sketch_id
    return _with_document(
        result, context.documents, context.entry, session_id=context.session_id
    )


@_register_handler
def sketch_circle(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    result, feature = create_circle_sketch_windows_with_handle(
        app=context.app,
        document=context.entry.document,
        plane=values["plane"],
        radius_mm=float(values["radius_mm"]),
        center_x_mm=float(values.get("center_x_mm", 0)),
        center_y_mm=float(values.get("center_y_mm", 0)),
    )
    if feature is not None and isinstance(result.get("sketch"), dict):
        result["sketch"]["sketch_id"] = context.documents.register_sketch(
            context.entry, feature
        )
    return result


def _with_dimension_ids(
    result: Dict[str, Any], dimension_id: str, sketch_id: str
) -> Dict[str, Any]:
    result["sketch_id"] = sketch_id
    if isinstance(result.get("dimension"), dict):
        result["dimension"].update(dimension_id=dimension_id, sketch_id=sketch_id)
    return result


@_register_handler
def sketch_fix_center(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    sketch_id = values["sketch_id"]
    feature = context.documents.resolve_sketch(context.entry, sketch_id)
    result, _relation = fix_rectangle_center_windows_with_handle(
        app=context.app,
        document=context.entry.document,
        sketch_feature=feature,
    )
    if result.get("ok") is True and _relation is None:
        raise OperationResultInvalid(
            "sketch.fix-center: native verification returned no fixed relation"
        )
    # The exact relation stays in the worker. Snapshot point/diagonal IDs are
    # evidence scoped to this sketch, not stable constraint handles.
    result.update(action="sketch.fix-center", sketch_id=sketch_id)
    return result


@_register_handler
def sketch_dimension_diameter(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    sketch_id = values["sketch_id"]
    sketch_feature = context.documents.resolve_sketch(context.entry, sketch_id)
    result, native_dimension = create_circle_diameter_windows_with_handle(
        app=context.app,
        document=context.entry.document,
        sketch_feature=sketch_feature,
        diameter_mm=float(values["diameter_mm"]),
    )
    result["sketch_id"] = sketch_id
    if native_dimension is not None:
        dimension_id = context.documents.register_dimension(
            context.entry,
            sketch_id,
            native_dimension,
            kind="diameter",
            profile_kind="circle",
        )
        # Even a failed post-mutation verification must expose its live handle.
        result.setdefault("dimension", {})
        _with_dimension_ids(result, dimension_id, sketch_id)
    return result


@_register_handler
def dimension_discover_diameter(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    sketch_id = values["sketch_id"]
    feature = context.documents.resolve_sketch(context.entry, sketch_id)
    result, native_dimension = discover_circle_diameter_windows_with_handle(
        app=context.app,
        document=context.entry.document,
        sketch_feature=feature,
    )
    result["action"] = "dimension.discover-diameter"
    result["sketch_id"] = sketch_id
    if isinstance(result.get("dimension"), dict):
        # Only this registry can confer an ID. In particular a failed native
        # read must not expose a stale or accidentally supplied wire handle.
        result["dimension"].pop("dimension_id", None)
        result["dimension"].pop("sketch_id", None)
    result = _with_document(
        result, context.documents, context.entry, session_id=context.session_id
    )
    if result.get("ok") is True:
        if native_dimension is None:
            raise OperationResultInvalid(
                "dimension.discover-diameter: native observation returned no dimension"
            )
        validate_dimension_discovery_observation(result)
        dimension_id = context.documents.register_dimension(
            context.entry,
            sketch_id,
            native_dimension,
            kind="diameter",
            profile_kind="circle",
        )
        _with_dimension_ids(result, dimension_id, sketch_id)
    return result


@_register_handler
def dimension_discover_rectangle(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    sketch_id = values["sketch_id"]
    feature = context.documents.resolve_sketch(context.entry, sketch_id)
    result, handles = discover_rectangle_dimensions_windows_with_handles(
        app=context.app, document=context.entry.document, sketch_feature=feature
    )
    result.update(action="dimension.discover-rectangle", sketch_id=sketch_id)
    for descriptor in result.get("dimensions", {}).values():
        descriptor.pop("dimension_id", None)
        descriptor.pop("sketch_id", None)
    result = _with_document(
        result, context.documents, context.entry, session_id=context.session_id
    )
    if result.get("ok") is True:
        validate_rectangle_discovery_observation(result)
        if any(handles.get(kind) is None for kind in ("width", "height")):
            raise OperationResultInvalid(
                "dimension.discover-rectangle: verified pair has missing native handles"
            )
        for kind in ("width", "height"):
            dimension_id = context.documents.register_dimension(
                context.entry,
                sketch_id,
                handles[kind],
                kind=kind,
                profile_kind="rectangle",
            )
            result["dimensions"][kind].update(
                dimension_id=dimension_id, sketch_id=sketch_id
            )
    return result


@_register_handler
def sketch_dimension_rectangle(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    sketch_id = values["sketch_id"]
    feature = context.documents.resolve_sketch(context.entry, sketch_id)
    result, handles = create_rectangle_dimensions_windows_with_handles(
        app=context.app,
        document=context.entry.document,
        sketch_feature=feature,
        width_mm=float(values["width_mm"]),
        height_mm=float(values["height_mm"]),
    )
    result["sketch_id"] = sketch_id
    # Failed/cleanup-failed partial creations retain native evidence, not
    # verified public bindings. Only this registry may confer live IDs.
    for descriptor in result.get("dimensions", {}).values():
        descriptor.pop("dimension_id", None)
        descriptor.pop("sketch_id", None)
    result = _with_document(
        result, context.documents, context.entry, session_id=context.session_id
    )
    if result.get("ok") is True:
        validate_rectangle_creation_observation(result)
        if any(handles.get(kind) is None for kind in ("width", "height")):
            raise OperationResultInvalid(
                "sketch.dimension-rectangle: verified pair has missing native handles"
            )
        for kind in ("width", "height"):
            dimension_id = context.documents.register_dimension(
                context.entry,
                sketch_id,
                handles[kind],
                kind=kind,
                profile_kind="rectangle",
            )
            result["dimensions"][kind].update(
                dimension_id=dimension_id, sketch_id=sketch_id
            )
    return result


@_register_handler
def dimension_inspect(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    dimension_id = values["dimension_id"]
    item = context.documents.resolve_dimension(context.entry, dimension_id)
    feature = context.documents.resolve_sketch(context.entry, item.sketch_id)
    adapter = (
        inspect_dimension_windows
        if item.kind == "diameter"
        else inspect_rectangle_dimension_windows
    )
    result = adapter(
        app=context.app,
        document=context.entry.document,
        sketch_feature=feature,
        dimension=item.dimension,
        **({"kind": item.kind} if item.kind != "diameter" else {}),
    )
    if item.kind != "diameter":
        result.setdefault("dimension", {"kind": item.kind})
    return _with_document(
        _with_dimension_ids(result, dimension_id, item.sketch_id),
        context.documents,
        context.entry,
        session_id=context.session_id,
    )


@_register_handler
def dimension_set(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    dimension_id = values["dimension_id"]
    item = context.documents.resolve_dimension(context.entry, dimension_id)
    feature = context.documents.resolve_sketch(context.entry, item.sketch_id)
    adapter = (
        set_dimension_windows
        if item.kind == "diameter"
        else set_rectangle_dimension_windows
    )
    result = adapter(
        app=context.app,
        document=context.entry.document,
        sketch_feature=feature,
        dimension=item.dimension,
        value_mm=float(values["value_mm"]),
        **({"kind": item.kind} if item.kind != "diameter" else {}),
    )
    if item.kind != "diameter":
        result.setdefault("dimension", {"kind": item.kind})
    return _with_dimension_ids(result, dimension_id, item.sketch_id)


def _bind_created_feature(
    context: OperationContext, result: Dict[str, Any], feature: Any
) -> Dict[str, Any]:
    descriptor = result.get("feature")
    if result.get("ok") and (feature is None or not isinstance(descriptor, dict)):
        raise OperationResultInvalid(
            "feature creation succeeded without an exact object"
        )
    if feature is not None and isinstance(descriptor, dict):
        try:
            descriptor["feature_id"] = context.documents.register_feature(
                context.entry, feature
            )
        except Exception as exc:
            if result.get("ok"):
                raise
            # A registry problem must not replace the native mutation's first
            # failure, or falsely suggest the created feature was rolled back.
            result.setdefault("warnings", []).append(
                {"code": "feature-handle-unavailable", "message": str(exc)}
            )
    return result


@_register_handler
def feature_extrude(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    sketch_id = values["sketch_id"]
    sketch_feature = context.documents.resolve_sketch(context.entry, sketch_id)
    result, feature = extrude_sketch_windows_with_handle(
        app=context.app,
        document=context.entry.document,
        sketch_feature=sketch_feature,
        depth_mm=float(values["depth_mm"]),
        reverse=values.get("reverse", False),
        merge=values.get("merge", True),
    )
    result["sketch_id"] = sketch_id
    return _bind_created_feature(context, result, feature)


@_register_handler
def feature_cut_extrude(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    sketch_id = values["sketch_id"]
    sketch_feature = context.documents.resolve_sketch(context.entry, sketch_id)
    result, feature = cut_extrude_sketch_windows_with_handle(
        app=context.app,
        document=context.entry.document,
        sketch_feature=sketch_feature,
        depth_mm=float(values["depth_mm"]),
        reverse=values.get("reverse", False),
    )
    result["sketch_id"] = sketch_id
    return _bind_created_feature(context, result, feature)


@_register_handler
def part_create_box(
    context: OperationContext, values: Dict[str, Any]
) -> Dict[str, Any]:
    result, created_document = create_box_part_windows_with_handle(
        str(values["output"]),
        width_mm=float(values["width_mm"]),
        height_mm=float(values["height_mm"]),
        depth_mm=float(values["depth_mm"]),
        template=(
            str(values["template"]) if values.get("template") is not None else None
        ),
        overwrite=bool(values.get("overwrite", False)),
        app=context.app,
    )
    if context.documents is not None and result.get("ok"):
        if created_document is None:
            raise RuntimeError("SOLIDWORKS returned no document after creating a part")
        context.entry = context.documents.register(created_document)
        context.documents.set_current(context.entry, session_id=context.session_id)
        return _with_document(
            result, context.documents, context.entry, session_id=context.session_id
        )
    return result


_expected_handlers = {
    spec.handler for spec in OPERATION_CATALOG.values() if spec.handler is not None
}
if set(_HANDLERS) != _expected_handlers:
    raise RuntimeError("operation catalog and worker handlers differ")


def execute_operation(
    app: Any,
    operation: str,
    parameters: Dict[str, Any],
    *,
    documents: Optional[DocumentRegistry] = None,
    session_id: str = DEFAULT_SESSION_ID,
    document_id: Optional[str] = None,
    expected_update_stamp: Optional[int] = None,
    lease_id: Optional[str] = None,
) -> Dict[str, Any]:
    values = validate_operation_request(
        operation,
        parameters,
        document_id=document_id,
        expected_update_stamp=expected_update_stamp,
        lease_id=lease_id,
    )
    spec = OPERATION_CATALOG[operation]
    if spec.handler is None:
        raise ValueError(f"operation belongs to the supervisor: {operation}")
    context = OperationContext(
        app, operation, documents, session_id, document_id, lease_id
    )
    if spec.selected_document and documents is not None:
        context.entry = documents.resolve(document_id, session_id=session_id)
        if expected_update_stamp is not None:
            actual = documents.describe(context.entry, session_id=session_id).get(
                "update_stamp"
            )
            if actual is None:
                raise DocumentUpdateStampUnavailable(
                    "the selected document does not expose GetUpdateStamp"
                )
            if actual != expected_update_stamp:
                raise DocumentUpdateConflict(
                    "the selected document changed: expected update stamp "
                    f"{expected_update_stamp}, found {actual}"
                )
        if spec.lease_guarded:
            documents.require_lease(
                context.entry, session_id=session_id, lease_id=lease_id
            )
        # Reject unknown document-local references before temporary activation.
        # A malformed target must not touch even the foreground selection.
        if "sketch_id" in values:
            documents.resolve_sketch(context.entry, values["sketch_id"])
        if "feature_id" in values:
            documents.resolve_feature(context.entry, values["feature_id"])
        if "dimension_id" in values:
            binding = documents.resolve_dimension(context.entry, values["dimension_id"])
            if (binding.kind, binding.profile_kind) not in (
                ("diameter", "circle"),
                ("width", "rectangle"),
                ("height", "rectangle"),
            ):
                raise UnsupportedDimensionKind(
                    "unsupported native dimension/profile binding"
                )
    activation = (
        documents.temporarily_activate(context.entry)
        if spec.temporary_activation
        and documents is not None
        and context.entry is not None
        else nullcontext()
    )
    with activation as activation_warnings:
        result = _HANDLERS[spec.handler](context, values)
    if isinstance(activation_warnings, list) and activation_warnings:
        result.setdefault("warnings", []).extend(activation_warnings)
        if result.get("ok"):
            result["ok"] = False
            result["error"] = {
                "type": "DocumentActivationFailed",
                "message": "operation completed but the previous foreground document could not be restored",
            }
    if (
        spec.temporary_activation
        and documents is not None
        and context.entry is not None
    ):
        return _with_document(result, documents, context.entry, session_id=session_id)
    return result
