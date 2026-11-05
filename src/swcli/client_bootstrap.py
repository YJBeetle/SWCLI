"""Foreground daemon action for a one-shot same-user Windows startup task."""

import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--startup-timeout", required=True)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()
    # The Task Scheduler action has no dependency on an inherited PYTHONPATH.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from swcli.cli import main as cli_main
    from swcli.daemon.client import parse_endpoint
    host, port = parse_endpoint(args.endpoint)
    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    with open(args.log, "a", encoding="utf-8", buffering=1) as log:
        previous = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = log
        try:
            return cli_main(["daemon", "serve", "--host", host, "--port", str(port),
                             "--startup-timeout", args.startup_timeout])
        finally:
            sys.stdout, sys.stderr = previous



if __name__ == "__main__":
    raise SystemExit(main())
