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
SUMMARY_VALUES = {"title": "验收标题", "subject": "Round trip", "author": "验收作者",
                  "keywords": "CAD, metadata", "comment": "第一行\nSecond line"}
ROUNDTRIP_NAME = "Metadata Roundtrip"
DELETED_NAME = "Metadata Delete Fixture"


def verify_properties(result, expected=EXPECTED):
    validate_operation_result("document.properties", result)
    require(result["ok"] and result["scope"] == "document", "property read failed")
    rows = {row["name"]: row for row in result["properties"]}
    require(len(result["properties"]) == len(rows) == len(expected)
            and set(rows) == set(expected), "property list lost rows or leaked configuration metadata")
    for name, (code, raw) in expected.items():
        row = rows[name]
        require(row["type_code"] == code and row["raw_value"] == raw
                and row["evaluated_value"] == raw and row["resolution"] == "resolved"
                and row["was_resolved"] is True and row["linked"] is False,
                "property value/type/evaluation differs from prepared fixture")
    return rows


def check_metadata(gate, document, configuration):
    summary = gate.command("document", "summary", document=document)
    validate_operation_result("document.summary", summary)
    require(summary["saved_version_history"], "saved fixture version history is missing")
    require(all(summary["fields"][key] == value for key, value in SUMMARY_VALUES.items()),
            "summary values did not persist")
    scoped = gate.command("document", "properties", "--configuration", configuration, document=document)
    validate_operation_result("document.properties", scoped)
    require(scoped["scope"] == "configuration" and scoped["configuration"] == configuration,
            "configuration scope differs from the selected configuration")
    require({row["name"]: row["raw_value"] for row in scoped["properties"]}
            == {"Drawing No": "configuration-only", ROUNDTRIP_NAME: "configuration value"},
            "configuration property edit leaked or failed to persist")
    aggregate = gate.command("document", "property-summary", "--name", ROUNDTRIP_NAME, document=document)
    validate_operation_result("document.property-summary", aggregate)
    matching = [row["properties"] for row in aggregate["configurations"] if row["configuration"] == configuration]
    require(matching == [[row for row in scoped["properties"] if row["name"] == ROUNDTRIP_NAME]],
            "configuration summary did not match the exact scoped read")
    return summary, scoped


def exercise_metadata(gate, document, case):
    structure = gate.command("document", "inspect", "--detail", "structure", document=document)
    configuration = structure["structure"]["configurations"]["active"]
    case["configuration"] = configuration
    original = gate.command("document", "summary", document=document)
    validate_operation_result("document.summary", original)
    gate.background(original, document)
    require(original["document"]["modified"] is False, "summary read dirtied the fixture")
    for field, value in SUMMARY_VALUES.items():
        edited = gate.write("document", "summary-set", field, value,
                            "--if-value", original["fields"][field], document=document)
        validate_operation_result("document.summary-set", edited)
        gate.background(edited, document)
        require(edited["value"] == value and edited["document"]["modified"],
                "summary write did not round-trip or mark document dirty")
    gate.write("document", "property-add", ROUNDTRIP_NAME, "original", document=document)
    updated = gate.write("document", "property-set", ROUNDTRIP_NAME, "文档值", "--if-value", "original",
                         document=document)
    validate_operation_result("document.property-set", updated)
    require(updated["property"]["raw_value"] == "文档值", "document property update was not verified")
    scoped = ("--configuration", configuration)
    gate.write("document", "property-add", ROUNDTRIP_NAME, "configuration value", *scoped, document=document)
    gate.write("document", "property-add", DELETED_NAME, "temporary", *scoped, document=document)
    removed = gate.write("document", "property-delete", DELETED_NAME, *scoped,
                         "--if-value", "temporary", document=document)
    validate_operation_result("document.property-delete", removed)
    require(removed["property"] is None and removed["changed"], "configuration property was not deleted")
    case["edited_summary"], case["edited_configuration_properties"] = check_metadata(gate, document, configuration)
    return {**EXPECTED, ROUNDTRIP_NAME: (30, "文档值")}


def run(gate, fixtures, *, host_fixtures=None, save_copy=False, edit_metadata=False):
    require(not edit_metadata or save_copy, "metadata writes require saving to a separate file")
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
        expected = exercise_metadata(gate, target, case) if edit_metadata else EXPECTED
        if edit_metadata:
            rows = verify_properties(gate.command("document", "properties", document=target), expected)
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
        require(verify_properties(reopened_read, expected) == rows, "reopened native property values changed")
        if edit_metadata:
            case["reopened_summary"], case["reopened_configuration_properties"] = check_metadata(
                gate, fresh, case["configuration"],
            )
            refused = gate.write("document", "summary-set", "author", "Read-only refusal", document=fresh,
                                 expected_error="ValueError")
            require(not refused["mutation"]["attempted"], "read-only edit reached the native setter")
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
    parser.add_argument("--edit-metadata", action="store_true", help="exercise summary and scoped property writes")
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
        run(gate, args.fixture_dir, host_fixtures=args.host_fixture_dir, save_copy=args.save_copy,
            edit_metadata=args.edit_metadata)
    except BaseException:
        gate.record["state"] = "failed"
        raise
    finally:
        gate.cleanup()
        gate.checkpoint("properties-final")
    require(not gate.record["cleanup_errors"], "property gate cleanup failed")


if __name__ == "__main__":
    main()
