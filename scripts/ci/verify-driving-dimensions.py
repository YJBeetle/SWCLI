"""Exercise installed driving-dimension commands against an existing daemon.

No COM objects are imported here. The front plane goes through the installed
CLI entry point; the other planes use its public daemon client. A remote/Wine
host can use --host-output-dir for its view of the supplied output directory.
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
import uuid

from swcli.daemon.client import DEFAULT_ENDPOINT, call_daemon


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


class DrivingSmoke:
    def __init__(self, *, endpoint, session, output_directory, cli=None):
        self.endpoint = endpoint
        self.session = session
        self.output_directory = output_directory
        # Use the same installed package as this isolated script, even if the
        # caller's shell still has PYTHONPATH pointing at a development tree.
        self.cli = cli or [sys.executable, "-I", "-m", "swcli"]
        self.record = {
            "session_id": session,
            "endpoint": endpoint,
            "planes": [],
            "events": [],
        }
        self.owned = {}

    def call(self, operation, parameters=None, *, expected_error=None, **context):
        context.setdefault("session_id", self.session)
        response = call_daemon(
            operation,
            parameters,
            endpoint=self.endpoint,
            timeout_seconds=120,
            **context,
        )
        self.record["events"].append(
            {"transport": "protocol", "operation": operation, "response": response}
        )
        if expected_error is not None:
            require(
                not response.get("success")
                and response.get("error", {}).get("code") == expected_error,
                f"{operation} did not reject with {expected_error}: {response}",
            )
            return response
        require(response.get("success"), f"{operation} failed: {response}")
        result = response["result"]
        require(
            result.get("ok", True), f"{operation} returned a failed result: {result}"
        )
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
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=135,
            env=environment,
        )
        stdout = completed.stdout.decode("utf-8-sig")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        event = {
            "transport": "cli",
            "arguments": arguments,
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
        self.record["events"].append(event)
        require(completed.returncode == 0, f"installed CLI failed: {event}")
        result = json.loads(stdout)
        require(result.get("ok"), f"installed CLI returned a failed result: {result}")
        event["result"] = result
        return result

    def create(self, *, session_id=None):
        result = self.call(
            "document.create", {"type": "part"}, session_id=session_id or self.session
        )
        document_id = result["document"]["document_id"]
        self.owned[document_id] = {
            "session_id": session_id or self.session,
            "lease_id": None,
        }
        return document_id

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

    def close(self, document_id):
        owner = self.owned[document_id]
        self.call("document.close", {"discard": True}, document_id=document_id, **owner)
        del self.owned[document_id]

    def cleanup(self):
        errors = []
        for document_id in reversed(tuple(self.owned)):
            try:
                self.close(document_id)
            except Exception as exc:
                errors.append({"document_id": document_id, "message": str(exc)})
        self.record["cleanup_errors"] = errors
        return errors

    def plane(self, plane):
        use_cli = plane == "front"
        document_id = self.create()
        foreground_id = self.create()
        lease = self.call(
            "document.lease.acquire", {"ttl_seconds": 300}, document_id=document_id
        )["lease"]["lease_id"]
        self.owned[document_id]["lease_id"] = lease
        write = {"document_id": document_id, "lease_id": lease}
        circle = self.call(
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
        self.call(
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
            self.command(
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
                ]
            )
            if use_cli
            else self.call(
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
        self.call(
            "sketch.dimension-diameter",
            {"sketch_id": sketch_id, "diameter_mm": 18},
            expected_error="SketchAlreadyDimensioned",
            **write,
        )
        require(
            self.stamp(document_id) == stamp, "duplicate creation changed native stamp"
        )
        extrusion = self.call(
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
        self.call(
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
            self.command(
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
                ]
            )
            if use_cli
            else self.call(
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
        saved = self.call("document.save-as", {"output": native_path}, **write)
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
        self.owned[reopened_id] = {
            "session_id": self.session + "-reopen",
            "lease_id": None,
        }
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
            }
        )
        self.close(reopened_id)
        self.close(foreground_id)

    def run(self):
        health = self.call("daemon.health")
        require(
            health["host_connected"], "driving gate needs an already connected host"
        )
        self.record["host"] = health["host"]
        for operation in (
            "sketch.dimension-diameter",
            "dimension.inspect",
            "dimension.set",
        ):
            require(
                operation in health["operations"], f"installed daemon lacks {operation}"
            )
        for plane in ("front", "top", "right"):
            self.plane(plane)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--host-output-dir",
        help="daemon-visible path for native artifacts; default: local output-dir",
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
    )
    # Reserve evidence before calling the daemon; never mutate the host and
    # only afterwards discover that a previous run's record would be replaced.
    with record_path.open("x", encoding="utf-8") as stream:
        error = None
        try:
            smoke.run()
        except Exception as exc:
            error = exc
            smoke.record["error"] = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            cleanup_errors = smoke.cleanup()
            smoke.record["success"] = error is None and not cleanup_errors
            json.dump(
                smoke.record, stream, ensure_ascii=False, allow_nan=False, indent=2
            )
            stream.write("\n")
    if error is not None:
        raise error
    require(not cleanup_errors, f"driving gate cleanup failed: {cleanup_errors}")
    print(f"Driving dimensions verified on front/top/right; record: {record_path}")


if __name__ == "__main__":
    main()
