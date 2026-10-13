"""Run a functional script with explicit adapter-provided import directories.

The launcher still uses -I: neither ambient PYTHONPATH nor the working directory
is imported. Source-only deployments must explicitly supply their trusted paths.
"""
import argparse
from pathlib import Path
import runpy
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-path", action="append", type=Path, required=True)
    parser.add_argument("script", type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    for path in args.python_path:
        if not path.is_absolute() or not path.is_dir():
            parser.error("python-path must be an existing absolute directory")
    script = args.script.resolve()
    if script.parent != Path(__file__).resolve().parents[1] or not script.is_file():
        parser.error("only functional scripts in the CI directory may be launched")
    sys.path[:0] = [str(path.resolve()) for path in args.python_path]
    sys.argv = [str(script), *args.arguments]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
