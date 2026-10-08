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


# Match the ten-minute CI phase, without extending any command/phase deadline.
LEASE_TTL_SECONDS = 600


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def close_enough(value, expected, message):
    require(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and math.isclose(value, expected, rel_tol=1e-9, abs_tol=1e-6),
        message,
    )


def host_path(directory, filename):
    # Protocol paths are deliberately in the daemon's namespace, unlike the
    # local JSON record. Do not silently convert a Linux path into a Win path.
    path_type = (
        PureWindowsPath
        if re.match(r"^[A-Za-z]:[\\/]", directory) or directory.startswith("\\\\")
        else PurePosixPath
    )
    return str(path_type(directory) / filename)


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


def assert_dimension(result, dimension_id, sketch_id, value):
    dimension = result["dimension"]
    require(
        re.fullmatch(r"m-[a-z0-9]{6}", dimension["dimension_id"]) is not None,
        "dimension did not receive a short registered handle",
    )
    require(
        dimension["dimension_id"] == dimension_id
        and dimension["sketch_id"] == sketch_id
        and dimension["kind"] == "diameter"
        and dimension["unit"] == "millimeter"
        and dimension["driven_state"] == 2
        and not dimension["read_only"]
        and bool(dimension["configuration"])
        and bool(dimension["native_name"]),
        "dimension identity, units, configuration or driving state changed",
    )
    close_enough(dimension["value"], value, "native diameter value is incorrect")


def assert_circle(result, radius, *, absorbed):
    require(
        result["geometry_complete"]
        and not result["editing"]
        and result["coordinate_system"] == "sketch-local"
        and result["profile_segment_count"] == 1
        and result["segment_count"] == 1
        and result["sketch"]["absorbed"] == absorbed,
        "circle observation is incomplete or its ownership/edit state changed",
    )
    segment = result["segments"][0]
    geometry = segment["geometry"]
    require(
        not segment["construction"]
        and geometry["kind"] == "arc"
        and geometry["complete_circle"],
        "profile is not one complete non-construction circle",
    )
    close_enough(geometry["radius_mm"], radius, "circle radius did not follow diameter")
    for axis, expected in (("x", 3), ("y", 4), ("z", 0)):
        close_enough(
            geometry["center_mm"][axis],
            expected,
            "driving edit moved the circle center",
        )


def assert_measurement(result, radius):
    metrics = result["metrics"]
    require(metrics["solid_body_count"] == 1, "expected one native solid body")
    close_enough(
        metrics["volume_mm3"], math.pi * radius**2 * 10, "cylinder volume is incorrect"
    )
    close_enough(
        metrics["surface_area_mm2"],
        2 * math.pi * radius * (radius + 10),
        "cylinder surface area is incorrect",
    )


def assert_fixed_center(result, sketch_id, *, created):
    validate_operation_result("sketch.fix-center", result)
    require(
        result["sketch_id"] == sketch_id and result["created"] is created,
        "center fixing targeted a different sketch or duplicated an existing fix",
    )
    geometry = result["center"]["geometry"]
    close_enough(geometry["width_mm"], 40, "center fixing changed rectangle width")
    close_enough(geometry["height_mm"], 30, "center fixing changed rectangle height")
    for axis, value in (("x", 3), ("y", 4), ("z", 0)):
        close_enough(
            geometry["center_mm"][axis], value, "center fixing moved the center"
        )
    for actual, expected in zip(geometry["bounds_mm"], (-17, -11, 23, 19)):
        close_enough(actual, expected, "center fixing changed rectangle bounds")


