"""Exercise installed dimensions and explicit center fixes on one daemon.

No COM objects are imported here. The front plane goes through the installed
CLI entry point; the other planes use its public daemon client. A remote/Wine
host can use --host-output-dir for its view of the supplied output directory.
Source-delivered Linux payloads can select their thin executable entry point
with --cli-command; the default still uses isolated installed Python.
The caller owns host startup/shutdown. Cleanup closes only documents created
by this gate and records failures instead of hiding the original error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess
import sys
import tempfile
import uuid

from swcli.daemon.client import DEFAULT_ENDPOINT, call_daemon
from swcli.result_schemas import validate_operation_result





def host_directory(value):
    windows = bool(re.match(r"^[A-Za-z]:[\\/]", value)) or value.startswith("\\\\")
    path = PureWindowsPath(value) if windows else PurePosixPath(value)
    if "\0" in value or not path.is_absolute() or (windows and not path.root):
        raise argparse.ArgumentTypeError(
            "host-output-dir must be an absolute daemon-visible path"
        )
    return value


def cli_executable(value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise argparse.ArgumentTypeError(
            "cli-command must be one absolute executable path"
        )
    try:
        resolved = path.resolve(strict=True)
    except (OSError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"cli-command does not exist: {path}") from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise argparse.ArgumentTypeError(
            "cli-command must be an executable file, not a directory or command line"
        )
    return str(resolved)


def request_timeout(value):
    if isinstance(value, bool):
        raise argparse.ArgumentTypeError("request-timeout must be a number, not bool")
    try:
        seconds = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise argparse.ArgumentTypeError("request-timeout must be a number") from exc
    if not math.isfinite(seconds) or not 0 < seconds <= MAX_REQUEST_TIMEOUT_SECONDS:
        raise argparse.ArgumentTypeError(
            f"request-timeout must be finite and greater than 0, at most {MAX_REQUEST_TIMEOUT_SECONDS} seconds"
        )
    return seconds


class EvidenceCheckpoint:
    """Reserve one run's evidence, then replace it with complete JSON snapshots."""

    def __init__(self, path):
        self.path = path
        self.mode = None

    @staticmethod
    def serialize(record):
        return json.dumps(record, ensure_ascii=False, allow_nan=False, indent=2) + "\n"

    def reserve(self, record):
        # Refuse existing evidence before any daemon call. Serialize first so
        # invalid JSON data cannot leave an empty newly reserved record.
        payload = self.serialize(record)
        with self.path.open("x", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
        self.mode = self.path.stat().st_mode & 0o777

    def write(self, record):
        payload = self.serialize(record)
        temporary = None
        try:
            # A killed process can leave this scratch file, but readers retain
            # the previous complete JSON until the same-directory replacement.
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".driving-dimensions.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
            # NamedTemporaryFile defaults to 0600. Preserve the reserved
            # record's mode so a host runner can still collect container JSON.
            temporary.chmod(self.mode)
            temporary.replace(self.path)
        except BaseException:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as exc:
                    print(
                        f"Driving-dimension checkpoint scratch cleanup failed: {temporary}: {exc}",
                        file=sys.stderr,
                        flush=True,
                    )
            raise


def modeling_host(path):
    record = json.loads(path.read_text(encoding="utf-8"))
    require(
        record.get("state") == "completed"
        and record.get("success") is True
        and record.get("cleanup_errors") == []
        and record.get("cases", [])[-1:] == ["rejected-cut-then-sketch"],
        "predecessor modeling gate did not complete successfully",
    )
    pid = record.get("host", {}).get("process_id")
    require(
        type(pid) is int and record.get("host_after", {}).get("process_id") == pid,
        "predecessor modeling gate has no unchanged native host PID",
    )
    return pid



# Entry points are also loaded directly by unit tests, outside the script directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_support.driving_checks import (
    host_path,
    LEASE_TTL_SECONDS, DEFAULT_REQUEST_TIMEOUT_SECONDS, MAX_REQUEST_TIMEOUT_SECONDS, CLI_TIMEOUT_GRACE_SECONDS, ORIGIN_FIXTURE, ORIGIN_FIXTURE_SHA256, require, close_enough, assert_dimension, assert_circle, assert_measurement, assert_fixed_center, assert_linear_dimension, assert_discovered_diameter
)
from gate_support.driving_diameter import DiameterCases
from gate_support.driving_rectangle import RectangleCases
from gate_support.driving_center import CenterCases
from gate_support.driving_geometry import GeometryCases

