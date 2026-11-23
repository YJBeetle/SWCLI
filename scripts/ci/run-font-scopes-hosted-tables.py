"""Sequence the three hosted, table-only font checks with their original receipts."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gate_support.font_inheritance import file_digest, require

REPOSITORY = "YJBeetle/SWCLI"
REF = "refs/heads/codex/docprops-font-scopes-next"
PHASES = ("probe", "fixture", "inheritance")


def source_head(environment):
    expected = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_REF": REF,
        "GITHUB_WORKFLOW_REF": REPOSITORY + "/.github/workflows/ci.yml@" + REF,
        "RUNNER_ENVIRONMENT": "github-hosted",
    }
    require(all(environment.get(key) == value for key, value in expected.items()),
            "hosted table fonts require the authorized manual CI branch")
    head = environment.get("GITHUB_SHA", "")
    require(re.fullmatch(r"[0-9a-f]{40}", head) is not None, "hosted table fonts require an exact source SHA")
    return head


def require_watchdog(directory, head, profile):
    receipt = json.loads((directory / "watchdog.json").read_text(encoding="utf-8"))
    require(receipt["success"] is True and receipt["supervision_verified"] is True
            and receipt["profile"] == profile and receipt["source_head"] == head
            and receipt["requested_scope"] == "tables", "table watchdog receipt differs from the expected phase")
    return receipt


def require_probe(directory, head):
    receipt = require_watchdog(directory, head, "next-fixture")
    require(receipt["supervision_probe"] is True and receipt["native_executed"] is False
            and not (directory / "native" / "report.json").exists()
            and not (directory / "native" / "trace.jsonl").exists(),
            "the table font probe must prove launch identity without COM")


def qualified_fixture(directory, head):
    receipt = require_watchdog(directory, head, "next-fixture")
    require(receipt["supervision_probe"] is False, "expected the generated fixture phase")
    native = directory / "native"
    report = json.loads((native / "report.json").read_text(encoding="utf-8"))
    require(report["success"] is True and not report["cleanup_errors"] and len(report["cases"]) == 1,
            "missing successful table fixture report")
    case = report["cases"][0]
    drawing = native / "font-tables-fixture.SLDDRW"
    require(case["success"] is True and case["scope"] == "tables" and case["source_head"] == head
            and case["source_kind"] == "generated-GB-table" and case["save_verified"] is True
            and case["reopen"]["read_only"] is True and not drawing.is_symlink()
            and Path(case["path"]).resolve() == drawing.resolve(),
            "fixture receipt does not describe this generated table drawing")
    digest = case["file_sha256"]
    require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None and file_digest(drawing) == digest,
            "generated table drawing SHA-256 differs from the fixture receipt")
    return drawing, digest


def require_inheritance(directory, head, digest):
    receipt = require_watchdog(directory, head, "internal")
    require(receipt["inheritance_fixture_sha256"] == digest, "inheritance watchdog used another fixture")
    report = json.loads((directory / "native" / "report.json").read_text(encoding="utf-8"))
    cases = report["cases"]
    require(report["success"] is True and not report["cleanup_errors"] and len(cases) == 3
            and {case["kind"] for case in cases} == {"part", "assembly", "drawing"}
            and all(case["success"] is True and case["selected_scopes"] == ["tables"] for case in cases),
            "expected all three successful internal font cases")
    drawing = next(case for case in cases if case["kind"] == "drawing")
    witness = drawing["inheritance_witness"]
    require(witness["scope"] == "tables" and witness["success"] is True
            and drawing["fixture"]["input_sha256"] == digest,
            "missing the internal table inheritance witness")


def run_phase(phase, root, head, swconst, template):
    output = root / phase
    profile = "internal" if phase == "inheritance" else "next-fixture"
    command = [sys.executable, "-I", str(HERE / "run-font-scopes-calibration.py"),
               "--scope", "tables", "--profile", profile, "--source-head", head,
               "--output-dir", str(output), "--swconst", str(swconst), "--drawing-template", str(template)]
    if phase == "probe":
        command.append("--supervision-probe")
    else:
        require_probe(root / "probe", head)
    if phase == "inheritance":
        drawing, digest = qualified_fixture(root / "fixture", head)
        command.extend(("--inheritance-drawing", str(drawing), "--inheritance-sha256", digest))

    result = subprocess.run(command, check=False)
    if result.returncode:
        print(f"Table font {phase} stopped; preserve original evidence under {output}", file=sys.stderr)
        return result.returncode

    if phase == "probe":
        require_probe(output, head)
    elif phase == "fixture":
        qualified_fixture(output, head)
    else:
        require_inheritance(output, head, digest)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=PHASES)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--drawing-template", type=Path, required=True)
    args = parser.parse_args()
    head = source_head(os.environ)
    checkout = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip()
    require(checkout == head, "hosted table fonts checkout differs from dispatch SHA")
    require(sys.platform == "win32" and sys.version_info[:2] == (3, 14) and sys.prefix != sys.base_prefix,
            "hosted table fonts require the installed Windows Python 3.14 venv")
    return run_phase(args.phase, args.output_dir.resolve(), head, args.swconst, args.drawing_template)


if __name__ == "__main__":
    raise SystemExit(main())