def assert_discovered_diameter(result, dimension_id, sketch_id, stamp):
    assert_dimension(result, dimension_id, sketch_id, 20)
    dimension = result["dimension"]
    require(
        result["sketch_id"] == sketch_id
        and type(dimension["driven_state"]) is int
        and dimension["read_only"] is False
        and isinstance(dimension["native_name"], str)
        and bool(dimension["native_name"].strip())
        and result["editing"] is False
        and result["equation_control"] == {"controlled": False, "equation_indices": []}
        and result["equation_control"]["controlled"] is False
        and result["design_table_controlled"] is False,
        "discovered diameter ownership or native control state is incorrect",
    )
    geometry = result["geometry_verification"]
    require(
        geometry["passed"] is True
        and geometry["method"] == "sketch-local-circle"
        and geometry["complete_circle"] is True
        and geometry["segment_count"] == 1
        and geometry["profile_segment_count"] == 1,
        "discovered diameter geometry verification is incomplete or failed",
    )
    close_enough(
        geometry["actual_radius_mm"], 10, "discovered diameter radius is incorrect"
    )
    for axis, expected in (("x", 3), ("y", 4), ("z", 0)):
        close_enough(
            geometry["actual_center_mm"][axis],
            expected,
            "discovered diameter circle center changed",
        )
    observation = result["observation"]
    before, after = observation["before"], observation["after"]
    require(
        observation["unchanged"] is True
        and observation["configuration_matched"] is True
        and before == after
        and all(
            type(state["update_stamp"]) is int
            and state["update_stamp"] == stamp
            and isinstance(state["configuration"], str)
            and bool(state["configuration"].strip())
            and state["configuration"] == dimension["configuration"]
            and state["editing"] is False
            for state in (before, after)
        ),
        "diameter discovery observation changed stamp, configuration or edit state",
    )


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


