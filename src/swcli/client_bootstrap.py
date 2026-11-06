"""Foreground daemon action for a one-shot same-user Windows startup task."""

import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--startup-timeout", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--attach-existing", action="store_true")
    parser.add_argument("--tray", choices=("auto", "on", "off"), default="auto")
    parser.add_argument("--runtime-settings")
    args = parser.parse_args()
    # The Task Scheduler action has no dependency on an inherited PYTHONPATH.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    if args.runtime_settings:
        from swcli.secure_transport import apply_runtime_environment
        apply_runtime_environment(json.loads(args.runtime_settings))
    from swcli.cli import main as cli_main
    from swcli.daemon.client import parse_endpoint
    host, port = parse_endpoint(args.endpoint)
    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    with open(args.log, "a", encoding="utf-8", buffering=1) as log:
        previous = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = log
        try:
            arguments = ["daemon", "serve", "--host", host, "--port", str(port),
                         "--startup-timeout", args.startup_timeout]
            if args.tray != "auto":
                arguments.extend(("--tray", args.tray))
            if args.visible:
                arguments.append("--visible")
            if args.attach_existing:
                arguments.append("--attach-existing")
            return cli_main(arguments)
        finally:
            sys.stdout, sys.stderr = previous



if __name__ == "__main__":
    raise SystemExit(main())
