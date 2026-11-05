"""Installed public CLI verification of document length display options."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath

from swcli.result_schemas import validate_operation_result

spec = importlib.util.spec_from_file_location(
    "_document_units_modeling", Path(__file__).with_name("verify-modeling.py")
)
modeling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modeling)
require = modeling.require
LENGTH_CODES = {"mm": 0, "inch": 3}


def read_units(gate, document, *, session=None):
    result = gate.command("document", "units", document=document, session=session)
    validate_operation_result("document.units", result)
    return result


def set_units(gate, document, before, *, length_unit=None, decimal_places=None):
    units = before["units"]
    stamp = before["document"]["update_stamp"]
    require(type(stamp) is int, "document units require a native update stamp")
    arguments = ["document", "units-set", "--if-update-stamp", stamp,
                 "--if-length-unit", units["length_unit"],
                 "--if-decimal-places", units["decimal_places"]]
    expected = dict(units["native_units"])
    if length_unit is not None:
        arguments.extend(["--length-unit", length_unit])
        expected["length_unit"] = LENGTH_CODES[length_unit]
    if decimal_places is not None:
        arguments.extend(["--decimal-places", decimal_places])
        expected["significant_digits"] = decimal_places
    result = gate.write(*arguments, document=document)
    validate_operation_result("document.units-set", result)
    changed = expected != units["native_units"]
    require(result["before"] == units and result["units"]["native_units"] == expected
            and result["changed"] is changed
            and result["mutation"] == {"attempted": changed, "may_have_changed": changed},
            "document unit setter did not preserve and read back its exact profile")
    gate.background(result, document)
    if changed:
        require(result["document"]["modified"] is True, "changed document units did not mark the document dirty")
    else:
        require(result["document"] == before["document"], "same-value document units changed document state")
    return result


def run(gate, fixtures, *, host_fixtures=None):
    gate.record.update(profile="document-units", state="running", success=False, unit_cases=[],
                       geometry_coverage="private calibration; not measured by this public gate")
    gate.record["host"] = gate.health()["host"]
    host = gate.record["host"]
    require(host.get("owned_by_daemon") is True and host.get("visible") is False
            and host.get("shared_interactive") is False,
            "document units require an independently owned hidden host")
    gate.require_empty()
    for suffix, kind in (("SLDPRT", 1), ("SLDASM", 2)):
        source = fixtures / ("properties." + suffix)
        require(source.is_file(), "prepared document unit fixture is missing")
        original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        source_host = str(PureWindowsPath(host_fixtures) / source.name) if host_fixtures else str(source)
        opened = gate.command("document", "open", source_host)
        document = opened["document"]["document_id"]
        require(opened["api_errors"] == opened["api_warnings"] == 0
                and opened["document"]["type"] == kind and not opened["document"]["modified"]
                and PureWindowsPath(opened["document"]["path"]) == PureWindowsPath(source_host),
                "document unit fixture did not open at its exact clean path")
        foreground = gate.create()
        case = {"format": suffix, "source_sha256": original_hash, "open": opened, "writes": []}
        gate.record["unit_cases"].append(case)
        baseline = gate.command("document", "inspect", document=document)["document"]
        gate.command("document", "lease", "acquire", "--ttl-seconds", 600, document=document)
        initial = case["initial"] = read_units(gate, document, session=gate.session + "-reader")
        gate.background(initial, document)
        native = initial["units"]["native_units"]
        require(initial["document"] == baseline, "document unit reads changed document state")
        require(native["fraction_base"] == 1
                and native["fraction_value"] in (0, 8) and native["round_to_fraction"] == 0
                and initial["units"]["length_unit"] in LENGTH_CODES
                and 0 <= initial["units"]["decimal_places"] <= 8,
                "document unit fixture has an unsupported native profile")
        case["lease_refusal"] = gate.command(
            "document", "units-set", "--length-unit", "inch", document=document,
            session=gate.session + "-contender", expected_error="DocumentLeaseConflict",
        )
        case["stamp_refusal"] = gate.write(
            "document", "units-set", "--length-unit", "inch",
            "--if-update-stamp", baseline["update_stamp"] + 1,
            document=document, expected_error="DocumentUpdateConflict",
        )
        wrong_unit = "inch" if initial["units"]["length_unit"] == "mm" else "mm"
        case["unit_value_refusal"] = gate.write(
            "document", "units-set", "--length-unit", "inch", "--if-length-unit", wrong_unit,
            document=document, expected_error="DocumentUnitsConflict",
        )
        wrong_places = (initial["units"]["decimal_places"] + 1) % 9
        case["precision_value_refusal"] = gate.write(
            "document", "units-set", "--decimal-places", 4, "--if-decimal-places", wrong_places,
            document=document, expected_error="DocumentUnitsConflict",
        )
        for key in ("unit_value_refusal", "precision_value_refusal"):
            require(case[key]["mutation"] == {"attempted": False, "may_have_changed": False},
                    "unit value conflict reached a native setter")
        after_refusals = read_units(gate, document)
        require(after_refusals["units"] == initial["units"] and after_refusals["document"] == baseline,
                "refused document unit edits changed native options or document state")
        current = initial
        for unit, places in (("inch", 0), (None, 4), ("mm", 8)):
            result = set_units(gate, document, current, length_unit=unit, decimal_places=places)
            case["writes"].append(result)
            current = result
        previous = case["writes"][-1]["before"]
        stale = case["stale_value_refusal"] = gate.write(
            "document", "units-set", "--length-unit", "inch",
            "--if-update-stamp", current["document"]["update_stamp"],
            "--if-length-unit", previous["length_unit"],
            "--if-decimal-places", previous["decimal_places"],
            document=document, expected_error="DocumentUnitsConflict",
        )
        require(stale["mutation"] == {"attempted": False, "may_have_changed": False},
                "stale document unit values reached a native setter")
        unchanged = read_units(gate, document)
        require(unchanged["units"] == current["units"] and unchanged["document"] == current["document"],
                "stale value refusal changed the document unit options")
        saved_path = gate.directory / ("saved-units." + suffix)
        saved_host = str(PureWindowsPath(gate.host_directory) / saved_path.name)
        saved = case["save_copy"] = gate.write("document", "save-as", saved_host, document=document)
        require(saved["api_saved"] is True and saved["save_errors"] == 0 and saved["save_warnings"] is None
                and not saved["document"]["modified"]
                and PureWindowsPath(saved["document"]["path"]) == PureWindowsPath(saved_host)
                and saved_path.is_file() and saved_path.stat().st_size >= 512
                and saved["artifact"]["format"] == suffix
                and PureWindowsPath(saved["artifact"]["path"]) == PureWindowsPath(saved_host)
                and saved["artifact"]["size_bytes"] == saved_path.stat().st_size,
                "unit-edited native copy did not save cleanly to its separate path")
        saved_hash = case["saved_sha256"] = hashlib.sha256(saved_path.read_bytes()).hexdigest()
        clean = read_units(gate, document)
        case["same_value"] = set_units(gate, document, clean, length_unit="mm", decimal_places=8)
        require(case["same_value"]["document"]["modified"] is False
                and hashlib.sha256(saved_path.read_bytes()).hexdigest() == saved_hash,
                "same-value unit request dirtied the saved document or changed its bytes")
        gate.close(document)
        reopened = case["reopen"] = gate.command("document", "open", saved_host, "--read-only")
        fresh = reopened["document"]["document_id"]
        require(fresh != document and reopened["read_only"] is True
                and reopened["api_errors"] == reopened["api_warnings"] == 0
                and reopened["document"]["type"] == kind and not reopened["document"]["modified"]
                and PureWindowsPath(reopened["document"]["path"]) == PureWindowsPath(saved_host),
                "saved document units did not reopen with a clean fresh read-only handle")
        observed = case["reopened_units"] = read_units(gate, fresh)
        require(observed["units"] == current["units"], "saved document length options were not preserved")
        refused = case["read_only_refusal"] = gate.write(
            "document", "units-set", "--length-unit", "inch",
            document=fresh, expected_error="ValueError",
        )
        require(refused["mutation"] == {"attempted": False, "may_have_changed": False},
                "read-only unit edit reached a native setter")
        final = read_units(gate, fresh)
        require(final["units"] == observed["units"] and final["document"] == observed["document"]
                and hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
                and hashlib.sha256(saved_path.read_bytes()).hexdigest() == saved_hash,
                "read-only document unit verification changed settings, state or file bytes")
        gate.close(fresh)
        gate.close(foreground)
        gate.require_empty(after_case="document-units-" + suffix)
        case["success"] = True
        gate.checkpoint("document-units-" + suffix + "-verified")
    gate.record["host_after"] = gate.health()["host"]
    require(gate.record["host_after"] == gate.record["host"], "document units replaced the owned host")
    gate.record.update(state="completed", success=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--fixture-dir", required=True, type=Path)
    parser.add_argument("--endpoint", default=os.environ.get("SWCLI_ENDPOINT", modeling.DEFAULT_ENDPOINT))
    parser.add_argument("--host-fixture-dir", type=modeling.host_directory)
    parser.add_argument("--host-output-dir", type=modeling.host_directory)
    parser.add_argument("--cli-command", type=modeling.executable)
    args = parser.parse_args(argv)
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    gate = modeling.ModelingSmoke(
        directory=directory, host_directory=args.host_output_dir or str(directory),
        cli=[args.cli_command] if args.cli_command else None, endpoint=args.endpoint,
    )
    gate.record_path = directory / "document-units.json"
    with gate.record_path.open("x", encoding="utf-8") as stream:
        json.dump(gate.record, stream)
    try:
        run(gate, args.fixture_dir, host_fixtures=args.host_fixture_dir)
    except BaseException as exc:
        gate.record.update(state="failed", success=False,
                           error={"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        gate.cleanup()
        if gate.record["cleanup_errors"] or gate.checkpoint_error is not None:
            gate.record.update(state="failed", success=False)
        gate.checkpoint("document-units-final")
    if gate.checkpoint_error is not None:
        raise gate.checkpoint_error
    require(not gate.record["cleanup_errors"], "document unit gate cleanup failed")


if __name__ == "__main__":
    main()
