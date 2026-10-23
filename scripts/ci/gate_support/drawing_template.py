"""Host fixture discovery, never a fallback to an arbitrary drawing template."""
import argparse
import os
from pathlib import Path


def drawing_template(program_data, explicit=None):
    if explicit:
        result = Path(explicit)
        if not result.is_file() or result.is_symlink() or result.suffix.lower() != ".drwdot":
            raise RuntimeError("Explicit drawing template is not a regular DRWDOT file: " + str(result))
        return result.resolve()
    root = Path(program_data) / "SOLIDWORKS"
    available = sorted((p for p in root.rglob("*") if p.is_file()
                        and not p.is_symlink() and p.suffix.lower() == ".drwdot"), key=str)
    matches = [p for p in available if p.name.lower() == "gb_a4.drwdot"
               and p.parent.name.lower() == "templates"]
    if len(matches) != 1:
        raise RuntimeError("Expected one installed templates/gb_a4.drwdot; set SWCLI_DRAWING_TEMPLATE explicitly. "
                           "Available DRWDOT fixtures: " + ", ".join(map(str, available[:20])))
    return matches[0].resolve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program-data", required=True)
    args = parser.parse_args()
    print(drawing_template(args.program_data, os.environ.get("SWCLI_DRAWING_TEMPLATE")))