class DrivingSmoke(DiameterCases, RectangleCases, CenterCases, GeometryCases):
    def __init__(
        self, *, endpoint, session, output_directory, cli=None, after_modeling=None,
        local_output_directory=None,
        request_timeout_seconds=DEFAULT_REQUEST_TIMEOUT_SECONDS,
        suite="full",
    ):
        require(suite in ("core", "full"), "unknown driving suite")
        self.suite = suite
        self.endpoint = endpoint
        self.session = session
        self.output_directory = output_directory
        self.local_output_directory = Path(local_output_directory or output_directory)
        # Use the same installed package as this isolated script, even if the
        # caller's shell still has PYTHONPATH pointing at a development tree.
        self.cli = cli or [sys.executable, "-I", "-m", "swcli"]
        self.request_timeout_seconds = request_timeout(request_timeout_seconds)
        self.after_modeling = after_modeling
        self.record = {
            "suite": suite,
            "state": "running",
            "stage": "initializing",
            "session_id": session,
            "endpoint": endpoint,
            "request_timeout_seconds": self.request_timeout_seconds,
            "cli_process_timeout_seconds": (
                self.request_timeout_seconds + CLI_TIMEOUT_GRACE_SECONDS
            ),
            "planes": [],
            "events": [],
            "case_cleanup": [],
        }
        self.owned = {}
        self.checkpoint_writer = None
        self.checkpoint_error = None
        self._cleaning_up = False

    def prepare_origin_fixture(self):
        # All host wrappers already share the physical output directory with
        # the daemon. Copy an immutable native fixture, never infer constraints
        # from coordinates or send a raw COM fixture-building escape hatch.
        source = Path(__file__).resolve().parent / "fixtures" / ORIGIN_FIXTURE
        contents = source.read_bytes()
        require(hashlib.sha256(contents).hexdigest() == ORIGIN_FIXTURE_SHA256,
                "origin fixture checksum mismatch")
        destination = self.local_output_directory / ORIGIN_FIXTURE
        with destination.open("xb") as stream:
            stream.write(contents)
        self.origin_path = host_path(self.output_directory, ORIGIN_FIXTURE)
        self.record["origin_fixture"] = {"sha256": ORIGIN_FIXTURE_SHA256,
                                         "host_path": self.origin_path}

    def checkpoint(self, stage, *, required=True):
        self.record["stage"] = stage
        if self.checkpoint_writer is None:
            return None
        try:
            self.checkpoint_writer(self.record)
        except Exception as exc:
            if self.checkpoint_error is None:
                self.checkpoint_error = exc
            self.record.setdefault("checkpoint_errors", []).append(
                {"stage": stage, "type": type(exc).__name__, "message": str(exc)}
            )
            print(
                f"Driving-dimension evidence checkpoint failed at {stage}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            if required and not self._cleaning_up:
                raise
            return exc
        return None

    def remember_owned_result(self, operation, result, context):
        # Register native resources before checkpoint I/O can fail. Otherwise
        # a successful create/open/lease response could become an orphan when
        # its evidence write aborts the gate.
        document_id = context.get("document_id")
        if operation in ("document.create", "document.open"):
            document_id = result["document"]["document_id"]
            self.owned[document_id] = {
                "session_id": context["session_id"],
                "lease_id": None,
            }
        elif operation == "document.lease.acquire" and document_id in self.owned:
            self.owned[document_id]["lease_id"] = result["lease"]["lease_id"]
        elif operation == "document.close":
            self.owned.pop(document_id, None)

    def call(self, operation, parameters=None, *, expected_error=None, **context):
        context.setdefault("session_id", self.session)
        event = {
            "transport": "protocol",
            "operation": operation,
            "parameters": dict(parameters or {}),
            "context": dict(context),
            "state": "running",
        }
        if expected_error is not None:
            event["expected_error"] = expected_error
        self.record["events"].append(event)
        try:
            self.checkpoint(f"{operation}.started")
            response = call_daemon(
                operation,
                parameters,
                endpoint=self.endpoint,
                timeout_seconds=self.request_timeout_seconds,
                **context,
            )
            event["response"] = response
            if expected_error is not None:
                require(
                    not response.get("success")
                    and response.get("error", {}).get("code") == expected_error,
                    f"{operation} did not reject with {expected_error}: {response}",
                )
                result = response
            else:
                require(response.get("success"), f"{operation} failed: {response}")
                result = response["result"]
                require(
                    result.get("ok", True),
                    f"{operation} returned a failed result: {result}",
                )
                self.remember_owned_result(operation, result, context)
        except Exception as exc:
            event["state"] = "failed"
            event["error"] = {"type": type(exc).__name__, "message": str(exc)}
            self.checkpoint(f"{operation}.failed", required=False)
            raise
        event["state"] = "completed"
        self.checkpoint(f"{operation}.completed")
        return result

    def command(self, arguments):
        command = [
            *self.cli,
            "--endpoint",
            self.endpoint,
            "--session",
            self.session,
            "--request-timeout",
            str(self.request_timeout_seconds),
            *arguments,
            "--json",
        ]
        environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        event = {
            "transport": "cli",
            "arguments": list(arguments),
            "state": "running",
        }
        self.record["events"].append(event)
        try:
            self.checkpoint("cli.started")
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.request_timeout_seconds + CLI_TIMEOUT_GRACE_SECONDS,
                env=environment,
            )
            event.update(
                returncode=completed.returncode,
                stdout=completed.stdout.decode("utf-8-sig"),
                stderr=completed.stderr.decode("utf-8", errors="replace"),
            )
            require(completed.returncode == 0, f"installed CLI failed: {event}")
            result = json.loads(event["stdout"])
            require(
                result.get("ok"), f"installed CLI returned a failed result: {result}"
            )
            event["result"] = result
        except Exception as exc:
            event["state"] = "failed"
            event["error"] = {"type": type(exc).__name__, "message": str(exc)}
            self.checkpoint("cli.failed", required=False)
            raise
        event["state"] = "completed"
        self.checkpoint("cli.completed")
        # CLI flattens response metadata into its presentation payload; the
        # operation-result schema describes only the daemon's business result.
        # Retain the full payload in evidence, stripping only these known keys
        # from the assertion view (not arbitrary unexpected properties).
        return {
            key: value for key, value in result.items()
            if key not in ("request_id", "replayed")
        }

    def create(self, *, session_id=None):
        result = self.call(
            "document.create", {"type": "part"}, session_id=session_id or self.session
        )
        return result["document"]["document_id"]

    def renew_lease(self, document_id):
        owner = self.owned[document_id]
        if owner["lease_id"] is not None:
            self.call(
                "document.lease.renew",
                {"ttl_seconds": LEASE_TTL_SECONDS},
                session_id=owner["session_id"],
                lease_id=owner["lease_id"],
            )

    def write(self, operation, parameters=None, **context):
        self.renew_lease(context["document_id"])
        return self.call(operation, parameters, **context)

    def write_command(self, arguments, *, document_id):
        self.renew_lease(document_id)
        return self.command(arguments)

    def stamp(self, document_id):
        result = self.call("document.inspect", document_id=document_id)
        stamp = result["document"]["update_stamp"]
        require(
            isinstance(stamp, int) and not isinstance(stamp, bool),
            "native update stamp unavailable",
        )
        return stamp

    def assert_background(self, document_id, foreground_id):
        result = self.call("document.list")
        require(
            result["current_document_id"] == foreground_id,
            "operation changed session current",
        )
        documents = {item["document_id"]: item for item in result["documents"]}
        require(
            documents[foreground_id]["active"]
            and documents[foreground_id]["current"]
            and not documents[document_id]["active"]
            and not documents[document_id]["current"],
            "operation did not restore the exact foreground document",
        )

    def selection_state(self, *, session_id):
        result = self.call("document.list", session_id=session_id)
        active_ids = sorted(
            item["document_id"] for item in result["documents"] if item["active"]
        )
        require(
            len(active_ids) == 1,
            "discovery gate requires one exact foreground document",
        )
        return {
            "current_document_id": result["current_document_id"],
            "active_document_id": active_ids[0],
        }

    def close(self, document_id):
        owner = self.owned[document_id]
        self.renew_lease(document_id)
        self.call("document.close", {"discard": True}, document_id=document_id, **owner)

    def cleanup(self):
        errors = []
        self.record["cleanup_errors"] = errors
        self._cleaning_up = True
        try:
            self.checkpoint("cleanup.started", required=False)
            for document_id in reversed(tuple(self.owned)):
                try:
                    self.close(document_id)
                except Exception as exc:
                    errors.append({"document_id": document_id, "message": str(exc)})
                self.checkpoint("cleanup.document.completed", required=False)
        finally:
            self._cleaning_up = False
        self.checkpoint("cleanup.completed", required=False)
        return errors

    def require_empty(self, after_case):
        result = self.call("document.list")
        documents = result["documents"]
        self.record["case_cleanup"].append({
            "case": after_case, "open_document_count": len(documents),
            "empty": documents == [],
            "remaining_document_ids": [doc["document_id"] for doc in documents],
        })
        require(documents == [], f"native open documents remain after {after_case}")

    def run(self):
        predecessor_pid = (
            modeling_host(self.after_modeling) if self.after_modeling else None
        )
        if self.after_modeling:
            predecessor = json.loads(self.after_modeling.read_text())
            require(predecessor.get("suite", "full") == self.suite,
                    "modeling and driving suite coverage must match")
        health = self.call("daemon.health")
        require(
            health["host_connected"], "driving gate needs an already connected host"
        )
        self.record["host"] = health["host"]
        if self.after_modeling is not None:
            require(
                health["host"]["process_id"] == predecessor_pid,
                "SOLIDWORKS was replaced between modeling and driving gates",
            )
            self.record["modeling_record"] = str(self.after_modeling)
        for operation in (
            "sketch.fix-center",
            "sketch.dimension-diameter",
            "sketch.dimension-rectangle",
            "dimension.discover-diameter",
            "dimension.discover-rectangle",
            "dimension.inspect",
            "dimension.set",
            "sketch.list",
        ):
            require(
                operation in health["operations"], f"installed daemon lacks {operation}"
            )
        self.checkpoint("host.verified")
        self.prepare_origin_fixture()
        for plane in ("front", "top", "right"):
            self.record["current_plane"] = plane
            self.checkpoint(f"plane.{plane}.starting")
            print(f"Driving-dimension gate: {plane} starting", flush=True)
            cases = (("diameter", self.plane), ("center", self.center_constraints),
                     ("rectangle", self.rectangle_dimensions))
            if self.suite == "core" and plane != "front":
                cases = (("geometry", self.plane_geometry),)
            for name, function in cases:
                function(plane)
                case = f"plane.{plane}.{name}"
                self.checkpoint(case + ".cleanup-check")
                print(f"Driving-dimension gate: {case}.cleanup-check", flush=True)
                self.require_empty(case)
            self.checkpoint(f"plane.{plane}.completed")
            print(f"Driving-dimension gate: {plane} passed", flush=True)
        after = self.call("daemon.health")
        self.record["host_after"] = after["host"]
        require(
            after["host_connected"]
            and after["host"]["process_id"] == health["host"]["process_id"],
            "SOLIDWORKS disconnected or was replaced during the driving gate",
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("core", "full"), default="full",
                        help="core: shared guards on front plus three-plane geometry; full: all combinations")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--after-modeling",
        type=Path,
        help="require a successful modeling.json from the same connected host",
    )
    parser.add_argument(
        "--host-output-dir",
        type=host_directory,
        help="daemon-visible path for native artifacts; default: local output-dir",
    )
    parser.add_argument(
        "--cli-command",
        type=cli_executable,
        help="one absolute local executable path, e.g. /usr/local/bin/sw-cli; default: isolated installed Python",
    )
    parser.add_argument(
        "--endpoint", default=os.environ.get("SWCLI_ENDPOINT", DEFAULT_ENDPOINT)
    )
    parser.add_argument(
        "--request-timeout", type=request_timeout,
        default=DEFAULT_REQUEST_TIMEOUT_SECONDS,
        help="per-request timeout in seconds (0 < seconds <= 3600; default: 120); CLI process gets 15 extra seconds",
    )
    arguments = parser.parse_args(argv)
    directory = arguments.output_dir.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    record_path = directory / "driving-dimensions.json"
    smoke = DrivingSmoke(
        endpoint=arguments.endpoint,
        session="driving-smoke-" + uuid.uuid4().hex[:12],
        output_directory=arguments.host_output_dir or str(directory),
        cli=[arguments.cli_command] if arguments.cli_command else None,
        after_modeling=arguments.after_modeling,
        local_output_directory=directory,
        request_timeout_seconds=arguments.request_timeout,
        suite=arguments.suite,
    )
    checkpoint = EvidenceCheckpoint(record_path)
    checkpoint.reserve(smoke.record)
    smoke.checkpoint_writer = checkpoint.write
    error = None
    try:
        smoke.run()
    except Exception as exc:
        error = exc
        smoke.record["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        cleanup_errors = smoke.cleanup()
        if error is None and smoke.checkpoint_error is not None:
            error = smoke.checkpoint_error
            smoke.record["error"] = {
                "type": type(error).__name__,
                "message": str(error),
            }
        smoke.record["state"] = "completed"
        smoke.record["success"] = error is None and not cleanup_errors
        final_write_error = smoke.checkpoint("completed", required=False)
        if final_write_error is not None and error is None:
            error = final_write_error
            smoke.record["success"] = False
            smoke.record["error"] = {
                "type": type(error).__name__,
                "message": str(error),
            }
    if error is not None:
        raise error
    require(not cleanup_errors, f"driving gate cleanup failed: {cleanup_errors}")
    print(
        f"Driving diameter/rectangle dimensions and center fixes verified on front/top/right; record: {record_path}"
    )


if __name__ == "__main__":
    main()
