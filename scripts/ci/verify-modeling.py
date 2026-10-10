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
from swcli.result_schemas import validate_operation_result

# Bound read-only observation groups independently of request/phase deadlines.
# The daemon lease default stays unchanged; holder writes still renew.
LEASE_TTL_SECONDS = 600
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120
DEFAULT_DEPTH_REQUEST_TIMEOUT_SECONDS = 600
MAX_REQUEST_TIMEOUT_SECONDS = 3600
CLI_TIMEOUT_GRACE_SECONDS = 15


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def near(actual, expected, message, tolerance=0.00001):
    require(
        type(actual) in (int, float)
        and math.isfinite(actual)
        and abs(actual - expected) <= tolerance,
        message,
    )


def unchanged_depth_metrics(before, after):
    # Independent kernel reads can differ by a few floating-point ULPs even
    # without a setter/rebuild. Keep every metric guarded, not dict equality.
    require(
        type(before["solid_body_count"]) is int
        and type(after["solid_body_count"]) is int
        and before["solid_body_count"] == after["solid_body_count"],
        "equal depth changed the solid body count",
    )
    pairs = [
        (key, before[key], after[key]) for key in ("volume_mm3", "surface_area_mm2")
    ] + [
        (f"centroid_mm.{axis}", before["centroid_mm"][axis], after["centroid_mm"][axis])
        for axis in "xyz"
    ]
    for label, expected, actual in pairs:
        require(
            type(expected) in (int, float) and math.isfinite(expected),
            f"equal depth has invalid baseline {label}",
        )
        near(
            actual,
            expected,
            f"equal depth changed {label}: {expected!r} -> {actual!r}",
            max(1e-6, abs(expected) * 1e-12),
        )


def verify_fixture_edges(edges, *, depth, hole_depth):
    """Check geometry, not identity, of the existing box/blind-hole fixture.

    Native raw endpoints are checked without deriving public length, normalized
    trim or closure semantics. Opposite curve sense and traversal order are valid.
    """
    lines = [edge for edge in edges if edge["curve_kind"] == "line"]
    circles = [edge for edge in edges if edge["curve_kind"] == "circle"]
    require(len(edges) == 14 and len(lines) == 12 and len(circles) == 2,
            "depth fixture edge enumeration/classification is incomplete")
    bounds = ((-40, 60), (-5, 45), (0, depth))
    expected_pairs = []
    for axis in range(3):
        other_axes = [index for index in range(3) if index != axis]
        for first in bounds[other_axes[0]]:
            for second in bounds[other_axes[1]]:
                start, end = [0, 0, 0], [0, 0, 0]
                for point in (start, end):
                    point[other_axes[0]], point[other_axes[1]] = first, second
                start[axis], end[axis] = bounds[axis]
                expected_pairs.append((start, end, axis))

    def same_point(first, second):
        return all(abs(a - b) <= 1e-5 for a, b in zip(first, second))

    for edge in lines:
        parameters = edge["parameter_data"]
        start, end = parameters["start_point_mm"], parameters["end_point_mm"]
        matches = [index for index, (a, b, _) in enumerate(expected_pairs)
                   if (same_point(start, a) and same_point(end, b))
                   or (same_point(start, b) and same_point(end, a))]
        require(len(matches) == 1, "fixture edge endpoints are missing, duplicated or misplaced")
        _, _, axis = expected_pairs.pop(matches[0])
        line = edge["curve_geometry"]["line"]
        direction, root = line["direction"], line["root_point_mm"]
        near(abs(direction[axis]), 1, "fixture line direction tilted", 1e-9)
        for index in range(3):
            if index != axis:
                near(direction[index], 0, "fixture line direction tilted", 1e-9)
                near(root[index], start[index], "untrimmed line does not contain native endpoints")
    require(not expected_pairs, "fixture line set is incomplete")
    levels = [0, hole_depth]
    for edge in circles:
        circle = edge["curve_geometry"]["circle"]
        center, axis = circle["center_mm"], circle["axis_direction"]
        near(circle["radius_mm"], 3, "fixture circle radius changed")
        near(center[0], 10, "fixture circle center moved")
        near(center[1], 20, "fixture circle center moved")
        near(axis[0], 0, "fixture circle axis tilted", 1e-9)
        near(axis[1], 0, "fixture circle axis tilted", 1e-9)
        near(abs(axis[2]), 1, "fixture circle axis tilted", 1e-9)
        matches = [index for index, z in enumerate(levels) if abs(center[2] - z) <= 1e-5]
        require(len(matches) == 1, "fixture circle levels are missing, duplicated or misplaced")
        levels.pop(matches[0])
        for key in ("start_point_mm", "end_point_mm"):
            point = edge["parameter_data"][key]
            near(point[2], center[2], "native circle endpoint left its plane")
            near(math.hypot(point[0] - center[0], point[1] - center[1]), 3,
                 "native circle endpoint left its untrimmed curve")
    require(not levels, "fixture circle set is incomplete")


