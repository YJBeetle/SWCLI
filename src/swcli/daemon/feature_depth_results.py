"""Project guarded native depth evidence into the public typed result."""

from copy import deepcopy


def feature_depth_result(native, feature_id):
    # Keep mutation/cleanup evidence on failures, but do not expose private
    # feature-data objects, native profile fingerprints or control internals.
    result = {"feature_id": feature_id}
    for key in (
        "ok",
        "action",
        "mutation",
        "requested_depth_mm",
        "before_depth_mm",
        "depth_changed",
        "definition_after",
        "measurement_before",
        "measurement_after",
        "verification",
        "rebuilt",
        "final_state",
        "modification_may_have_happened",
        "error",
        "warnings",
        "feature",
    ):
        if key in native:
            result[key] = deepcopy(native[key])
    if "feature" in result:
        result["feature"]["feature_id"] = feature_id
    checks = {}
    for phase in ("preflight", "postflight"):
        source = native.get(phase)
        if source is not None:
            checks[phase] = {
                key: deepcopy(source[key])
                for key in (
                    "ok",
                    "selection_access",
                    "observation",
                    "error",
                    "warnings",
                )
                if key in source
            }
    if checks:
        result["selection_checks"] = checks
    return result
