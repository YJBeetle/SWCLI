"""Public read-only topology handlers on the resident COM worker."""

from ..hosts.windows import _com_value, _error
from ..hosts.windows_feature_inspection import _state, _same
from ..hosts.windows_topology_references import (
    PersistentReferenceScopeMismatch, make_reference, verify_reference,
)
from ..topology_references import POLICY, document_path, decode_reference


def reference_operation(context, values, *, observe, register, with_document):
    action = context.operation
    result = {"ok": False, "action": action}
    before = None
    registry = context.entry.entities
    document = context.entry.document
    bindings = None
    try:
        before, edit_before, foreground_before = _state(context.app, document)
        result["observation"] = {"before": before, "unchanged": False}
        registry.observe_scope(configuration=before["configuration"], update_stamp=before["update_stamp"])
        path = document_path(_com_value(document, "GetPathName"))
        payload = None
        if action == "entity.reference-create":
            kind = values.get("kind", "face")
            target = registry.resolve(values["entity_id"], kind=kind,
                                      configuration=before["configuration"], update_stamp=before["update_stamp"])
        else:
            payload = decode_reference(values["reference"])
            kind = payload["kind"]
            if path != payload["document_path"] or before["configuration"] != payload["configuration"]:
                raise PersistentReferenceScopeMismatch("saved path or exact configuration differs from reference scope")
        observations, all_bindings = {}, {}
        for current_kind in ("face", "edge"):
            observed, observed_bindings = observe(context, current_kind)
            if not observed["ok"]:
                # Keep the first native failure and its original error/details.
                result["error"] = observed["error"]
                if observed.get("warnings"):
                    result["warnings"] = observed["warnings"]
                raise RuntimeError("complete native topology observation failed")
            if observed["observation"]["before"] != before or observed["observation"]["after"] != before:
                raise RuntimeError("topology observation scope changed between complete kinds")
            observations[current_kind], all_bindings[current_kind] = observed, observed_bindings
        faces, edges = all_bindings["face"], all_bindings["edge"]
        result.update(reference_scope={"document_path": path, "configuration": before["configuration"]},
                      topology_policy=POLICY, kind=kind, face_count=len(faces), edge_count=len(edges))
        if payload is None:
            reference = make_reference(context.app, target.binding, path=path, state=before,
                                       kind=kind, faces=faces, edges=edges)
            result.update(reference=reference, entity_id=values["entity_id"],
                          captured_update_stamp=before["update_stamp"])
        else:
            index = verify_reference(context.app, _com_value(document, "Extension"), payload,
                                     faces=faces, edges=edges)
            result.update(captured_update_stamp=payload["captured_update_stamp"],
                          native_status=0, resolution="resolved", topology_verified=True)
            # Defer handle issuance until the final state check succeeds.
            bindings = (observations[kind], all_bindings[kind], index, kind)
    except Exception as exc:
        if "error" not in result:
            result["error"] = _error(exc)
        if type(getattr(exc, "native_status", None)) is int:
            result["native_status"] = exc.native_status
    finally:
        if before is not None:
            try:
                after, edit_after, foreground_after = _state(context.app, document)
                registry.observe_scope(configuration=after["configuration"], update_stamp=after["update_stamp"])
                unchanged = (before == after and _same(context.app, edit_before, edit_after)
                             and _same(context.app, foreground_before, foreground_after)
                             and ("reference_scope" not in result or document_path(_com_value(document, "GetPathName"))
                                  == result["reference_scope"]["document_path"]))
                result["observation"].update(after=after, unchanged=unchanged)
                if not unchanged:
                    raise RuntimeError("persistent-reference observation changed document/configuration/state")
            except Exception as exc:
                if "error" in result:
                    result.setdefault("warnings", []).append({"code": "reference-final-state-check-failed", "message": str(exc)})
                else:
                    result["error"] = _error(exc)
        if "error" in result:
            for field in ("reference", "entity_id", "entity", "resolution", "topology_verified"):
                result.pop(field, None)
    if "error" not in result:
        if bindings is not None:
            observed, native_bindings, index, kind = bindings
            tokens = register(context, observed, native_bindings, kind)
            result["entity"] = {**observed["entities"][index], "entity_id": tokens[index]}
        result["ok"] = True
    try:
        return with_document(result, context.documents, context.entry, session_id=context.session_id)
    except Exception as exc:
        if "error" not in result:
            raise
        result.setdefault("warnings", []).append({
            "code": "reference-document-description-failed", "message": str(exc)})
        result["session_id"] = context.session_id
        return result
