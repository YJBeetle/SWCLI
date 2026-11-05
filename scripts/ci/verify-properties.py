"""Installed public CLI reads of separately prepared native property fixtures."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath

from swcli.result_schemas import validate_operation_result

spec = importlib.util.spec_from_file_location(
    "_properties_public_modeling", Path(__file__).with_name("verify-modeling.py")
)
modeling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modeling)
require = modeling.require

EXPECTED = {
    "Chinese Name": (30, "测试零件"),
    "English Name": (30, "Property fixture"),
    "Drawing No": (30, ""),
    "Quantity": (3, "42"),
    "Approved": (11, "Yes"),
}


def verify_properties(result):
    validate_operation_result("document.properties", result)
    require(result["ok"] and result["scope"] == "document", "property read failed")
    rows = {row["name"]: row for row in result["properties"]}
    require(len(result["properties"]) == len(rows) == len(EXPECTED)
            and set(rows) == set(EXPECTED), "property list lost rows or leaked configuration metadata")
    for name, (code, raw) in EXPECTED.items():
        row = rows[name]
        require(row["type_code"] == code and row["raw_value"] == raw
                and row["evaluated_value"] == raw and row["resolution"] == "resolved"
                and row["was_resolved"] is True and row["linked"] is False,
                "property value/type/evaluation differs from prepared fixture")
    return rows


def run(gate, fixtures, *, host_fixtures=None, save_copy=False):
    gate.record.update(state="running", success=False, property_cases=[])
    gate.record["host"] = gate.health()["host"]
    gate.require_empty()
    for suffix in ("SLDPRT", "SLDASM"):
        path = fixtures / ("properties." + suffix)
        require(path.is_file(), "prepared property fixture is missing")
        before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        source_host = str(PureWindowsPath(host_fixtures) / path.name) if host_fixtures else str(path)
        mode = [] if save_copy else ["--read-only"]
        opened = gate.command("document", "open", source_host, *mode)
        require(opened["api_errors"] == opened["api_warnings"] == 0
                and PureWindowsPath(opened["document"]["path"]) == PureWindowsPath(source_host),
                "property fixture did not open cleanly at the requested path")
        target = opened["document"]["document_id"]
        foreground = gate.create()
        case = {"format": suffix, "source_sha256": before_hash, "open": opened}
        gate.record["property_cases"].append(case)
        before = gate.command("document", "inspect", document=target)["document"]
        stamp = before["update_stamp"]
        observer = gate.session + "-reader"
        gate.command("document", "lease", "acquire", "--ttl-seconds", 600, document=target)
        listing = case["listing"] = gate.command(
            "document", "properties", "--if-update-stamp", stamp, document=target, session=observer
        )
        gate.background(listing, target)
        rows = verify_properties(listing)
        require(listing["requested_name"] is None, "listing unexpectedly became a lookup")
        for name in EXPECTED:
            response = gate.command(
                "document", "properties", "--name", name, "--if-update-stamp", stamp,
                document=target, session=observer,
            )
            validate_operation_result("document.properties", response)
            gate.background(response, target)
            require(response["requested_name"] == name and response["properties"] == [rows[name]],
                    "named lookup disagrees with listing")
            case.setdefault("lookups", {})[name] = response
        missing = case["missing"] = gate.command(
            "document", "properties", "--name", "Absent property", document=target, session=observer
        )
        validate_operation_result("document.properties", missing)
        require(missing["properties"] == [], "missing name became an existing property")
        gate.command(
            "document", "properties", "--if-update-stamp", stamp + 1,
            document=target, expected_error="DocumentUpdateConflict",
        )
        after = gate.command("document", "inspect", document=target)["document"]
        require(before == after and not after["modified"], "property reads changed document state")
        reopened_host = source_host
        saved_hash = before_hash
        saved_path = path
        if save_copy:
            saved_path = gate.directory / ("saved-" + path.name)
            reopened_host = str(PureWindowsPath(gate.host_directory) / saved_path.name)
            saved = case["save_copy"] = gate.write(
                "document", "save-as", reopened_host, document=target
            )
            require(saved["save_errors"] == 0 and saved["save_warnings"] is None
                    and not saved["document"]["modified"] and saved_path.is_file(),
                    "property fixture save-as failed")
            saved_hash = hashlib.sha256(saved_path.read_bytes()).hexdigest()
            case["saved_sha256"] = saved_hash
        gate.close(target)
        reopened = case["reopen"] = gate.command("document", "open", reopened_host, "--read-only")
        fresh = reopened["document"]["document_id"]
        require(fresh != target and reopened["api_errors"] == reopened["api_warnings"] == 0
                and PureWindowsPath(reopened["document"]["path"]) == PureWindowsPath(reopened_host),
                "property reopen did not acquire a clean fresh handle")
        reopened_read = case["reopened_properties"] = gate.command("document", "properties", document=fresh)
        require(verify_properties(reopened_read) == rows, "reopened native property values changed")
        require(not gate.command("document", "inspect", document=fresh)["document"]["modified"]
                and hashlib.sha256(path.read_bytes()).hexdigest() == before_hash
                and hashlib.sha256(saved_path.read_bytes()).hexdigest() == saved_hash,
                "read-only property gate changed fixture bytes/state")
        gate.close(fresh)
        gate.close(foreground)
        gate.require_empty()
        case["success"] = True
        gate.checkpoint("properties-" + suffix + "-verified")
    gate.record["host_after"] = gate.health()["host"]
    require(gate.record["host_after"] == gate.record["host"], "host changed during property reads")
    gate.record.update(state="completed", success=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--fixture-dir", required=True, type=Path)
    parser.add_argument("--endpoint", default=os.environ.get("SWCLI_ENDPOINT", modeling.DEFAULT_ENDPOINT))
    parser.add_argument("--host-fixture-dir", type=modeling.host_directory)
    parser.add_argument("--host-output-dir", type=modeling.host_directory)
    parser.add_argument("--cli-command", type=modeling.executable)
    parser.add_argument("--save-copy", action="store_true", help="save to a new native file before reopening")
    args = parser.parse_args(argv)
    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    gate = modeling.ModelingSmoke(
        directory=args.output_dir, host_directory=args.host_output_dir or str(args.output_dir),
        cli=[args.cli_command] if args.cli_command else None,
        endpoint=args.endpoint,
    )
    gate.record_path = args.output_dir / "properties.json"
    with gate.record_path.open("x", encoding="utf-8") as stream:
        json.dump(gate.record, stream)
    try:
        run(gate, args.fixture_dir, host_fixtures=args.host_fixture_dir, save_copy=args.save_copy)
    except BaseException:
        gate.record["state"] = "failed"
        raise
    finally:
        gate.cleanup()
        gate.checkpoint("properties-final")
    require(not gate.record["cleanup_errors"], "property gate cleanup failed")


if __name__ == "__main__":
    main()
