"""Read installed SW2025 typelib contracts before the existing combined full gate.

No SOLIDWORKS host is created or attached, and no model is read or written.
"""
import argparse
import hashlib
import json
from pathlib import Path

REQUIRED = {
    "IModelDocExtension": {"SaveAs3": 7},
    "IDimension": {"GetSystemValue3": 2},
    "IConfigurationManager": {"ActiveConfiguration": 0},
}
ENUMS = {"swThisConfiguration": 1, "swSpecifyConfiguration": 3}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def library_identity(library):
    attr = library.GetLibAttr()
    return dict(guid=str(attr[0]), lcid=attr[1], syskind=attr[2], major=attr[3], minor=attr[4])


def read_contracts(sldworks, swconst, com, evidence):
    for path in (sldworks, swconst):
        require(path.is_absolute() and path.is_file(), "typelib must be an existing absolute file")
    # Explicit paths prevent LoadTypeLib registration (Microsoft contract).
    library = com.LoadTypeLib(str(sldworks))
    evidence["sldworks"] = dict(path=str(sldworks), sha256=hashlib.sha256(sldworks.read_bytes()).hexdigest(),
                                library=library_identity(library), interfaces={})
    for index in range(library.GetTypeInfoCount()):
        name = library.GetDocumentation(index)[0]
        if name not in REQUIRED:
            continue
        require(name not in evidence["sldworks"]["interfaces"], "duplicate required interface")
        info = library.GetTypeInfo(index)
        attr = info.GetTypeAttr()
        require(attr.typekind in (com.TKIND_INTERFACE, com.TKIND_DISPATCH), "required name is not an interface")
        members = {}
        for offset in range(attr.cFuncs):
            names = list(info.GetNames(info.GetFuncDesc(offset)[0]))
            if names and names[0] in REQUIRED[name]:
                members.setdefault(names[0], []).append(names[1:])
        evidence["sldworks"]["interfaces"][name] = dict(iid=str(attr.iid), typekind=attr.typekind, members=members)
    for interface, wanted in REQUIRED.items():
        actual = evidence["sldworks"]["interfaces"].get(interface, {}).get("members", {})
        for member, count in wanted.items():
            require(len(actual.get(member, [])) == 1 and len(actual[member][0]) == count,
                    interface + "." + member + " has an unexpected installed parameter list")
    library = com.LoadTypeLib(str(swconst))
    evidence["swconst"] = dict(path=str(swconst), sha256=hashlib.sha256(swconst.read_bytes()).hexdigest(),
                               library=library_identity(library), constants={})
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attr = info.GetTypeAttr()
        if attr.typekind != com.TKIND_ENUM:
            continue
        for offset in range(attr.cVars):
            desc = info.GetVarDesc(offset)
            name = info.GetDocumentation(desc[0])[0]
            if name in ENUMS:
                require(name not in evidence["swconst"]["constants"], "duplicate configuration enum")
                require(type(desc.value) is int, "configuration enum is not an integer")
                evidence["swconst"]["constants"][name] = desc.value
    require(evidence["swconst"]["constants"] == ENUMS, "installed configuration enums differ from the implementation")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--sldworks", required=True, type=Path)
    parser.add_argument("--swconst", required=True, type=Path)
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = args.output_dir / "report.json"
    evidence = dict(success=False, evidence_kind="installed-typelib-readonly", model_calls=0,
                    native_binding_accepted=False)
    report.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    try:
        import pythoncom
        read_contracts(args.sldworks, args.swconst, pythoncom, evidence)
        evidence["success"] = True
    except Exception as exc:
        evidence["first_error"] = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        report.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