class DrivingSmoke:
    def __init__(
        self, *, endpoint, session, output_directory, cli=None, after_modeling=None
    ):
        self.endpoint = endpoint
        self.session = session
        self.output_directory = output_directory
        # Use the same installed package as this isolated script, even if the
        # caller's shell still has PYTHONPATH pointing at a development tree.
        self.cli = cli or [sys.executable, "-I", "-m", "swcli"]
        self.after_modeling = after_modeling
        self.record = {
            "state": "running",
            "stage": "initializing",
            "session_id": session,
            "endpoint": endpoint,
            "planes": [],
            "events": [],
        }
        self.owned = {}
        self.checkpoint_writer = None
        self.checkpoint_error = None
        self._cleaning_up = False

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
                timeout_seconds=120,
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
            "120",
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
                timeout=135,
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
        return result

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

    def observe(
        self, document_id, sketch_id, dimension_id, value, *, absorbed, cli=False
    ):
        before = self.stamp(document_id)
        result = (
            self.command(
                ["dimension", "inspect", dimension_id, "--document", document_id]
            )
            if cli
            else self.call(
                "dimension.inspect",
                {"dimension_id": dimension_id},
                document_id=document_id,
            )
        )
        assert_dimension(result, dimension_id, sketch_id, value)
        circle = self.call(
            "sketch.inspect", {"sketch_id": sketch_id}, document_id=document_id
        )
        assert_circle(circle, value / 2, absorbed=absorbed)
        require(
            self.stamp(document_id) == before,
            "read-only dimension/sketch inspect changed native stamp",
        )
        return result

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

    def discover_reopened_sketch(self, document_id, *, foreground_id, current_id, cli):
        reopen_session = self.session + "-reopen"
        before_stamp = self.stamp(document_id)
        before_selection = {
            "main": self.selection_state(session_id=self.session),
            "reopen": self.selection_state(session_id=reopen_session),
        }
        require(
            before_selection["main"]
            == {"current_document_id": current_id, "active_document_id": foreground_id}
            and before_selection["reopen"]
            == {
                "current_document_id": foreground_id,
                "active_document_id": foreground_id,
            },
            "reopened sketch discovery did not start with the intended background/session state",
        )
        proof = {
            "document_id": document_id,
            "main_session_id": self.session,
            "reopen_session_id": reopen_session,
            "update_stamp_before": before_stamp,
            "selection_before": before_selection,
        }
        self.record.setdefault("reopened_sketch_discoveries", []).append(proof)
        self.checkpoint("reopened-sketch-discovery.started")

        def list_sketches():
            return (
                self.command(["sketch", "list", "--document", document_id])
                if cli
                else self.call("sketch.list", document_id=document_id)
            )

        listed = list_sketches()
        proof["listed"] = listed
        require(
            listed["count"] == 1 and len(listed["sketches"]) == 1,
            "native reopen did not discover exactly one complete 2D sketch",
        )
        descriptor = listed["sketches"][0]
        sketch_id = descriptor["sketch_id"]
        proof["sketch_id"] = sketch_id
        require(
            re.fullmatch(r"s-[a-z0-9]{6}", sketch_id) is not None
            and descriptor["type"] == "ProfileFeature"
            and descriptor["absorbed"]
            and descriptor["owner"] is not None
            and bool(descriptor["owner"]["name"])
            and bool(descriptor["owner"]["type"]),
            "discovered sketch lacks exact registered/absorbed ownership metadata",
        )
        self.checkpoint("reopened-sketch-discovery.listed")
        repeated = list_sketches()
        proof["repeated"] = repeated
        require(
            repeated["count"] == 1
            and len(repeated["sketches"]) == 1
            and repeated["sketches"][0]["sketch_id"] == sketch_id,
            "repeated sketch discovery changed a live native sketch handle",
        )
        self.checkpoint("reopened-sketch-discovery.repeated")
        # This handle comes only from the reopened native feature traversal.
        # Never select by a remembered native name or reuse the expired handle.
        observed = self.call(
            "sketch.inspect", {"sketch_id": sketch_id}, document_id=document_id
        )
        proof["observed"] = observed
        require(
            observed["sketch"]["sketch_id"] == sketch_id,
            "reopened sketch inspection returned a different registered handle",
        )
        assert_circle(observed, 10, absorbed=True)
        self.checkpoint("reopened-sketch-discovery.observed")
        after_stamp = self.stamp(document_id)
        after_selection = {
            "main": self.selection_state(session_id=self.session),
            "reopen": self.selection_state(session_id=reopen_session),
        }
        proof.update(update_stamp_after=after_stamp, selection_after=after_selection)
        for result in (listed, repeated, observed):
            require(
                result["document"]["document_id"] == document_id
                and not result["document"]["current"]
                and not result["document"]["active"],
                "reopened sketch observation changed its background document identity",
            )
        require(
            after_stamp == before_stamp,
            "sketch discovery/inspection changed native update stamp",
        )
        require(
            after_selection == before_selection,
            "sketch discovery changed foreground or session current",
        )
        self.checkpoint("reopened-sketch-discovery.completed")
        return proof

    def discover_reopened_dimension(
        self,
        document_id,
        *,
        sketch_id,
        expired_dimension_id,
        foreground_id,
        current_id,
        cli,
    ):
        reopen_session = self.session + "-reopen"
        before_stamp = self.stamp(document_id)
        before_selection = {
            "main": self.selection_state(session_id=self.session),
            "reopen": self.selection_state(session_id=reopen_session),
        }
        require(
            before_selection["main"]
            == {"current_document_id": current_id, "active_document_id": foreground_id}
            and before_selection["reopen"]
            == {
                "current_document_id": foreground_id,
                "active_document_id": foreground_id,
            },
            "reopened diameter discovery did not start with the intended background/session state",
        )
        proof = {
            "document_id": document_id,
            "sketch_id": sketch_id,
            "expired_dimension_id": expired_dimension_id,
            "update_stamp_before": before_stamp,
            "selection_before": before_selection,
        }
        self.record.setdefault("reopened_dimension_discoveries", []).append(proof)
        self.checkpoint("reopened-dimension-discovery.started")

        def discover():
            return (
                self.command(
                    [
                        "dimension",
                        "discover-diameter",
                        sketch_id,
                        "--document",
                        document_id,
                    ]
                )
                if cli
                else self.call(
                    "dimension.discover-diameter",
                    {"sketch_id": sketch_id},
                    document_id=document_id,
                )
            )

        discovered = discover()
        proof["discovered"] = discovered
        dimension_id = discovered["dimension"]["dimension_id"]
        proof["dimension_id"] = dimension_id
        require(
            dimension_id != expired_dimension_id,
            "reopened diameter discovery reused an expired dimension handle",
        )
        assert_discovered_diameter(discovered, dimension_id, sketch_id, before_stamp)
        self.checkpoint("reopened-dimension-discovery.discovered")
        repeated = discover()
        proof["repeated"] = repeated
        require(
            repeated["dimension"]["dimension_id"] == dimension_id,
            "repeated diameter discovery changed a live native dimension handle",
        )
        assert_discovered_diameter(repeated, dimension_id, sketch_id, before_stamp)
        require(
            repeated["observation"]["before"] == discovered["observation"]["before"],
            "repeated diameter discovery changed its observation scope",
        )
        self.checkpoint("reopened-dimension-discovery.repeated")
        inspected = (
            self.command(
                ["dimension", "inspect", dimension_id, "--document", document_id]
            )
            if cli
            else self.call(
                "dimension.inspect",
                {"dimension_id": dimension_id},
                document_id=document_id,
            )
        )
        proof["inspected"] = inspected
        assert_dimension(inspected, dimension_id, sketch_id, 20)
        require(
            inspected["dimension"]["configuration"]
            == discovered["observation"]["before"]["configuration"]
            and inspected["geometry_verification"]["passed"] is True
            and inspected["editing"] is False
            and inspected["equation_control"]
            == {"controlled": False, "equation_indices": []}
            and inspected["design_table_controlled"] is False,
            "newly discovered diameter inspection changed geometry, configuration or control state",
        )
        self.checkpoint("reopened-dimension-discovery.inspected")
        after_stamp = self.stamp(document_id)
        after_selection = {
            "main": self.selection_state(session_id=self.session),
            "reopen": self.selection_state(session_id=reopen_session),
        }
        proof.update(update_stamp_after=after_stamp, selection_after=after_selection)
        for result in (discovered, repeated, inspected):
            require(
                result["document"]["document_id"] == document_id
                and result["document"]["current"] is False
                and result["document"]["active"] is False
                and result["document"]["update_stamp"] == before_stamp,
                "reopened diameter observation changed its background document identity or stamp",
            )
        require(
            after_stamp == before_stamp,
            "diameter discovery/inspection changed native update stamp",
        )
        require(
            after_selection == before_selection,
            "diameter discovery changed foreground or session current",
        )
        self.checkpoint("reopened-dimension-discovery.completed")
        return proof

    def close(self, document_id):
        owner = self.owned[document_id]
        self.renew_lease(document_id)
        self.call("document.close", {"discard": True}, document_id=document_id, **owner)

    def center_constraints(self, plane):
        """Public proof, including native persistence; no COM fixture or retry."""
        document_id = self.create()
        origin_id = self.create() if plane == "front" else None
        foreground_id = self.create()
        lease = self.call(
            "document.lease.acquire",
            {"ttl_seconds": LEASE_TTL_SECONDS},
            document_id=document_id,
        )["lease"]["lease_id"]
        write = {"document_id": document_id, "lease_id": lease}
        rectangle = self.write(
            "sketch.rectangle",
            {
                "plane": plane,
                "width_mm": 40,
                "height_mm": 30,
                "center_x_mm": 3,
                "center_y_mm": 4,
            },
            **write,
        )
        sketch_id = rectangle["sketch"]["sketch_id"]
        values = {"sketch_id": sketch_id}
        stamp = self.stamp(document_id)
        self.call(
            "sketch.fix-center",
            values,
            expected_error="DocumentLeaseConflict",
            document_id=document_id,
            session_id=self.session + "-contender",
        )
        self.write(
            "sketch.fix-center",
            values,
            expected_error="DocumentUpdateConflict",
            expected_update_stamp=stamp + 1,
            **write,
        )
        require(self.stamp(document_id) == stamp, "rejected center fix changed stamp")
        self.assert_background(document_id, foreground_id)
        fixed = (
            self.write_command(
                [
                    "sketch",
                    "fix-center",
                    "--document",
                    document_id,
                    sketch_id,
                    "--lease",
                    lease,
                    "--if-update-stamp",
                    str(stamp),
                ],
                document_id=document_id,
            )
            if plane == "front"
            else self.write(
                "sketch.fix-center", values, expected_update_stamp=stamp, **write
            )
        )
        assert_fixed_center(fixed, sketch_id, created=True)
        self.assert_background(document_id, foreground_id)
        fixed_stamp = self.stamp(document_id)
        repeated = self.write("sketch.fix-center", values, **write)
        assert_fixed_center(repeated, sketch_id, created=False)
        require(self.stamp(document_id) == fixed_stamp, "existing fix changed stamp")
        self.assert_background(document_id, foreground_id)
        proof = {
            "plane": plane,
            "sketch_id": sketch_id,
            "fixed": fixed,
            "repeated": repeated,
        }
        self.record.setdefault("center_constraints", []).append(proof)
        self.checkpoint(f"center.{plane}.fixed")

        if origin_id is not None:
            origin_lease = self.call(
                "document.lease.acquire",
                {"ttl_seconds": LEASE_TTL_SECONDS},
                document_id=origin_id,
            )["lease"]["lease_id"]
            origin_write = {"document_id": origin_id, "lease_id": origin_lease}
            origin = self.write(
                "sketch.rectangle",
                {"plane": plane, "width_mm": 40, "height_mm": 30},
                **origin_write,
            )
            origin_stamp = self.stamp(origin_id)
            proof["origin_refusal"] = self.write(
                "sketch.fix-center",
                {"sketch_id": origin["sketch"]["sketch_id"]},
                expected_error="UnsupportedCenterConstraint",
                **origin_write,
            )
            require(
                self.stamp(origin_id) == origin_stamp, "origin refusal changed stamp"
            )
            inspected = self.call(
                "sketch.inspect",
                {"sketch_id": origin["sketch"]["sketch_id"]},
                document_id=origin_id,
            )
            require(inspected["editing"] is False, "origin refusal left an edit active")
            self.assert_background(origin_id, foreground_id)
            self.close(origin_id)

        path = host_path(self.output_directory, f"rectangle-center-{plane}.SLDPRT")
        saved = self.write("document.save-as", {"output": path}, **write)
        proof["artifact"] = saved["artifact"]
        self.close(document_id)
        self.call(
            "sketch.fix-center",
            values,
            expected_error="SketchNotFound",
            document_id=foreground_id,
        )
        reopened = self.call("document.open", {"path": path, "read_only": True})
        reopened_id = reopened["document"]["document_id"]
        reopened_foreground = self.create()
        before = self.stamp(reopened_id)
        listed = self.call("sketch.list", document_id=reopened_id)
        require(listed["count"] == 1, "reopened rectangle has an ambiguous sketch list")
        recovered_id = listed["sketches"][0]["sketch_id"]
        require(recovered_id != sketch_id, "closed sketch handle was reused")
        require(self.stamp(reopened_id) == before, "sketch discovery changed stamp")
        self.call(
            "sketch.fix-center",
            values,
            expected_error="SketchNotFound",
            document_id=reopened_id,
        )
        recovered = self.write(
            "sketch.fix-center",
            {"sketch_id": recovered_id},
            document_id=reopened_id,
        )
        assert_fixed_center(recovered, recovered_id, created=False)
        require(self.stamp(reopened_id) == before, "saved fix readback changed stamp")
        self.assert_background(reopened_id, reopened_foreground)
        proof.update(
            reopened=recovered,
            recovered_sketch_id=recovered_id,
            expired_handles_rejected=True,
        )
        self.checkpoint(f"center.{plane}.verified")
        self.close(reopened_id)
        self.close(reopened_foreground)
        self.close(foreground_id)

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

    def plane(self, plane):
        use_cli = plane == "front"
        document_id = self.create()
        foreground_id = self.create()
        lease = self.call(
            "document.lease.acquire",
            {"ttl_seconds": LEASE_TTL_SECONDS},
            document_id=document_id,
        )["lease"]["lease_id"]
        write = {"document_id": document_id, "lease_id": lease}
        circle = self.write(
            "sketch.circle",
            {"plane": plane, "radius_mm": 5, "center_x_mm": 3, "center_y_mm": 4},
            **write,
        )
        sketch_id = circle["sketch"]["sketch_id"]
        self.assert_background(document_id, foreground_id)
        stamp = self.stamp(document_id)
        self.call(
            "sketch.dimension-diameter",
            {"sketch_id": sketch_id, "diameter_mm": 16},
            expected_error="DocumentLeaseConflict",
            document_id=document_id,
            session_id=self.session + "-contender",
        )
        self.write(
            "sketch.dimension-diameter",
            {"sketch_id": sketch_id, "diameter_mm": 16},
            expected_error="DocumentUpdateConflict",
            expected_update_stamp=stamp + 1,
            **write,
        )
        require(
            self.stamp(document_id) == stamp, "rejected creation changed native stamp"
        )
        created = (
            self.write_command(
                [
                    "sketch",
                    "dimension-diameter",
                    sketch_id,
                    "--diameter-mm",
                    "16",
                    "--document",
                    document_id,
                    "--lease",
                    lease,
                    "--if-update-stamp",
                    str(stamp),
                ],
                document_id=document_id,
            )
            if use_cli
            else self.write(
                "sketch.dimension-diameter",
                {"sketch_id": sketch_id, "diameter_mm": 16},
                expected_update_stamp=stamp,
                **write,
            )
        )
        dimension_id = created["dimension"]["dimension_id"]
        assert_dimension(created, dimension_id, sketch_id, 16)
        require(
            created["native_status"] == 0
            and created["geometry_verification"]["passed"]
            and not created["editing"],
            "diameter creation failed native verification",
        )
        self.observe(
            document_id, sketch_id, dimension_id, 16, absorbed=False, cli=use_cli
        )
        stamp = self.stamp(document_id)
        self.write(
            "sketch.dimension-diameter",
            {"sketch_id": sketch_id, "diameter_mm": 18},
            expected_error="SketchAlreadyDimensioned",
            **write,
        )
        require(
            self.stamp(document_id) == stamp, "duplicate creation changed native stamp"
        )
        extrusion = self.write(
            "feature.extrude", {"sketch_id": sketch_id, "depth_mm": 10}, **write
        )
        assert_measurement(self.call("document.measure", document_id=document_id), 8)
        self.observe(document_id, sketch_id, dimension_id, 16, absorbed=True)
        stamp = self.stamp(document_id)
        self.call(
            "dimension.set",
            {"dimension_id": dimension_id, "value_mm": 22},
            expected_error="DocumentLeaseConflict",
            document_id=document_id,
            session_id=self.session + "-contender",
        )
        self.write(
            "dimension.set",
            {"dimension_id": dimension_id, "value_mm": 22},
            expected_error="DocumentUpdateConflict",
            expected_update_stamp=stamp + 1,
            **write,
        )
        require(
            self.stamp(document_id) == stamp, "rejected value edit changed native stamp"
        )
        changed = (
            self.write_command(
                [
                    "dimension",
                    "set",
                    dimension_id,
                    "--value-mm",
                    "20",
                    "--document",
                    document_id,
                    "--lease",
                    lease,
                    "--if-update-stamp",
                    str(stamp),
                ],
                document_id=document_id,
            )
            if use_cli
            else self.write(
                "dimension.set",
                {"dimension_id": dimension_id, "value_mm": 20},
                expected_update_stamp=stamp,
                **write,
            )
        )
        assert_dimension(changed, dimension_id, sketch_id, 20)
        require(
            changed["native_status"] == 0
            and changed["geometry_verification"]["passed"]
            and not changed["editing"],
            "absorbed diameter edit failed native verification",
        )
        self.observe(document_id, sketch_id, dimension_id, 20, absorbed=True)
        self.assert_background(document_id, foreground_id)
        measured = self.call("document.measure", document_id=document_id)
        assert_measurement(measured, 10)
        diagnosis = self.call("document.diagnose", document_id=document_id)
        require(
            diagnosis["diagnostics"]["healthy"] and diagnosis["needs_rebuild"] == 0,
            "edited cylinder needs rebuild or has feature diagnostics",
        )
        native_path = host_path(self.output_directory, f"{self.session}-{plane}.SLDPRT")
        saved = self.write("document.save-as", {"output": native_path}, **write)
        require(
            saved["artifact"]["size_bytes"] >= 512
            and saved["document"]["document_id"] == document_id,
            "native save lost document identity or produced an invalid file",
        )
        self.observe(document_id, sketch_id, dimension_id, 20, absorbed=True)
        self.assert_background(document_id, foreground_id)
        self.close(document_id)
        reopened = self.call(
            "document.open",
            {"path": native_path, "read_only": True},
            session_id=self.session + "-reopen",
        )
        reopened_id = reopened["document"]["document_id"]
        require(
            reopened_id != document_id,
            "native reopen reused an expired document handle",
        )
        self.call(
            "dimension.inspect",
            {"dimension_id": dimension_id},
            expected_error="DimensionNotFound",
            document_id=reopened_id,
        )
        self.call(
            "dimension.set",
            {"dimension_id": dimension_id, "value_mm": 22},
            expected_error="DimensionNotFound",
            document_id=reopened_id,
        )
        self.call(
            "sketch.inspect",
            {"sketch_id": sketch_id},
            expected_error="SketchNotFound",
            document_id=reopened_id,
        )
        reopened_foreground_id = self.create(session_id=self.session + "-reopen")
        discovered = self.discover_reopened_sketch(
            reopened_id,
            foreground_id=reopened_foreground_id,
            current_id=foreground_id,
            cli=use_cli,
        )
        discovered_dimension = self.discover_reopened_dimension(
            reopened_id,
            sketch_id=discovered["sketch_id"],
            expired_dimension_id=dimension_id,
            foreground_id=reopened_foreground_id,
            current_id=foreground_id,
            cli=use_cli,
        )
        reopened_measurement = self.call("document.measure", document_id=reopened_id)
        assert_measurement(reopened_measurement, 10)
        structure = self.call(
            "document.inspect", {"detail": "structure"}, document_id=reopened_id
        )["structure"]
        require(
            structure["bodies"]["count"] == 1
            and not structure["features"]["truncated"],
            "native reopen changed body count or truncated structure observation",
        )
        require(
            any(
                item["name"] == extrusion["feature"]["name"]
                for item in structure["features"]["items"]
            ),
            "native reopen lost the created extrusion feature",
        )
        reopened_diagnosis = self.call("document.diagnose", document_id=reopened_id)
        require(
            reopened_diagnosis["diagnostics"]["healthy"]
            and reopened_diagnosis["needs_rebuild"] == 0,
            "saved/reopened cylinder has feature/rebuild diagnostics",
        )
        self.record["planes"].append(
            {
                "plane": plane,
                "dimension_id": dimension_id,
                "sketch_id": sketch_id,
                "native_path": native_path,
                "artifact": saved["artifact"],
                "before_edit_volume_mm3": math.pi * 64 * 10,
                "after_edit_metrics": measured["metrics"],
                "reopened_metrics": reopened_measurement["metrics"],
                "expired_handles_rejected": True,
                "reopened_sketch_discovery": discovered,
                "reopened_dimension_discovery": discovered_dimension,
            }
        )
        self.checkpoint(f"plane.{plane}.verified")
        self.close(reopened_id)
        self.close(reopened_foreground_id)
        self.close(foreground_id)

    def run(self):
        predecessor_pid = (
            modeling_host(self.after_modeling) if self.after_modeling else None
        )
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
            "dimension.discover-diameter",
            "dimension.inspect",
            "dimension.set",
            "sketch.list",
        ):
            require(
                operation in health["operations"], f"installed daemon lacks {operation}"
            )
        self.checkpoint("host.verified")
        for plane in ("front", "top", "right"):
            self.record["current_plane"] = plane
            self.checkpoint(f"plane.{plane}.starting")
            print(f"Driving-dimension gate: {plane} starting", flush=True)
            self.plane(plane)
            self.center_constraints(plane)
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
        f"Driving dimensions and center fixes verified on front/top/right; record: {record_path}"
    )


if __name__ == "__main__":
    main()
