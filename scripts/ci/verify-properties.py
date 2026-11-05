"""Installed public CLI reads of separately prepared native property fixtures."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

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


def run(gate, fixtures):
    gate.record.update(state="running", success=False, property_cases=[])
    gate.record["host"] = gate.health()["host"]
    gate.require_empty()
    for suffix in ("SLDPRT", "SLDASM"):
        path = fixtures / ("properties." + suffix)
        require(path.is_file(), "prepared property fixture is missing")
        before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        opened = gate.command("document", "open", str(path), "--read-only")
        require(opened["api_errors"] == opened["api_warnings"] == 0, "property fixture did not open cleanly")
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
        gate.close(target)
        reopened = case["reopen"] = gate.command("document", "open", str(path), "--read-only")
        fresh = reopened["document"]["document_id"]
        require(fresh != target and reopened["api_errors"] == reopened["api_warnings"] == 0,
                "property reopen did not acquire a clean fresh handle")
        reopened_read = case["reopened_properties"] = gate.command("document", "properties", document=fresh)
        require(verify_properties(reopened_read) == rows, "reopened native property values changed")
        require(not gate.command("document", "inspect", document=fresh)["document"]["modified"]
                and hashlib.sha256(path.read_bytes()).hexdigest() == before_hash,
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
    args = parser.parse_args(argv)
    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    gate = modeling.ModelingSmoke(
        directory=args.output_dir, host_directory=str(args.output_dir),
        endpoint=args.endpoint,
    )
    gate.record_path = args.output_dir / "properties.json"
    with gate.record_path.open("x", encoding="utf-8") as stream:
        json.dump(gate.record, stream)
    try:
        run(gate, args.fixture_dir)
    except BaseException:
        gate.record["state"] = "failed"
        raise
    finally:
        gate.cleanup()
        gate.checkpoint("properties-final")
    require(not gate.record["cleanup_errors"], "property gate cleanup failed")


if __name__ == "__main__":
    main()
