"""Shared lightweight visible-host smoke; no CAD creation, export or save.

The adapter starts an exclusive visible daemon and checks process teardown.
This gate owns only its read-only document and stops the verified owned daemon.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location("visible_transport", Path(__file__).with_name("verify-modeling.py"))
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


def verify(smoke, sample):
    before = smoke.health()["host"]
    smoke.record.update(profile="visible-open", host=before)
    transport.require(before["visible"] is True and before["owned_by_daemon"] is True
                      and before["shared_interactive"] is False,
                      "visible smoke requires an exclusively owned visible host")
    smoke.require_empty()
    opened = smoke.command("document", "open", sample, "--read-only")
    document = opened["document"]["document_id"]
    transport.require(opened["read_only"] is True and opened["api_errors"] == 0
                      and opened["api_warnings"] in (0, 2) and opened["document"]["type"] == 1,
                      "visible sample open failed native read-only verification")
    observed = smoke.command("document", "inspect", document=document)["document"]
    transport.require(observed["document_id"] == document and observed["type"] == 1,
                      "visible inspection targeted a different document")
    smoke.close(document)
    smoke.require_empty()
    after = smoke.health()["host"]
    smoke.record["host_after"] = after
    transport.require(after["process_id"] == before["process_id"] and after["visible"] is True
                      and after["owned_by_daemon"] is True and after["shared_interactive"] is False,
                      "visible host changed identity, visibility or ownership")
    stopped = smoke.command("daemon", "stop")
    transport.require(stopped["result"]["stopping"] is True,
                      "visible smoke did not stop its connected daemon")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--sample-part", required=True, type=transport.host_directory)
    parser.add_argument("--endpoint", default=os.environ.get("SWCLI_ENDPOINT", transport.DEFAULT_ENDPOINT))
    parser.add_argument("--cli-command", type=transport.executable)
    parser.add_argument("--request-timeout", type=transport.request_timeout,
                        default=transport.DEFAULT_REQUEST_TIMEOUT_SECONDS,
                        help="Per-request deadline in seconds; adapters may override for slower hosts")
    args = parser.parse_args(argv)
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    smoke = transport.ModelingSmoke(directory=directory, host_directory=str(directory), endpoint=args.endpoint,
        cli=[args.cli_command] if args.cli_command else None, request_timeout_seconds=args.request_timeout)
    smoke.record_path = directory / "visible.json"
    with smoke.record_path.open("x", encoding="utf-8") as stream:
        json.dump(smoke.record, stream)
    error = None
    try:
        verify(smoke, args.sample_part)
    except Exception as exc:
        error = exc
        smoke.record["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        smoke.cleanup()
        smoke.record.update(state="completed", success=error is None and smoke.checkpoint_error is None
                            and not smoke.record["cleanup_errors"])
        smoke.checkpoint("completed")
    if error:
        raise error
    transport.require(smoke.record["success"] and smoke.checkpoint_error is None,
                      "visible smoke cleanup or evidence failed")


if __name__ == "__main__":
    main()
