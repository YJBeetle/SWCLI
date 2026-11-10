"""Compare metadata-only interop reflection with an existing installed typelib receipt.

No CAD object is created, connected or invoked. No typelib collection is repeated.
Windows PowerShell Desktop and the supplied installed files must already exist.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

TARGETS = {"IModelDocExtension": {"SaveAs3": 7}, "IDimension": {"SetSystemValue3": 3, "GetSystemValue3": 2}}
MAX_FILE = 256 * 1024 * 1024
MAX_JSON = 16 * 1024 * 1024
ATTRIBUTE = "System.Runtime.InteropServices."
NATIVE_TYPES = {3: "System.Int32", 5: "System.Double", 8: "System.String", 9: "System.Object", 11: "System.Boolean", 12: "System.Object"}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def fingerprint(path):
    require(path.is_absolute() and path.is_file(), "explicit existing absolute input file is required")
    require(path.stat().st_size <= MAX_FILE, "input file exceeds bound")
    return dict(path=str(path), size_bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def read_json(path):
    require(path.stat().st_size <= MAX_JSON, "JSON receipt exceeds bound")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def literal(text):
    require(isinstance(text, str) and len(text) <= 65536, "bounded literal metadata is required")
    return ast.literal_eval(text)


def native_type(value, depth=0):
    require(depth <= 8, "native type metadata exceeds depth bound")
    if type(value) is int:
        return NATIVE_TYPES.get(value)
    if type(value) in (tuple, list) and len(value) == 2 and value[0] == 26:
        child = native_type(value[1], depth + 1)
        return child + "&" if child is not None else None
    return None


def attribute_value(attributes, name):
    matches = [item for item in attributes if item.get("type") == ATTRIBUTE + name]
    require(len(matches) <= 1, "duplicate metadata attribute: " + name)
    if not matches:
        return None
    values = matches[0].get("constructor_arguments", [])
    require(len(values) >= 1, "metadata attribute has no constructor argument: " + name)
    return values[0]["value"]


def library_identity(receipt):
    # Consume the already retained primitive receipt; never evaluate its IID expression.
    value = receipt.get("library_attributes", "")
    pattern = r"\(IID\('([0-9A-Fa-f{}-]+)'\),\s*(-?\d+),\s*(-?\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)"
    match = re.fullmatch(pattern, value)
    require(match is not None, "existing typelib identity receipt has an unexpected shape")
    return dict(guid=match.group(1).strip("{}").upper(), lcid=int(match.group(2)), syskind=int(match.group(3)),
                major=int(match.group(4)), minor=int(match.group(5)))


def compare_contracts(native, managed, report):
    identity = report["typelib_identity"] = library_identity(native)
    require(identity["major"] == 33, "installed typelib must be SOLIDWORKS 2025 major 33")
    require(managed.get("success") is True and managed.get("assembly", {}).get("reflection_only") is True,
            "reflection-only metadata collection did not complete")
    checks = report.setdefault("contract_checks", [])
    def check(name, actual, expected):
        row = dict(name=name, actual=actual, expected=expected, matches=actual == expected)
        checks.append(row)
    check("assembly.typelib_guid", str(attribute_value(managed["assembly"].get("attributes", []), "GuidAttribute")).strip("{}").upper(), identity["guid"])
    check("assembly.typelib_major", attribute_value(managed["assembly"].get("attributes", []), "TypeLibVersionAttribute"), identity["major"])
    for file_key in ("interop_file", "solidworks_exe"):
        match = re.match(r"^(\d+)", managed.get(file_key, {}).get("file_version", ""))
        check(file_key + ".major", int(match.group(1)) if match is not None else None, identity["major"])
    for name, methods in TARGETS.items():
        candidates = [item for item in native.get("interfaces", []) if item.get("name") == name]
        require(len(candidates) == 1, "existing typelib interface missing or ambiguous: " + name)
        source = candidates[0]
        target = managed.get("interfaces", {}).get(name)
        require(isinstance(target, dict), "interop interface missing: " + name)
        check(name + ".interface", target.get("is_interface"), True)
        guid = attribute_value(target.get("attributes", []), "GuidAttribute")
        check(name + ".guid", str(guid).strip("{}").upper(), source["guid"].strip("{}").upper())
        for method, count in methods.items():
            definitions = [item for item in source.get("functions", []) if item.get("name") == method]
            require(len(definitions) == 1, "existing typelib method missing or ambiguous: " + method)
            definition = definitions[0]
            parameters = literal(definition["args_repr"])
            returned = literal(definition["rettype_repr"])
            observed = target.get("methods", {}).get(method)
            require(isinstance(observed, dict), "interop method missing: " + method)
            prefix = name + "." + method
            check(prefix + ".native_arity", len(parameters), count)
            check(prefix + ".managed_arity", len(observed.get("parameters", [])), count)
            check(prefix + ".dispid", attribute_value(observed.get("attributes", []), "DispIdAttribute"), definition["memid"])
            return_type = native_type(returned[0])
            require(return_type is not None, "unresolved native return type: " + prefix)
            check(prefix + ".return_type", observed.get("return_type"), return_type)
            for index, (actual, expected) in enumerate(zip(observed.get("parameters", []), parameters)):
                expected_type = native_type(expected[0])
                require(expected_type is not None, "unresolved native parameter type: " + prefix)
                check(prefix + ".parameter_type." + str(index), actual.get("type"), expected_type)
                check(prefix + ".parameter_position." + str(index), actual.get("position"), index)
    require(checks and all(row["matches"] for row in checks), "interop metadata differs from the retained typelib contract")
    report["marshaling_review_required"] = True
    report["null_marshaling_accepted"] = False
    report["native_binding_accepted"] = False


def collect(args, report, *, runner=subprocess.run):
    report["collector_script"] = fingerprint(Path(__file__).resolve())
    paths = {name: getattr(args, name) for name in ("typelib_evidence", "sldworks", "interop", "solidworks_exe", "powershell")}
    before = report["inputs"] = {}
    for name, path in paths.items():
        before[name] = fingerprint(path)
    native = report["retained_typelib_evidence"] = read_json(args.typelib_evidence)
    require(native.get("execution_kind") == "local-installed-typelib-only-zero-CAD", "explicit zero-CAD typelib receipt is required")
    require(before["sldworks"]["sha256"] == native.get("sha256"), "installed typelib bytes differ from the retained receipt")
    script = Path(__file__).with_name("inspect-installed-interop-metadata.ps1")
    report["reflection_script"] = fingerprint(script)
    reflection = args.output_dir / "reflection.json"
    command = [str(args.powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script),
               "-InteropPath", str(args.interop), "-SolidWorksExe", str(args.solidworks_exe), "-OutputPath", str(reflection)]
    report["reflection_attempted"] = True
    try:
        result = runner(command, capture_output=True, timeout=120, check=False)
    except subprocess.TimeoutExpired as error:
        (args.output_dir / "reflection.stdout.log").write_bytes(error.stdout or b"")
        (args.output_dir / "reflection.stderr.log").write_bytes(error.stderr or b"")
        report["reflection_timeout"] = True
        raise
    (args.output_dir / "reflection.stdout.log").write_bytes(result.stdout)
    (args.output_dir / "reflection.stderr.log").write_bytes(result.stderr)
    report["reflection_exit_code"] = result.returncode
    if reflection.is_file():
        report["reflection"] = read_json(reflection)
    require(result.returncode == 0, "reflection-only metadata process failed; inspect its retained first error")
    managed = report.get("reflection", {})
    require(managed.get("interop_file", {}).get("sha256") == before["interop"]["sha256"], "reflected interop bytes differ from the explicit input")
    require(managed.get("solidworks_exe", {}).get("sha256") == before["solidworks_exe"]["sha256"], "exe metadata differs from the explicit input")
    after = report["inputs_after"] = {name: fingerprint(path) for name, path in paths.items()}
    require(after == before, "inspection input changed while metadata was being collected")
    compare_contracts(native, managed, report)
    report["success"] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output-dir", "typelib-evidence", "sldworks", "interop", "solidworks-exe", "powershell"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    require(args.output_dir.is_absolute(), "output directory must be absolute")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = dict(success=False, execution_kind="installed-interop-metadata-only-zero-CAD", model_calls=0,
                  cad_object_activations=0, native_binding_accepted=False, null_marshaling_accepted=False)
    destination = args.output_dir / "report.json"
    try:
        collect(args, report)
    except Exception as error:
        report["first_error"] = dict(type=type(error).__name__, message=str(error))
        return 1
    finally:
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
