"""Reject mutually exclusive native modes and wrong-branch Line Font requests.

Runs before package installation in the unprivileged portable jobs. No CAD,
secrets, native runtime, or API operation is needed to validate this routing.
"""
import json
import os

BRANCH = "refs/heads/codex/docprops-line-style"


def validate_route(*, event, ref, native_full=False, internal=False, public=False):
    flags = (native_full, internal, public)
    if any(type(value) is not bool for value in flags):
        raise ValueError("native mode flags must be boolean")
    if sum(flags) > 1:
        raise ValueError("native_full, line_font_calibration and line_font_public are mutually exclusive")
    if any(flags) and event != "workflow_dispatch":
        raise ValueError("native mode inputs are only accepted for workflow_dispatch")
    if (internal or public) and ref != BRANCH:
        raise ValueError("Line Font gates require the codex/docprops-line-style branch")
    if public:
        return "line-font-public"
    if internal:
        return "line-font-internal"
    if native_full:
        return "full"
    if event == "push" and ref.startswith("refs/tags/v"):
        return "tag-policy-controls-full"
    return "portable"


def boolean(name):
    value = os.environ.get(name, "false").lower()
    if value not in ("true", "false"):
        raise ValueError(name + " must be true or false")
    return value == "true"


def main():
    mode = validate_route(event=os.environ["GITHUB_EVENT_NAME"], ref=os.environ["GITHUB_REF"],
        native_full=boolean("SWCLI_ROUTE_FULL"), internal=boolean("SWCLI_ROUTE_LINE_FONT_INTERNAL"),
        public=boolean("SWCLI_ROUTE_LINE_FONT_PUBLIC"))
    print(json.dumps({"validated_native_route": mode}))


if __name__ == "__main__":
    main()