def executable(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
        raise argparse.ArgumentTypeError(
            "cli-command must be one absolute executable path"
        )
    return str(path.resolve())


def host_directory(value):
    path = PureWindowsPath(value)
    if "\0" in value or not path.is_absolute():
        raise argparse.ArgumentTypeError(
            "host paths must be absolute Windows/UNC paths"
        )
    return value


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


class ModelingSmoke:
    def __init__(
        self,
        *,
        directory,
        host_directory,
        endpoint,
        cli=None,
        request_timeout_seconds=DEFAULT_REQUEST_TIMEOUT_SECONDS,
        depth_request_timeout_seconds=DEFAULT_DEPTH_REQUEST_TIMEOUT_SECONDS,
    ):
        self.directory = directory
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
            "session_id": self.session,
            "endpoint": endpoint,
            "request_timeout_seconds": self.request_timeout_seconds,
            "depth_request_timeout_seconds": self.depth_request_timeout_seconds,
            "cli_process_timeout_seconds": (
                self.request_timeout_seconds + CLI_TIMEOUT_GRACE_SECONDS
            ),
            "events": [],
            "cases": [],
            "cleanup_errors": [],
        }

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
            else:
                require(
                    completed.returncode == 0
                    and isinstance(result, dict)
                    and (
                        result.get("ok") is True
                        or result.get("success") is True
                        or (
                            arguments == ("capabilities",)
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

    def write(self, *arguments, document, expected_error=None, timeout_seconds=None):
        return self.command(
            *arguments,
            document=document,
            lease=self.renew(document),
            expected_error=expected_error,
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

    def observe_features(self, document, *, bosses, cuts, background=False):
        """Read exact handles/definitions without the holder's write token."""
        observer = self.session + "-observer"
        self.renew(document)
        listed = self.command("feature", "list", document=document, session=observer)
        features = listed["features"]
        observation = listed["observation"]
        require(
            listed["scope"] == "part-extrusions"
            and listed["count"] == len(features) == bosses + cuts
            and observation["unchanged"] is True
            and observation["before"] == observation["after"]
            and observation["after"]["editing"] is False
            and listed["document"]["update_stamp"]
            == observation["after"]["update_stamp"]
            and listed["document"]["modified"] == observation["after"]["modified"],
            "feature listing is incomplete or changed native state",
        )
        ids = [feature["feature_id"] for feature in features]
        require(
            len(set(ids)) == len(ids)
            and all(re.fullmatch(r"f-[a-z0-9]{6}", value) for value in ids)
            and sum(f["kind"] == "boss-extrude" for f in features) == bosses
            and sum(f["kind"] == "cut-extrude" for f in features) == cuts,
            "feature listing lost exact handles or native kind coverage",
        )
        if background:
            self.background(listed, document)
        for feature in features:
            self.renew(document)
            inspected = self.command(
                "feature",
                "inspect",
                feature["feature_id"],
                "--if-update-stamp",
                listed["document"]["update_stamp"],
                document=document,
                session=observer,
            )
            definition = inspected["definition"]
            state = inspected["observation"]
            require(
                inspected["feature"] == feature
                and state["unchanged"] is True
                and state["before"] == state["after"] == observation["after"]
                and definition["end_condition"] == 0
                and definition["both_directions"] is False
                and definition["thin"] is False
                and definition["from_type"] == 0
                and definition["forward_draft"] is False
                and definition["reverse_draft"] is False,
                "feature inspection lost exact definition or changed native state",
            )
            near(definition["depth_mm"], 20, "read-only native feature depth changed")
            if background:
                self.background(inspected, document)
        repeated = self.command("feature", "list", document=document, session=observer)
        require(
            repeated["features"] == features and repeated["observation"] == observation,
            "repeated live feature observation changed handles or state",
        )
        return ids

    def native_model(self):
        a, b = self.create(), self.create()
        require(a != b, "unsaved documents received the same handle")
        selected = self.command("document", "inspect", document=a)
        self.background(selected, a)
        stamp = selected["document"]["update_stamp"]
        require(type(stamp) is int, "GetUpdateStamp unavailable on this host")
        lease = self.command(
            "document",
            "lease",
            "acquire",
            "--ttl-seconds",
            LEASE_TTL_SECONDS,
            document=a,
        )["lease"]["lease_id"]
        self.command(
            "sketch",
            "rectangle",
            "--plane",
            "front",
            "--width-mm",
            100,
            "--height-mm",
            50,
            document=a,
            session=self.session + "-contender",
            expected_error="DocumentLeaseConflict",
        )
        self.write(
            "sketch",
            "rectangle",
            "--plane",
            "front",
            "--width-mm",
            100,
            "--height-mm",
            50,
            "--if-update-stamp",
            stamp + 1,
            document=a,
            expected_error="DocumentUpdateConflict",
        )
        sketches = []
        for index, plane in enumerate(("front", "top", "right")):
            rectangle = self.rectangle(a, plane, 100, 50, 10, 20)
            self.background(rectangle, a)
            sketches.append(rectangle["sketch"]["sketch_id"])
            extrusion = self.feature(
                a, sketches[-1], depth=20, reverse=index == 1, merge=index != 2
            )
            self.background(extrusion, a)
            if index == 0:
                size = extrusion["bodies"]["items"][0]["approximate_bounding_box"][
                    "size_mm"
                ]
                require(
                    extrusion["bodies"]["count"] == 1,
                    "first extrusion is not one solid",
                )
                for axis, expected in (("x", 100), ("y", 50), ("z", 20)):
                    near(
                        size[axis],
                        expected,
                        "first extrusion bounding box changed",
                        0.1,
                    )
                measured = self.measure(a, volume=100000, area=16000)
                self.background(measured, a)
                for axis, expected in (("x", 10), ("y", 20), ("z", 10)):
                    near(
                        measured["metrics"]["centroid_mm"][axis],
                        expected,
                        "centroid changed",
                    )
                hole = self.circle(a, radius=4, x=10, y=20)
                profile = hole["sketch"]["sketch_id"]
                observed = self.command(
                    "sketch",
                    "inspect",
                    profile,
                    document=a,
                    session=self.session + "-observer",
                )
                require(
                    observed["editing"] is False
                    and observed["geometry_complete"] is True
                    and observed["sketch"]["absorbed"] is False
                    and observed["profile_segment_count"] == 1
                    and observed["segments"][0]["geometry"]["complete_circle"] is True,
                    "read-only profile observation failed",
                )
                near(
                    observed["segments"][0]["geometry"]["radius_mm"],
                    4,
                    "observed radius changed",
                )
                require(
                    observed["document"]["update_stamp"]
                    == hole["document"]["update_stamp"],
                    "read-only profile observation changed update stamp",
                )
                self.background(observed, a)
                cut = self.feature(a, profile, cut=True, depth=20)
                self.background(cut, a)
                near(
                    cut["geometry_verification"]["volume_removed_mm3"],
                    320 * math.pi,
                    "blind cut removed the wrong material",
                )
                near(
                    cut["measurement_after"]["surface_area_mm2"],
                    16000 + 128 * math.pi,
                    "blind cut surface area changed",
                )
                absorbed = self.command(
                    "sketch",
                    "inspect",
                    profile,
                    document=a,
                    session=self.session + "-observer",
                )
                require(
                    absorbed["editing"] is False
                    and absorbed["geometry_complete"] is True
                    and absorbed["sketch"]["absorbed"] is True
                    and absorbed["sketch"]["owner"]["name"] == cut["feature"]["name"]
                    and absorbed["document"]["update_stamp"]
                    == cut["document"]["update_stamp"],
                    "absorbed profile lost its exact owner or changed update stamp",
                )
                self.background(absorbed, a)
                feature_ids = self.observe_features(
                    a, bosses=1, cuts=1, background=True
                )
                require(
                    set(feature_ids)
                    == {
                        extrusion["feature"]["feature_id"],
                        cut["feature"]["feature_id"],
                    },
                    "live discovery did not reuse the exact created feature handles",
                )
                limited = self.command(
                    "feature",
                    "list",
                    "--max-features",
                    1,
                    document=a,
                    session=self.session + "-observer",
                    expected_error="FeatureListLimitExceeded",
                )
                require(
                    "features" not in limited,
                    "limited feature read exposed a partial list",
                )
                self.write(
                    "feature",
                    "cut-extrude",
                    profile,
                    "--depth-mm",
                    20,
                    document=a,
                    expected_error="SketchUnavailable",
                )
        require(
            len(set(sketches)) == 3,
            "rectangle sketches did not receive distinct handles",
        )
        for plane in ("front", "top", "right"):
            circle = self.circle(a, plane, 8, 120, 20)
            self.background(circle, a)
            extrusion = self.feature(
                a, circle["sketch"]["sketch_id"], depth=20, merge=False
            )
            self.background(extrusion, a)
        foreground = self.command("document", "inspect")["document"]
        require(
            foreground["document_id"] == b
            and foreground["active"] is True
            and foreground["current"] is True,
            "foreground part was not restored",
        )
        metrics = self.measure(a)["metrics"]
        native = str(PureWindowsPath(self.host_directory) / "model.SLDPRT")
        saved = self.write("document", "save-as", native, document=a)
        self.background(saved, a)
        require(
            saved["document"]["modified"] is False
            and bool(saved["document"]["path"])
            and saved["file_verification"]["minimum_size_valid"] is True,
            "native save-as left an invalid document/file state",
        )
        status = self.command("document", "lease", "status", document=a)
        require(status["lease"]["lease_id"] == lease, "save-as lost its document lease")
        local_model = self.directory / "model.SLDPRT"
        require(
            local_model.is_file() and local_model.stat().st_size > 0,
            "daemon-visible output did not produce a local native artifact",
        )
        self.verify_in_place_save(a, local_model)
        digest = hashlib.sha256(local_model.read_bytes()).hexdigest()
        self.write(
            "document",
            "save-as",
            native,
            document=a,
            expected_error="OutputExists",
        )
        require(
            hashlib.sha256(local_model.read_bytes()).hexdigest() == digest,
            "save-as modified an existing native target",
        )
        self.write(
            "feature",
            "extrude",
            sketches[0],
            "--depth-mm",
            20,
            document=a,
            expected_error="SketchUnavailable",
        )
        self.command("document", "lease", "release", lease)
        self.close(a)
        reopened = self.command(
            "document", "open", native, "--read-only", session=self.session + "-reopen"
        )["document"]["document_id"]
        require(reopened != a, "reopen reused an expired document ID")
        structure = self.command(
            "document", "inspect", "--detail", "structure", document=reopened
        )["structure"]
        require(
            structure["bodies"]["count"] == extrusion["bodies"]["count"],
            "native save/reopen changed solid body count",
        )
        self.measure(
            reopened, volume=metrics["volume_mm3"], area=metrics["surface_area_mm2"]
        )
        reopened_ids = self.observe_features(reopened, bosses=6, cuts=1)
        require(
            not set(feature_ids) & set(reopened_ids),
            "native close/reopen reused retired feature handles",
        )
        self.command(
            "feature",
            "inspect",
            feature_ids[0],
            document=reopened,
            expected_error="FeatureNotFound",
        )
        diagnosis = self.command("document", "diagnose", document=reopened)
        require(
            diagnosis["diagnostics"]["healthy"] is True
            and diagnosis["needs_rebuild"] == 0,
            "saved/reopened model has feature or rebuild diagnostics",
        )
        self.close(reopened)
        current = self.command("document", "inspect")["document"]
        require(
            current["document_id"] == b and current["current"] is True,
            "independent reopen session changed the original session current",
        )
        self.close(b)

    def observe_faces(self, document, *, depth, hole_depth, background, repeat=False):
        """Reuse the depth fixture; reads have no write token or activation."""
        observer = self.session + "-entity-reader"
        self.renew(document)
        before = self.command(
            "document", "inspect", document=document, session=observer
        )["document"]
        listed = self.command("entity", "list", document=document, session=observer)
        validate_operation_result("entity.list", listed)
        faces = listed["entities"]
        require(
            listed["face_count"] == 8 and len(faces) == 8,
            "depth fixture face enumeration is incomplete",
        )
        planes = [face for face in faces if face["surface_kind"] == "plane"]
        cylinders = [face for face in faces if face["surface_kind"] == "cylinder"]
        require(
            len(planes) == 7 and len(cylinders) == 1,
            "depth fixture analytic face classification changed",
        )
        remaining_planes = [
            (0, 1, 60),
            (0, -1, -40),
            (1, 1, 45),
            (1, -1, -5),
            (2, 1, depth),
            (2, -1, 0),
            (2, -1, hole_depth),
        ]
        for face in planes:
            plane = face["surface_geometry"]["plane"]
            normal = plane["outward_normal"]
            axis = max(range(3), key=lambda index: abs(normal[index]))
            require(
                abs(abs(normal[axis]) - 1) < 1e-9
                and all(
                    abs(value) <= 1e-9
                    for index, value in enumerate(normal)
                    if index != axis
                ),
                "fixture plane has a non-axis outward normal",
            )
            position = plane["point_mm"][axis]
            matches = [
                index
                for index, (expected_axis, sign, location) in enumerate(
                    remaining_planes
                )
                if axis == expected_axis
                and (1 if normal[axis] > 0 else -1) == sign
                and abs(position - location) <= 1e-5
            ]
            require(
                len(matches) == 1,
                "fixture plane set has a missing, repeated or misplaced face",
            )
            remaining_planes.pop(matches[0])
        require(not remaining_planes, "fixture plane set is incomplete")
        cylinder = cylinders[0]["surface_geometry"]["cylinder"]
        near(cylinder["radius_mm"], 3, "native cylinder radius changed")
        for value, expected in zip(cylinder["axis_point_mm"][:2], (10, 20)):
            near(value, expected, "native cylinder axis moved")
        near(abs(cylinder["axis_direction"][2]), 1, "native cylinder axis tilted")
        if repeat:
            repeated = self.command(
                "entity", "list", document=document, session=observer
            )
            validate_operation_result("entity.list", repeated)
            require(
                repeated == listed, "read-only repeat changed IDs, geometry or state"
            )
        for face in (planes[0], cylinders[0]):
            self.renew(document)
            inspected = self.command(
                "entity",
                "inspect",
                face["entity_id"],
                document=document,
                session=observer,
            )
            validate_operation_result("entity.inspect", inspected)
            require(
                inspected["entity"] == face,
                "exact entity inspection changed its binding",
            )
            if background:
                self.background(inspected, document)
        if background:
            self.background(listed, document)
        self.renew(document)
        require(
            self.command("document", "inspect", document=document, session=observer)[
                "document"
            ]
            == before,
            "entity reads changed native document or foreground/current state",
        )
        return [face["entity_id"] for face in faces]

    def observe_edges(self, document, *, depth, hole_depth, background, face_id, repeat=False):
        """Observe the same fixture through the installed CLI, without a lease."""
        observer = self.session + "-entity-reader"
        self.renew(document)
        before = self.command("document", "inspect", document=document, session=observer)["document"]
        listed = self.command("entity", "list", "--kind", "edge", document=document, session=observer)
        validate_operation_result("entity.list", listed)
        require(listed["edge_count"] == 14, "fixture edge count changed")
        edges = listed["entities"]
        verify_fixture_edges(edges, depth=depth, hole_depth=hole_depth)
        if repeat:
            self.renew(document)
            repeated = self.command("entity", "list", "--kind", "edge", document=document, session=observer)
            validate_operation_result("entity.list", repeated)
            require(
                {key: value for key, value in repeated.items() if key != "entities"}
                == {key: value for key, value in listed.items() if key != "entities"}
                and {e["entity_id"]: e for e in repeated["entities"]}
                == {e["entity_id"]: e for e in edges},
                "edge repeat changed IDs, geometry or state",
            )
        for kind in ("line", "circle"):
            edge = next(e for e in edges if e["curve_kind"] == kind)
            self.renew(document)
            inspected = self.command("entity", "inspect", edge["entity_id"], "--kind", "edge",
                                     document=document, session=observer)
            validate_operation_result("entity.inspect", inspected)
            require(inspected["entity"] == edge, "exact edge inspection changed its binding")
            if background:
                self.background(inspected, document)
        # Discovering edges must not evict the same-scope face registry.
        self.renew(document)
        face = self.command("entity", "inspect", face_id, document=document, session=observer)
        validate_operation_result("entity.inspect", face)
        require(face["entity"]["entity_id"] == face_id, "edge discovery evicted a live face ID")
        self.command("entity", "inspect", edges[0]["entity_id"], document=document,
                     session=observer, expected_error="EntityNotFound")
        self.command("entity", "inspect", face_id, "--kind", "edge", document=document,
                     session=observer, expected_error="EntityNotFound")
        if background:
            self.background(listed, document)
            self.background(face, document)
        self.renew(document)
        require(self.command("document", "inspect", document=document, session=observer)["document"] == before,
                "edge reads changed native document or foreground/current state")
        return [e["entity_id"] for e in edges]

    def feature_depth(self):
        # A separate exact single-solid fixture: the main modeling case includes
        # deliberate multiple bodies and is not eligible for this narrow writer.
        a, b = self.create(), self.create()
        lease = self.command(
            "document",
            "lease",
            "acquire",
            "--ttl-seconds",
            LEASE_TTL_SECONDS,
            document=a,
        )["lease"]["lease_id"]
        rectangle = self.rectangle(a, width=100, height=50, x=10, y=20)
        boss = self.feature(a, rectangle["sketch"]["sketch_id"], depth=20)
        circle = self.circle(a, radius=3, x=10, y=20)
        cut = self.feature(a, circle["sketch"]["sketch_id"], cut=True, depth=5)
        boss_id, cut_id = boss["feature"]["feature_id"], cut["feature"]["feature_id"]
        initial_faces = self.observe_faces(
            a, depth=20, hole_depth=5, background=True, repeat=True
        )
        initial_edges = self.observe_edges(
            a, depth=20, hole_depth=5, background=True, face_id=initial_faces[0], repeat=True
        )
        require(set(initial_faces).isdisjoint(initial_edges), "face and edge IDs overlap")
        self.command("entity", "inspect", initial_edges[0], "--kind", "edge",
                     document=b, expected_error="EntityNotFound")
        self.command(
            "entity",
            "inspect",
            initial_faces[0],
            document=b,
            expected_error="EntityNotFound",
        )
        # More read-only refusal checks must not let the writer lease lapse on
        # a slow host before its next explicit renewal/write.
        self.renew(a)
        before = self.command("document", "inspect", document=a)["document"]
        self.command(
            "entity",
            "list",
            "--if-update-stamp",
            before["update_stamp"] + 1,
            document=a,
            expected_error="DocumentUpdateConflict",
        )
        self.command(
            "feature",
            "set-depth",
            boss_id,
            "--depth-mm",
            25,
            document=a,
            session=self.session + "-contender",
            expected_error="DocumentLeaseConflict",
        )
        self.command("entity", "list", "--kind", "edge", "--if-update-stamp",
                     before["update_stamp"] + 1, document=a, expected_error="DocumentUpdateConflict")
        self.write(
            "feature",
            "set-depth",
            boss_id,
            "--depth-mm",
            25,
            "--if-update-stamp",
            before["update_stamp"] + 1,
            document=a,
            expected_error="DocumentUpdateConflict",
        )
        after = self.command("document", "inspect", document=a)["document"]
        require(before == after, "refused depth writes changed document state")
        for feature_id, target, expected_volume in (
            (boss_id, 25, 125000 - math.pi * 9 * 5),
            (cut_id, 8, 125000 - math.pi * 9 * 8),
        ):
            stamp = self.command("document", "inspect", document=a)["document"][
                "update_stamp"
            ]
            changed = self.write(
                "feature",
                "set-depth",
                feature_id,
                "--depth-mm",
                target,
                "--if-update-stamp",
                stamp,
                document=a,
                timeout_seconds=self.depth_request_timeout_seconds,
            )
            self.background(changed, a)
            self.command(
                "entity",
                "inspect",
                initial_faces[0],
                document=a,
                expected_error="EntityReferenceStale",
            )
            self.command("entity", "inspect", initial_edges[0], "--kind", "edge",
                         document=a, expected_error="EntityReferenceStale")
            require(
                changed["feature_id"] == feature_id
                and changed["depth_changed"] is True
                and all(changed["mutation"].values())
                and changed["rebuilt"] is True,
                "depth write lost target or verified mutation lifecycle",
            )
            near(
                changed["definition_after"]["depth_mm"],
                target,
                "depth readback mismatch",
            )
            self.measure(a, volume=expected_volume)
            near(
                changed["measurement_after"]["volume_mm3"],
                expected_volume,
                "depth write changed the wrong material",
                abs(expected_volume) * 1e-9 + 0.00001,
            )
            equal = self.write(
                "feature",
                "set-depth",
                feature_id,
                "--depth-mm",
                target,
                "--if-update-stamp",
                changed["document"]["update_stamp"],
                document=a,
                timeout_seconds=self.depth_request_timeout_seconds,
            )
            self.background(equal, a)
            require(
                equal["depth_changed"] is False
                and not any(equal["mutation"].values())
                and "rebuilt" not in equal,
                "equal depth performed modification/rebuild",
            )
            unchanged_depth_metrics(
                changed["measurement_after"], equal["measurement_after"]
            )
            for response in (changed, equal):
                require(
                    not response.get("warnings")
                    and response["verification"]["passed"] is True,
                    "depth operation left warnings or incomplete verification",
                )
                for check in response["selection_checks"].values():
                    require(
                        check["ok"] is True and all(check["selection_access"].values()),
                        "selection access was not released/restored",
                    )
        self.command(
            "feature",
            "set-depth",
            boss_id,
            "--depth-mm",
            25,
            document=b,
            expected_error="FeatureNotFound",
        )
        before_close_faces = self.observe_faces(
            a, depth=25, hole_depth=8, background=True
        )
        before_close_edges = self.observe_edges(
            a, depth=25, hole_depth=8, background=True, face_id=before_close_faces[0]
        )
        require(
            not set(initial_faces) & set(before_close_faces),
            "depth edits silently rebound old entity IDs",
        )
        require(set(initial_faces + initial_edges).isdisjoint(before_close_faces + before_close_edges),
                "depth edits silently rebound face or edge IDs")
        native = str(PureWindowsPath(self.host_directory) / "edited-depth.SLDPRT")
        saved = self.write("document", "save-as", native, document=a)
        self.background(saved, a)
        require(
            saved["document"]["modified"] is False
            and saved["file_verification"]["minimum_size_valid"] is True,
            "edited native part did not save cleanly",
        )
        self.command("document", "lease", "release", lease)
        self.close(a)
        reopened = self.command("document", "open", native, "--read-only")["document"][
            "document_id"
        ]
        self.command(
            "entity",
            "inspect",
            before_close_faces[0],
            document=reopened,
            expected_error="EntityNotFound",
        )
        reopened_faces = self.observe_faces(
            reopened, depth=25, hole_depth=8, background=False
        )
        self.command("entity", "inspect", before_close_edges[0], "--kind", "edge",
                     document=reopened, expected_error="EntityNotFound")
        reopened_edges = self.observe_edges(
            reopened, depth=25, hole_depth=8, background=False, face_id=reopened_faces[0]
        )
        require(
            not set(before_close_faces) & set(reopened_faces),
            "native reopen reused expired entity IDs",
        )
        require(set(initial_faces + initial_edges + before_close_faces + before_close_edges)
                .isdisjoint(reopened_faces + reopened_edges), "native reopen reused expired face or edge IDs")
        self.record["entity_observation"] = {
            "verified": True,
            "face_count": 8,
            "planes": 7,
            "cylinders": 1,
            "edge_count": 14,
            "lines": 12,
            "circles": 2,
            "mixed_kind_ids_preserved": True,
            "wrong_kind_rejected": True,
            "edge_cas_rejected": True,
            "repeat_ids_preserved": True,
            "changed_scope_rejected": True,
            "reopen_ids_fresh": True,
            "leased_background_read_unchanged": True,
        }
        features = self.command("feature", "list", document=reopened)["features"]
        require(
            len(features) == 2
            and {f["kind"] for f in features} == {"boss-extrude", "cut-extrude"}
            and not {boss_id, cut_id} & {f["feature_id"] for f in features},
            "native reopen lost features or reused expired handles",
        )
        for feature in features:
            observed = self.command(
                "feature", "inspect", feature["feature_id"], document=reopened
            )
            near(
                observed["definition"]["depth_mm"],
                25 if feature["kind"] == "boss-extrude" else 8,
                "saved native depth did not persist",
            )
        state = self.command("document", "inspect", document=reopened)["document"]
        refused = self.command(
            "feature",
            "set-depth",
            features[0]["feature_id"],
            "--depth-mm",
            26,
            document=reopened,
            expected_error="DocumentNotWritable",
        )
        require(
            not any(refused["mutation"].values())
            and not any(
                refused["selection_checks"]["preflight"]["selection_access"].values()
            ),
            "read-only refusal attempted mutation or selection access",
        )
        require(
            self.command("document", "inspect", document=reopened)["document"] == state,
            "read-only refusal changed the reopened document",
        )
        self.measure(reopened, volume=125000 - math.pi * 9 * 8)
        self.close(reopened)
        self.close(b)

    def reverse_cut(self):
        document = self.create()
        rectangle = self.rectangle(document)
        self.feature(document, rectangle["sketch"]["sketch_id"], reverse=True)
        circle = self.circle(document, radius=3)
        cut = self.feature(
            document, circle["sketch"]["sketch_id"], cut=True, reverse=True
        )
        near(
            cut["geometry_verification"]["volume_removed_mm3"],
            90 * math.pi,
            "reverse cut removed the wrong material",
        )
        self.close(document)

    def sample_exports(self, part, assembly):
        document = self.command("document", "open", part, "--read-only")["document"][
            "document_id"
        ]
        stamp = self.command("document", "inspect", document=document)["document"][
            "update_stamp"
        ]
        require(
            type(stamp) is int, "GetUpdateStamp unavailable on the installed sample"
        )
        lease = self.command(
            "document",
            "lease",
            "acquire",
            "--ttl-seconds",
            LEASE_TTL_SECONDS,
            document=document,
        )["lease"]["lease_id"]
        denied = str(PureWindowsPath(self.host_directory) / "lease-denied.STEP")
        self.command(
            "document",
            "export",
            "--document",
            document,
            denied,
            session=self.session + "-contender",
            expected_error="DocumentLeaseConflict",
        )
        require(
            not (self.directory / "lease-denied.STEP").exists(),
            "denied export created an artifact",
        )
        self.renew(document)
        self.command(
            "document",
            "export",
            "--document",
            document,
            str(PureWindowsPath(self.host_directory) / "leased.STEP"),
            lease=lease,
        )
        self.verify_step("leased.STEP")
        self.command("document", "lease", "release", lease)
        foreground = self.command("document", "open", assembly, "--read-only")[
            "document"
        ]["document_id"]
        self.command(
            "document",
            "export",
            "--document",
            document,
            str(PureWindowsPath(self.host_directory) / "multi-document.STEP"),
        )
        self.verify_step("multi-document.STEP")
        documents = self.command("document", "list")
        by_id = {item["document_id"]: item for item in documents["documents"]}
        self.background({"document": by_id[document]}, document)
        require(
            by_id[foreground]["active"] is True
            and by_id[foreground]["current"] is True,
            "background export did not restore the foreground assembly",
        )
        self.close(foreground)
        self.close(document)
        self.assembly_save_reopen(assembly)

    def assembly_save_reopen(self, assembly):
        # Rename only the assembly into the evidence directory. Referenced
        # parts remain at their original paths: this is not Pack and Go.
        opened = self.command("document", "open", assembly)
        document = opened["document"]["document_id"]
        require(opened["document"]["type"] == 2, "sample is not an assembly")
        before = self.command(
            "document", "inspect", "--detail", "structure", document=document
        )["structure"]

        def signature(structure):
            features = structure["features"]
            require(features["count"] > 0 and not features["truncated"],
                    "assembly feature tree is empty or truncated")
            return {
                "configurations": structure["configurations"],
                "features": [(item["name"], item["type"]) for item in features["items"]],
            }

        expected = signature(before)
        target = str(PureWindowsPath(self.host_directory) / "assembly.SLDASM")
        saved = self.write("document", "save-as", target, document=document)
        require(saved["document"]["document_id"] == document
                and saved["document"]["modified"] is False
                and saved["artifact"]["format"] == "SLDASM"
                and saved["file_verification"]["minimum_size_valid"] is True,
                "assembly save-as left an invalid document/file state")
        native_file = self.directory / "assembly.SLDASM"
        require(native_file.is_file() and native_file.stat().st_size >= 512,
                "assembly save-as produced an empty or truncated file")
        save_as_bytes = native_file.stat().st_size
        require(saved["artifact"]["size_bytes"] == save_as_bytes,
                "assembly save-as size evidence disagrees with the artifact")
        # Also exercise Save3 on the new file, never on the installed sample.
        self.verify_in_place_save(document, native_file)
        digest = hashlib.sha256(native_file.read_bytes()).hexdigest()
        self.close(document)
        reopened = self.command("document", "open", target, "--read-only")
        reopened_id = reopened["document"]["document_id"]
        require(reopened_id != document and reopened["document"]["type"] == 2
                and reopened["read_only"] is True and reopened["api_errors"] == 0,
                "saved assembly did not reopen as a fresh read-only assembly")
        after = self.command(
            "document", "inspect", "--detail", "structure", document=reopened_id
        )["structure"]
        require(signature(after) == expected,
                "assembly save/reopen changed configurations or feature tree")
        self.close(reopened_id)
        require(hashlib.sha256(native_file.read_bytes()).hexdigest() == digest,
                "read-only assembly reopen changed the saved artifact")
        self.record["assembly_save_reopen"] = {
            "save_as_bytes": save_as_bytes,
            "size_bytes": native_file.stat().st_size,
            "sha256": digest,
            "structure_unchanged": True,
            "fresh_document_id": True,
        }
        self.checkpoint("assembly-save-reopen.verified")

    def verify_in_place_save(self, document, native_file):
        kind = {".SLDASM": "assembly", ".SLDDRW": "drawing", ".SLDPRT": "part"}[
            native_file.suffix.upper()
        ]
        saved = self.write("document", "save", document=document)
        require(saved["api_saved"] is True and saved["save_errors"] == 0
                and saved["document_after"]["modified"] is False,
                f"{kind} in-place save failed")
        require(native_file.is_file() and native_file.stat().st_size >= 512,
                f"{kind} in-place save produced an empty or truncated file")
        self.record.setdefault("native_in_place_saves", []).append({
            "format": native_file.suffix[1:].upper(),
            "size_bytes": native_file.stat().st_size,
        })

    def drawing_save_reopen(self, drawing, local_drawing, *,
                            work_directory=None, host_work_directory=None):
        # Only Save3 a new byte-for-byte copy. The installed source is opened
        # read-only for the baseline; this is not a drawing SaveAs or Pack and Go.
        source = Path(local_drawing)
        require(source.is_file() and source.suffix.lower() == ".slddrw",
                "drawing source must be a readable local SLDDRW file")
        source_bytes = source.read_bytes()
        require(len(source_bytes) >= 512, "drawing source is empty or truncated")
        source_digest = hashlib.sha256(source_bytes).hexdigest()
        require((work_directory is None) == (host_work_directory is None),
                "drawing work directories must supply both path namespaces")
        work_directory = (Path(work_directory).expanduser().resolve()
                          if work_directory is not None else self.directory)
        require(work_directory.is_dir(), "drawing work directory does not exist")
        host_work_directory = (self.host_directory if host_work_directory is None
                               else host_work_directory)
        host_directory(host_work_directory)
        native_file = work_directory / "drawing.SLDDRW"
        target = str(PureWindowsPath(host_work_directory) / native_file.name)
        evidence_file = self.directory / native_file.name
        proof = {
            "source": drawing,
            "source_sha256_before": source_digest,
            "observation_scope": "top-level-feature-tree",
            "work_path": target,
            "opens": [],
        }
        self.record["drawing_save_reopen"] = proof

        def open_checked(path, *, read_only):
            result = self.command("document", "open", path,
                                  *(("--read-only",) if read_only else ()))
            proof["opens"].append({
                "path": path, "read_only": result["read_only"],
                "api_errors": result["api_errors"],
                "api_warnings": result["api_warnings"],
            })
            require(result["document"]["type"] == 3
                    and result["read_only"] is read_only
                    and result["api_errors"] == 0,
                    "drawing did not open with the required type/read-only state")
            # swFileLoadWarning_ReadOnly = 2 is expected only for explicit
            # read-only opens. All other warnings (including lost references)
            # fail the gate rather than silently weakening the reopen proof.
            require(result["api_warnings"] in ((0, 2) if read_only else (0,)),
                    f"drawing open has unexpected warnings: {result['api_warnings']}")
            return result["document"]["document_id"]

        def signature(document):
            structure = self.command("document", "inspect", "--detail", "structure",
                                     document=document)["structure"]
            features = structure["features"]
            require(features["count"] > 0 and not features["truncated"],
                    "drawing feature tree is empty or truncated")
            return [(item["name"], item["type"]) for item in features["items"]]

        try:
            original = open_checked(drawing, read_only=True)
            expected = signature(original)
            self.close(original)
            with native_file.open("xb") as stream:
                stream.write(source_bytes)
            document = open_checked(target, read_only=False)
            require(signature(document) == expected,
                    "drawing copy changed the source feature tree")
            self.verify_in_place_save(document, native_file)
            proof["size_bytes"] = native_file.stat().st_size
            digest = hashlib.sha256(native_file.read_bytes()).hexdigest()
            self.close(document)
            reopened = open_checked(target, read_only=True)
            require(reopened != document, "drawing reopen reused an expired document ID")
            require(signature(reopened) == expected,
                    "drawing save/reopen changed the feature tree")
            self.close(reopened)
            require(hashlib.sha256(native_file.read_bytes()).hexdigest() == digest,
                    "read-only drawing reopen changed the saved artifact")
            proof.update(sha256=digest, structure_unchanged=True, fresh_document_id=True)
        finally:
            proof["source_sha256_after"] = hashlib.sha256(source.read_bytes()).hexdigest()
            require(proof["source_sha256_after"] == source_digest,
                    "drawing gate changed the installed source")
        # Keep reference bundles outside the evidence tree. Publish only after
        # all checks, including source protection, without replacing evidence.
        # The host adapter owns fixture preparation and cleanup on every exit.
        if native_file.resolve() != evidence_file.resolve():
            verified_bytes = native_file.read_bytes()
            require(hashlib.sha256(verified_bytes).hexdigest() == digest,
                    "drawing changed before copying verified evidence")
            stream = evidence_file.open("xb")  # Failure here never owns an existing file.
            try:
                with stream:
                    stream.write(verified_bytes)
            except Exception:
                evidence_file.unlink()  # Remove only this call's incomplete copy.
                raise
        proof["evidence_path"] = str(evidence_file)
        self.checkpoint("drawing-save-reopen.verified")

    def verify_step(self, name):
        path = self.directory / name
        require(
            path.is_file() and b"ISO-10303-21" in path.read_bytes()[:512],
            f"export did not produce a valid local STEP file: {path}",
        )

    def rejected_cut_then_sketch(self):
        document = self.create()
        rectangle = self.rectangle(document)
        self.feature(document, rectangle["sketch"]["sketch_id"])
        circle = self.circle(document, x=1000)
        profile = circle["sketch"]["sketch_id"]
        rejected = self.command(
            "feature",
            "cut-extrude",
            profile,
            "--depth-mm",
            10,
            document=document,
            expected_error="CutExtrusionFailed",
        )
        require(
            rejected.get("warnings", []) == [],
            "native cut rejection reported cleanup warnings",
        )
        self.command("document", "inspect", document=document)
        observed = self.command("sketch", "inspect", profile, document=document)
        require(
            observed["editing"] is False,
            "rejected cut left sketch editing active or unknown",
        )
        measured = self.measure(document, volume=12000)
        require(
            measured["metrics"]["solid_body_count"] == 1,
            "rejected cut changed solid count",
        )
        self.close(document)
        self.require_empty()
        # Same sequence as the first driving case: a new background circle.
        # Do not restart or retry when InsertSketch fails after the native cut.
        background, foreground = self.create(), self.create()
        recovered = self.circle(background, radius=8, x=3, y=4)
        self.background(recovered, background)
        active = self.command("document", "inspect")["document"]
        require(
            active["document_id"] == foreground and active["active"] is True,
            "post-rejection sketch did not restore its foreground document",
        )
        self.close(background)
        self.close(foreground)

    def require_empty(self):
        result = self.command("document", "list")
        require(
            result["count"] == 0 and result["documents"] == [],
            "native open documents remain; the gate requires an isolated empty host",
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
            sample_drawing=None, sample_drawing_local=None,
            drawing_work_dir=None, host_drawing_work_dir=None):
        self.record["host"] = self.health()["host"]
        self.command(
            "capabilities"
        )  # The client validates the real capabilities Schema.
        self.require_empty()
        cases = [
            ("native-model", self.native_model),
            ("reverse-cut", self.reverse_cut),
            ("feature-depth", self.feature_depth),
        ]
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
        cases.append(("rejected-cut-then-sketch", self.rejected_cut_then_sketch))
        for name, function in cases:
            self.checkpoint(name + ".starting")
            function()
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
    parser.add_argument("--sample-assembly", type=host_directory)
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
    )
    # Never overwrite prior evidence, even before the first host operation.
    with smoke.record_path.open("x", encoding="utf-8") as stream:
        json.dump(smoke.record, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    error = None
    try:
        smoke.run(
            sample_part=arguments.sample_part, sample_assembly=arguments.sample_assembly,
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
