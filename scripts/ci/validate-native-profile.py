"""Reject ambiguous native CI inputs before private runtime jobs can start."""
import json
import os

FEATURE_REFS = {
    "calibrate_tolerances": "refs/heads/codex/docprops-tolerances",
    "accept_tolerances": "refs/heads/codex/docprops-tolerances",
    "detailing_calibration": "refs/heads/codex/docprops-detailing",
    "detailing_public_gate": "refs/heads/codex/docprops-detailing",
    "native_revolve_calibration": "refs/heads/codex/swcli-revolve-feature",
    "native_revolve_public": "refs/heads/codex/swcli-revolve-feature",
}
FLAGS = ("native_full", *FEATURE_REFS)


def enabled(value):
    if type(value) is bool:
        return value
    if isinstance(value, str) and value in ("", "true", "false"):
        return value == "true"
    raise ValueError("native scope flags must be booleans")


def resolve(event, ref, inputs):
    if not isinstance(inputs, dict):
        raise ValueError("workflow inputs must be an object")
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
    if scope in FEATURE_REFS and ref != FEATURE_REFS[scope]:
        raise ValueError("feature profile requires its exact development branch: " + scope)
    return {"native_full": "full", "calibrate_tolerances": "tolerances-calibration",
            "accept_tolerances": "tolerances-public"}.get(scope, scope)


def main():
    profile = resolve(os.environ["GITHUB_EVENT_NAME"], os.environ["GITHUB_REF"],
                      json.loads(os.environ.get("SWCLI_NATIVE_INPUTS", "{}")))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("profile=" + profile + "\n")
    print("Validated native scope: " + profile)


if __name__ == "__main__":
    main()
