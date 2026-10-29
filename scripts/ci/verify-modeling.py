"""Shared real SOLIDWORKS modeling gate for Windows, Linux/Wine and macOS/Wine.

The caller installs and starts the host. This script uses only the public CLI,
never imports COM, restarts a host or changes installed samples. Local evidence
and daemon-visible artifact paths are explicit, separate namespaces. A native
cut rejection must be followed by successful background sketch creation in the
same host; a disconnected or replaced host is a failure, not a retry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import subprocess
import sys
import tempfile
import uuid

from swcli.daemon.client import DEFAULT_ENDPOINT
from swcli.hosts.export_validation import export_file_valid
from swcli.result_schemas import validate_operation_result




def executable(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
        raise argparse.ArgumentTypeError(
            "cli-command must be one absolute executable path"
        )
    return str(path.resolve())


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



# Entry points are also loaded directly by unit tests, outside the script directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_support.model_checks import (
    host_directory,
    LEASE_TTL_SECONDS, DEFAULT_REQUEST_TIMEOUT_SECONDS, DEFAULT_DEPTH_REQUEST_TIMEOUT_SECONDS, MAX_REQUEST_TIMEOUT_SECONDS, CLI_TIMEOUT_GRACE_SECONDS, require, near, unchanged_depth_metrics, verify_fixture_edges
)
from gate_support.model_native import NativeModelCases
from gate_support.model_through_all import ThroughAllCases
from gate_support.model_polygons import PolygonCases
from gate_support.model_depth import FeatureDepthCases
from gate_support.model_files import NativeFileCases

class ModelingSmoke(PolygonCases, ThroughAllCases, NativeModelCases, FeatureDepthCases, NativeFileCases):
    def __init__(
        self,
        *,
        directory,
        host_directory,
        endpoint,
        cli=None,
        request_timeout_seconds=DEFAULT_REQUEST_TIMEOUT_SECONDS,
        depth_request_timeout_seconds=DEFAULT_DEPTH_REQUEST_TIMEOUT_SECONDS,
        suite="full",
        case_set="all",
    ):
        self.directory = directory
        require(suite in ("core", "full"), "unknown modeling suite")
        self.suite = suite
        require(case_set in ("all", "native", "assembly", "exports", "reverse-cut", "through-all", "depth",
                             "drawing-save", "drawing-save-as", "drawing-copy-first", "drawing-copy-reopen", "drawing-reopen-no-inspect", "continuation"), "unknown modeling case set")
        self.case_set = case_set
        self.host_directory = host_directory
        self.endpoint = endpoint
        self.cli = cli or [sys.executable, "-I", "-m", "swcli"]
        self.request_timeout_seconds = request_timeout(request_timeout_seconds)
        self.depth_request_timeout_seconds = request_timeout(
            depth_request_timeout_seconds
        )
        self.session = "modeling-smoke-" + uuid.uuid4().hex[:12]
        self.owned = {}
        self.leases = {}
        self.cleaning_up = False
        self.checkpoint_error = None
        self.record_path = directory / "modeling.json"
        self.record = {
            "state": "running",
            "stage": "initializing",
            "success": False,
            "suite": suite,
            "session_id": self.session,
            "endpoint": endpoint,
            "request_timeout_seconds": self.request_timeout_seconds,
            "depth_request_timeout_seconds": self.depth_request_timeout_seconds,
            "cli_process_timeout_seconds": (
                self.request_timeout_seconds + CLI_TIMEOUT_GRACE_SECONDS
            ),
            "events": [],
            "cases": [],
            "case_cleanup": [],
            "cleanup_errors": [],
        }
        if case_set in ("drawing-copy-first", "drawing-copy-reopen", "drawing-reopen-no-inspect"):
            self.record.update(diagnostic_case=case_set, full_acceptance_eligible=False)

    def checkpoint(self, stage):
        try:
            self.write_checkpoint(stage)
        except Exception as exc:
            self.checkpoint_error = self.checkpoint_error or exc
            print(
                f"Modeling checkpoint failed at {stage}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            if not self.cleaning_up:
                raise

    def write_checkpoint(self, stage):
        self.record["stage"] = stage
        payload = (
            json.dumps(self.record, ensure_ascii=False, allow_nan=False, indent=2)
            + "\n"
        )
        scratch = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.directory,
                prefix=".modeling.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                scratch = Path(stream.name)
                stream.write(payload)
                stream.flush()
            scratch.chmod(self.record_path.stat().st_mode & 0o777)
            scratch.replace(self.record_path)
        finally:
            if scratch is not None and scratch.exists():
                scratch.unlink()

    def command(
        self,
        *arguments,
        document=None,
        session=None,
        lease=None,
        expected_error=None,
        allowed_error=None,
        timeout_seconds=None,
    ):
        session = session or self.session
        seconds = (
            self.request_timeout_seconds
            if timeout_seconds is None
            else request_timeout(timeout_seconds)
        )
        command = [
            *self.cli,
            "--endpoint",
            self.endpoint,
            "--session",
            session,
            "--request-timeout",
            str(seconds),
            *map(str, arguments),
        ]
        if document is not None:
            command.extend(["--document", document])
        if lease is not None:
            command.extend(["--lease", lease])
        command.append("--json")
        event = {
            "command": command,
            "state": "running",
            "request_timeout_seconds": seconds,
        }
        self.record["events"].append(event)
        stage = ".".join(map(str, arguments[:2]))
        print(f"Modeling gate: {stage}", flush=True)
        self.checkpoint(stage + ".started")
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=seconds + CLI_TIMEOUT_GRACE_SECONDS,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            event.update(
                returncode=completed.returncode,
                stdout=completed.stdout.decode("utf-8-sig"),
                stderr=completed.stderr.decode("utf-8", errors="replace"),
            )
            result = json.loads(event["stdout"])
            event["result"] = result
            if expected_error is not None:
                require(
                    completed.returncode != 0
                    and result.get("ok") is False
                    and result.get("error", {}).get("type") == expected_error,
                    f"{stage} did not reject with {expected_error}: {event}",
                )
            elif (allowed_error is not None and completed.returncode != 0
                  and isinstance(result, dict) and result.get("ok") is False
                  and result.get("error", {}).get("type") == allowed_error):
                # A fixture preparation exception, not a successful operation.
                # The caller must validate its native save and artifact evidence.
                pass
            else:
                require(
                    completed.returncode == 0
                    and isinstance(result, dict)
                    and (
                        result.get("ok") is True
                        or result.get("success") is True
                        or (
                            arguments in (("capabilities",), ("capabilities", "--full"))
                            and result.get("host_connected") is True
                        )
                    ),
                    f"{stage} failed: {event}",
                )
                # Track owned native resources before checkpoint I/O can fail.
                if arguments[:2] in (("document", "create"), ("document", "open")):
                    self.owned[result["document"]["document_id"]] = session
                elif arguments[:2] == ("document", "close"):
                    self.owned.pop(document, None)
                    self.leases.pop(document, None)
                elif arguments[:3] == ("document", "lease", "acquire"):
                    self.leases[document] = result["lease"]["lease_id"]
                elif arguments[:3] == ("document", "lease", "release"):
                    self.leases = {
                        key: value
                        for key, value in self.leases.items()
                        if value != arguments[3]
                    }
        except Exception as exc:
            event["state"] = "failed"
            event["error"] = {"type": type(exc).__name__, "message": str(exc)}
            if isinstance(exc, subprocess.TimeoutExpired):
                event["stdout"] = (exc.stdout or b"").decode("utf-8", errors="replace")
                event["stderr"] = (exc.stderr or b"").decode("utf-8", errors="replace")
            raise
        finally:
            # Keep the original native/transport error if recording also fails.
            if event["state"] == "failed":
                try:
                    self.checkpoint(stage + ".failed")
                except Exception as exc:
                    print(
                        f"Failure checkpoint could not be written: {exc}",
                        file=sys.stderr,
                    )
        event["state"] = "completed"
        self.checkpoint(stage + ".completed")
        # Keep the full CLI presentation in evidence. Result schemas describe
        # the daemon business result, not the CLI's two envelope metadata keys.
        # Do not strip any other property: unknown result fields must still fail.
        return {
            key: value for key, value in result.items()
            if key not in ("request_id", "replayed")
        }

    def renew(self, document):
        lease = self.leases.get(document)
        if lease:
            self.command(
                "document",
                "lease",
                "renew",
                lease,
                "--ttl-seconds",
                LEASE_TTL_SECONDS,
                session=self.owned[document],
            )
        return lease

    def write(self, *arguments, document, expected_error=None, allowed_error=None,
              timeout_seconds=None):
        return self.command(
            *arguments,
            document=document,
            lease=self.renew(document),
            expected_error=expected_error,
            allowed_error=allowed_error,
            timeout_seconds=timeout_seconds,
        )

    def create(self):
        result = self.command("document", "create", "--type", "part")
        descriptor = result["document"]
        require(
            result["created"] is True
            and descriptor["path"] == ""
            and descriptor["type"] == 1,
            "create did not return an unsaved native part",
        )
        return descriptor["document_id"]

    def close(self, document):
        lease = self.renew(document)
        return self.command(
            "document",
            "close",
            "--discard",
            document=document,
            session=self.owned[document],
            lease=lease,
        )

    def background(self, result, document):
        descriptor = result["document"]
        require(
            descriptor["document_id"] == document
            and descriptor["active"] is False
            and descriptor["current"] is False,
            "background operation changed exact document identity or foreground/current",
        )

    def rectangle(self, document, plane="front", width=40, height=30, x=0, y=0):
        result = self.write(
            "sketch",
            "rectangle",
            "--plane",
            plane,
            "--width-mm",
            width,
            "--height-mm",
            height,
            "--center-x-mm",
            x,
            "--center-y-mm",
            y,
            document=document,
        )
        require(
            result["editing"] is False
            and result["plane"] == plane
            and result["coordinate_system"] == "sketch-local"
            and result["geometry_verification"]["passed"] is True
            and result["geometry_verification"]["profile_segment_count"] == 4
            and re.fullmatch(r"s-[a-z0-9]{6}", result["sketch"]["sketch_id"]),
            "rectangle failed native geometry/closed-edit/handle checks",
        )
        return result

    def circle(self, document, plane="front", radius=2, x=0, y=0):
        result = self.write(
            "sketch",
            "circle",
            "--plane",
            plane,
            "--radius-mm",
            radius,
            "--center-x-mm",
            x,
            "--center-y-mm",
            y,
            document=document,
        )
        geometry = result["geometry_verification"]
        require(
            result["editing"] is False
            and geometry["passed"] is True
            and geometry["complete_circle"] is True
            and geometry["profile_segment_count"] == 1,
            "circle failed native geometry or closed-edit checks",
        )
        near(geometry["actual_radius_mm"], radius, "circle radius changed")
        for axis, expected in (("x", x), ("y", y), ("z", 0)):
            near(
                geometry["actual_center_mm"][axis],
                expected,
                "circle local center changed",
            )
        return result

    def feature(
        self, document, profile, *, cut=False, depth=10, reverse=False, merge=True
    ):
        arguments = [
            "feature",
            "cut-extrude" if cut else "extrude",
            profile,
            "--depth-mm",
            depth,
        ]
        if reverse:
            arguments.append("--reverse")
        if not cut and not merge:
            arguments.append("--no-merge")
        result = self.write(*arguments, document=document)
        require(
            re.fullmatch(r"f-[a-z0-9]{6}", result["feature"]["feature_id"]),
            "native creation did not return an exact feature handle",
        )
        geometry = result["geometry_verification"]
        require(
            geometry["passed"] is True and geometry["actual_reverse"] is reverse,
            "feature native definition/direction verification failed",
        )
        if not cut:
            near(geometry["actual_depth_mm"], depth, "native extrusion depth changed")
            require(
                geometry["actual_merge"] is merge and result["bodies"]["count"] > 0,
                "native extrusion merge/body verification failed",
            )
        return result

    def measure(self, document, *, volume=None, area=None):
        result = self.command("document", "measure", document=document)
        if volume is not None:
            near(
                result["metrics"]["volume_mm3"],
                volume,
                "native volume changed",
                abs(volume) * 1e-9 + 0.00001,
            )
        if area is not None:
            near(
                result["metrics"]["surface_area_mm2"],
                area,
                "native surface area changed",
                abs(area) * 1e-9 + 0.00001,
            )
        return result

    def require_empty(self, *, after_case=None):
        result = self.command("document", "list")
        empty = result["count"] == 0 and result["documents"] == []
        if after_case is not None:
            self.record["case_cleanup"].append({
                "case": after_case,
                "open_document_count": result["count"],
                "empty": empty,
                "remaining_document_ids": [doc["document_id"] for doc in result["documents"]],
            })
        require(
            empty,
            "native open documents remain; the gate requires an isolated empty host"
            + (f" after {after_case}" if after_case is not None else ""),
        )

    def health(self):
        status = self.command("daemon", "status")["result"]
        require(
            status["host_connected"] is True and status["recovery_required"] is False,
            "modeling gate needs an already connected, unreplaced host",
        )
        require(
            type(status["host"]["process_id"]) is int, "native host PID unavailable"
        )
        return status

    def run(self, *, sample_part=None, sample_assembly=None,
            verify_sample_assembly_save=False,
            sample_drawing=None, sample_drawing_local=None,
            drawing_work_dir=None, host_drawing_work_dir=None):
        self.record["host"] = self.health()["host"]
        self.command(
            "capabilities", "--full"
        )  # The client validates the real capabilities Schema.
        self.require_empty()
        cases = [
            ("native-model", self.native_model),
            ("generated-assembly", self.generated_assembly),
            ("reverse-cut", self.reverse_cut),
            ("feature-depth", self.feature_depth),
        ]
        if self.suite == "core":
            cases = cases[:2]
        else:
            cases.insert(1, ("polygon-model", self.polygon_model))
        # Extend the existing reverse-cut full set; both cut contracts share
        # one host/receipt, with no extra restart or diagnostic-only shortcut.
        if self.case_set in ("reverse-cut", "through-all") and self.suite == "full":
            cases.append(("through-all-cut", self.through_all_cut))
        if sample_part:
            cases.append(
                (
                    "sample-exports",
                    lambda: self.sample_exports(sample_part, sample_assembly),
                )
            )
        if sample_drawing:
            cases.append(("drawing-save-reopen", lambda: self.drawing_save_reopen(
                sample_drawing, sample_drawing_local, work_directory=drawing_work_dir,
                host_work_directory=host_drawing_work_dir)))
            cases.append(("drawing-save-as-reopen", lambda: self.drawing_save_reopen(
                sample_drawing, sample_drawing_local, work_directory=drawing_work_dir,
                host_work_directory=host_drawing_work_dir, save_as=True)))
            if self.case_set in ("drawing-copy-first", "drawing-copy-reopen", "drawing-reopen-no-inspect"):
                probe_options = {"reopen": self.case_set != "drawing-copy-first"}
                if self.case_set == "drawing-reopen-no-inspect":
                    probe_options["inspect_structure"] = False
                cases.append((self.case_set, lambda: self.drawing_copy_first(
                    sample_drawing_local, work_directory=drawing_work_dir,
                    host_work_directory=host_drawing_work_dir,
                    **probe_options)))
        if verify_sample_assembly_save:
            cases.append(("official-assembly-save-reopen",
                          lambda: self.assembly_save_reopen(sample_assembly)))
        cases.append(("rejected-cut-then-sketch", self.rejected_cut_then_sketch))
        selection = getattr(self, "case_set", "all")
        if selection != "all":
            names = {"native": {"native-model", "polygon-model"},
                     "assembly": {"generated-assembly", "official-assembly-save-reopen"},
                     "exports": {"sample-exports"}, "reverse-cut": {"reverse-cut", "through-all-cut"},
                     "through-all": {"through-all-cut"},
                     "depth": {"feature-depth"}, "drawing-save": {"drawing-save-reopen"},
                     "drawing-save-as": {"drawing-save-as-reopen"},
                     "drawing-copy-first": {"drawing-copy-first"},
                     "drawing-copy-reopen": {"drawing-copy-reopen"},
                     "drawing-reopen-no-inspect": {"drawing-reopen-no-inspect"},
                     "continuation": {"rejected-cut-then-sketch"}}[selection]
            cases = [(name, function) for name, function in cases if name in names]
            require(cases, "selected modeling case set is unavailable for this suite/fixtures")
            self.record["case_set"] = selection
        for name, function in cases:
            self.checkpoint(name + ".starting")
            function()
            # CloseDoc can return without unloading every referenced document.
            # Confirm the real catalog is empty before admitting the next case;
            # do not close unknown leftovers, restart the host or retry a case.
            self.checkpoint(name + ".cleanup-check")
            print(f"Modeling gate: {name}.cleanup-check", flush=True)
            self.require_empty(after_case=name)
            self.record["cases"].append(name)
            self.checkpoint(name + ".verified")
        self.require_empty()
        self.record["host_after"] = self.health()["host"]
        require(
            self.record["host_after"]["process_id"]
            == self.record["host"]["process_id"],
            "SOLIDWORKS was replaced during the modeling gate",
        )

    def cleanup(self):
        self.cleaning_up = True
        for document in list(self.owned):
            try:
                self.close(document)
            except Exception as exc:
                self.record["cleanup_errors"].append(
                    {
                        "document_id": document,
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
                )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--host-output-dir", type=host_directory)
    parser.add_argument("--cli-command", type=executable)
    parser.add_argument(
        "--request-timeout",
        type=request_timeout,
        default=DEFAULT_REQUEST_TIMEOUT_SECONDS,
        help="per-request timeout in seconds (0 < seconds <= 3600; default: 120); CLI process gets 15 extra seconds",
    )
    parser.add_argument(
        "--endpoint", default=os.environ.get("SWCLI_ENDPOINT", DEFAULT_ENDPOINT)
    )
    parser.add_argument(
        "--depth-request-timeout",
        type=request_timeout,
        default=DEFAULT_DEPTH_REQUEST_TIMEOUT_SECONDS,
        help="guarded depth-write/equal-depth request budget in seconds (default: 600)",
    )
    parser.add_argument("--sample-part", type=host_directory)
    parser.add_argument("--suite", choices=("core", "full"), default="full",
                        help="core daily regression or complete CAD/negative-case coverage")
    parser.add_argument("--case-set", choices=("all", "native", "assembly", "exports", "reverse-cut", "through-all", "depth",
                                              "drawing-save", "drawing-save-as", "drawing-copy-first", "drawing-copy-reopen", "drawing-reopen-no-inspect", "continuation"), default="all")
    parser.add_argument("--sample-assembly", type=host_directory)
    parser.add_argument("--verify-sample-assembly-save", action="store_true",
                        help="also prepare and strictly save/reopen the official ASM fixture; generated ASM is always tested")
    parser.add_argument("--sample-drawing", type=host_directory,
                        help="installed drawing source in the daemon's Windows namespace")
    parser.add_argument("--sample-drawing-local", type=Path,
                        help="same installed drawing source in the client's filesystem namespace")
    parser.add_argument("--drawing-work-dir", type=Path,
                        help="existing client-visible temporary drawing/reference fixture directory")
    parser.add_argument("--host-drawing-work-dir", type=host_directory,
                        help="same temporary fixture directory in the daemon's Windows namespace")
    arguments = parser.parse_args(argv)
    if bool(arguments.sample_part) != bool(arguments.sample_assembly):
        parser.error("sample-part and sample-assembly must be supplied together")
    if arguments.verify_sample_assembly_save and not arguments.sample_assembly:
        parser.error("verify-sample-assembly-save requires sample-assembly")
    if bool(arguments.sample_drawing) != bool(arguments.sample_drawing_local):
        parser.error("sample-drawing and sample-drawing-local must be supplied together")
    if bool(arguments.drawing_work_dir) != bool(arguments.host_drawing_work_dir):
        parser.error("drawing-work-dir and host-drawing-work-dir must be supplied together")
    if arguments.drawing_work_dir and not arguments.sample_drawing:
        parser.error("drawing work directories require a sample-drawing source")
    directory = arguments.output_dir.expanduser().resolve()
    host = arguments.host_output_dir or str(directory)
    host_directory(host)  # POSIX clients must explicitly supply the host namespace.
    directory.mkdir(parents=True, exist_ok=True)
    smoke = ModelingSmoke(
        directory=directory,
        host_directory=host,
        endpoint=arguments.endpoint,
        cli=[arguments.cli_command] if arguments.cli_command else None,
        request_timeout_seconds=arguments.request_timeout,
        depth_request_timeout_seconds=arguments.depth_request_timeout,
        suite=arguments.suite,
        case_set=arguments.case_set,
    )
    # Never overwrite prior evidence, even before the first host operation.
    with smoke.record_path.open("x", encoding="utf-8") as stream:
        json.dump(smoke.record, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    error = None
    try:
        smoke.run(
            sample_part=arguments.sample_part, sample_assembly=arguments.sample_assembly,
            verify_sample_assembly_save=arguments.verify_sample_assembly_save,
            sample_drawing=arguments.sample_drawing,
            sample_drawing_local=arguments.sample_drawing_local,
            drawing_work_dir=arguments.drawing_work_dir,
            host_drawing_work_dir=arguments.host_drawing_work_dir,
        )
    except Exception as exc:
        error = exc
        smoke.record["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        smoke.cleanup()
        if error is None and smoke.checkpoint_error is not None:
            error = smoke.checkpoint_error
            smoke.record["error"] = {
                "type": type(error).__name__,
                "message": str(error),
            }
        smoke.record["state"] = "completed"
        smoke.record["success"] = error is None and not smoke.record["cleanup_errors"]
        smoke.checkpoint("completed")
    if error is None and smoke.checkpoint_error is not None:
        error = smoke.checkpoint_error
    if error is not None:
        raise error
    require(
        smoke.record["success"],
        f"modeling cleanup failed: {smoke.record['cleanup_errors']}",
    )
    print(f"Shared modeling verified; record: {smoke.record_path}", flush=True)


if __name__ == "__main__":
    main()
