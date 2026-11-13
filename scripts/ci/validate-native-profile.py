"""Reject ambiguous native CI inputs before private runtime jobs can start."""
import json
import os
import re

FEATURE_REFS = {
    "native_topology_targeted": "refs/heads/codex/swcli-topology-references",
    "image_quality_calibration": "refs/heads/codex/docprops-export-options",
    "image_quality_public_acceptance": "refs/heads/codex/docprops-export-options",
    "dimension_format_public": "refs/heads/codex/docprops-dimension-format",
    "dimension_format_calibration": "refs/heads/codex/docprops-dimension-format",
    "line_font_public": "refs/heads/codex/docprops-line-style",
    "line_font_calibration": "refs/heads/codex/docprops-line-style",
    "stl_options_public": "refs/heads/codex/swcli-stl-export-options",
    "stl_options_targeted": "refs/heads/codex/swcli-stl-export-options",
    "calibrate_font_scopes": "refs/heads/codex/docprops-font-scopes",
    "calibrate_tolerances": "refs/heads/codex/docprops-tolerances",
    "accept_tolerances": "refs/heads/codex/docprops-tolerances",
    "detailing_calibration": "refs/heads/codex/docprops-detailing",
    "detailing_public_gate": "refs/heads/codex/docprops-detailing",
    "native_revolve_calibration": "refs/heads/codex/swcli-revolve-feature",
    "native_revolve_public": "refs/heads/codex/swcli-revolve-feature",
    "native_revolve_direction": "refs/heads/codex/swcli-revolve-feature-next",
}
FLAGS = ("native_full", *FEATURE_REFS)


def enabled(value):
    if type(value) is bool:
        return value
    if isinstance(value, str) and value in ("", "true", "false"):
        return value == "true"
    raise ValueError("native scope flags must be booleans")


def resolve(event, ref, inputs, *, head=None):
    if not isinstance(inputs, dict):
        raise ValueError("workflow inputs must be an object")
    font_profile = inputs.get("font_scopes_profile", "internal")
    if font_profile not in ("internal", "public-notes"):
        raise ValueError("unknown font profile")
    if font_profile != "internal" and not enabled(inputs.get("calibrate_font_scopes", False)):
        raise ValueError("font public profile requires font validation")
    selected = [key for key in FLAGS if enabled(inputs.get(key, False))]
    if event != "workflow_dispatch":
        if selected:
            raise ValueError("native scope flags require workflow_dispatch")
        return "full" if event == "push" and ref.startswith("refs/tags/v") else "portable"
    if len(selected) > 1:
        raise ValueError("choose one native scope; full and feature profiles are mutually exclusive")
    if not selected:
        return "portable"
    scope = selected[0]
    if scope == "native_revolve_direction":
        expected = inputs.get("revolve_direction_head", "")
        if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{40}", expected) is None or expected != head:
            raise ValueError("revolve direction requires the exact selected 40-character commit head")
        if any(enabled(inputs.get(key, False)) for key in
               ("units_calibration", "units_write_calibration", "units_public_acceptance")):
            raise ValueError("revolve direction cannot mix with units profiles")
    if scope in FEATURE_REFS and ref != FEATURE_REFS[scope]:
        raise ValueError("feature profile requires its exact development branch: " + scope)
    return {"native_full": "full", "calibrate_tolerances": "tolerances-calibration",
            "accept_tolerances": "tolerances-public"}.get(scope, scope)


def main():
    profile = resolve(os.environ["GITHUB_EVENT_NAME"], os.environ["GITHUB_REF"],
                      json.loads(os.environ.get("SWCLI_NATIVE_INPUTS", "{}")), head=os.environ.get("GITHUB_SHA"))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("profile=" + profile + "\n")
    print("Validated native scope: " + profile)


if __name__ == "__main__":
    main()
