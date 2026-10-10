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
        self.command(
            "entity",
            "inspect",
            initial_faces[0],
            document=b,
            expected_error="EntityNotFound",
        )
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
        require(
            not set(initial_faces) & set(before_close_faces),
            "depth edits silently rebound old entity IDs",
        )
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
        require(
            not set(before_close_faces) & set(reopened_faces),
            "native reopen reused expired entity IDs",
        )
        self.record["entity_observation"] = {
            "verified": True,
            "face_count": 8,
            "planes": 7,
            "cylinders": 1,
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

    def run(self, *, sample_part=None, sample_assembly=None):
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
    arguments = parser.parse_args(argv)
    if bool(arguments.sample_part) != bool(arguments.sample_assembly):
        parser.error("sample-part and sample-assembly must be supplied together")
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
            sample_part=arguments.sample_part, sample_assembly=arguments.sample_assembly
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
