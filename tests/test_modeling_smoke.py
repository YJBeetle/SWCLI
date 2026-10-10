"""Portable contract tests for the gate, not proof of native CAD behavior."""

import copy
import importlib.util
import io
import json
import math
from itertools import combinations, product
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import unittest
from unittest import mock

from swcli.cli import build_parser, _typed_payload

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/verify-modeling.py"
spec = importlib.util.spec_from_file_location("modeling_smoke", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class FakeCLI:
    def __init__(self, directory):
        self.directory = directory
        self.parser = build_parser()
        self.documents = {}
        self.current = {}
        self.active = None
        self.serial = 0
        self.saved = {}
        self.calls = []
        self.rejected = False
        self.defect = None
        self.health_calls = 0
        self.feature_ids = {}
        self.entity_ids = {}
        self.edge_reads = 0
        self.now = 0
        self.operation_seconds = 0

    def descriptor(self, document, session):
        return {
            "title": document["id"],
            "document_id": document["id"],
            "path": document["path"],
            "type": document.get("type", 1),
            "modified": document["modified"],
            "update_stamp": document["stamp"],
            "active": self.active == document["id"],
            "current": self.current.get(session) == document["id"],
        }

    @staticmethod
    def failure(code, **extra):
        return {
            "ok": False,
            "error": {"type": code, "message": "native reason"},
            **extra,
        }

    def run(self, command, **kwargs):
        # Parse real generated command lines, including options before paths.
        start = command.index("--endpoint")
        args = self.parser.parse_args(command[start:])
        self.calls.append(args)
        self.now += self.operation_seconds
        for document in self.documents.values():
            if document["lease"] and document["lease"]["expires_at"] <= self.now:
                document["lease"] = None
        result = self.dispatch(args)
        if args.command not in ("daemon", "capabilities"):
            result = _typed_payload(
                f"{args.command}.{getattr(args, args.command + '_command', '')}",
                {"result": result, "request_id": f"smoke-{len(self.calls)}"},
            )
        return subprocess.CompletedProcess(
            command,
            1 if result.get("ok") is False else 0,
            json.dumps(result, ensure_ascii=False).encode("utf-8"),
            b"native stderr\n",
        )

    def dispatch(self, args):
        session = args.session
        action = args.command
        subcommand = getattr(args, action + "_command", None)
        if action in ("capabilities", "daemon"):
            self.health_calls += 1
            health = {
                "host_connected": self.defect != "disconnected",
                "recovery_required": False,
                "host": {
                    "process_id": (
                        124
                        if self.defect == "host-replaced" and self.health_calls > 2
                        else 123
                    )
                },
            }
            return (
                health
                if action == "capabilities"
                else {"success": True, "result": health}
            )
        if action == "document" and subcommand in ("create", "open"):
            self.serial += 1
            document_id = f"d-{self.serial:06x}"
            if subcommand == "open":
                document = copy.deepcopy(
                    self.saved.get(
                        args.path,
                        {
                            "profiles": {},
                            "count": 1,
                            "volume": 12000,
                            "area": 8000,
                            "stamp": 1,
                            "modified": False,
                            "lease": None,
                        },
                    )
                )
                document["path"] = args.path
                document["lease"] = None
            else:
                document = {
                    "path": "",
                    "stamp": 1,
                    "modified": False,
                    "profiles": {},
                    "count": 0,
                    "volume": 0,
                    "area": 0,
                    "lease": None,
                }
            document["id"] = document_id
            document.setdefault("type", {".sldasm": 2, ".slddrw": 3}.get(
                gate.PureWindowsPath(args.path).suffix.lower(), 1)
                if subcommand == "open" else 1)
            if self.defect == "assembly-reopen-failed" and subcommand == "open" and args.path.endswith("assembly.SLDASM"):
                return self.failure("OpenFailed")
            document["read_only"] = args.read_only if subcommand == "open" else False
            if document["type"] == 3 and args.path.endswith("drawing.SLDDRW") and args.read_only:
                if self.defect == "drawing-reopen-failed":
                    return self.failure("OpenFailed")
                if self.defect == "drawing-reopen-changed-file":
                    (self.directory / "drawing.SLDDRW").write_bytes(b"changed" * 100)
                if self.defect == "drawing-reused-id":
                    document_id = document["id"] = "d-000002"
                if self.defect == "drawing-readonly-missing":
                    document["read_only"] = False
            self.documents[document_id] = document
            self.active = self.current[session] = document_id
            return {
                "ok": True,
                "created": True,
                "read_only": document["read_only"],
                "api_errors": (1 if self.defect == "drawing-open-error"
                               and document["type"] == 3 else 0),
                "api_warnings": (4 if self.defect == "drawing-reference-warning"
                                 and document["type"] == 3 else
                                 2 if self.defect == "drawing-writable-warning"
                                 and document["type"] == 3 and not args.read_only else
                                 2 if self.defect == "drawing-readonly-warning"
                                 and document["type"] == 3 and args.read_only else 0),
                "document": self.descriptor(document, session),
            }
        if action == "document" and subcommand == "list":
            documents = [
                self.descriptor(document, session)
                for document in self.documents.values()
            ]
            if self.defect == "close-no-op" and self.rejected:
                documents.append({"document_id": "d-orphan"})
            return {"ok": True, "count": len(documents), "documents": documents}
        document_id = getattr(args, "document_id", None) or self.current.get(session)
        if (
            action == "document"
            and subcommand == "lease"
            and args.lease_command in ("renew", "release")
        ):
            document_id = next(
                (
                    key
                    for key, value in self.documents.items()
                    if value["lease"] and value["lease"]["lease_id"] == args.lease_id
                ),
                None,
            )
            if document_id is None:
                return self.failure("DocumentLeaseNotFound")
        document = self.documents[document_id]
        descriptor = self.descriptor(document, session)
        if action == "document" and subcommand == "lease":
            if args.lease_command == "acquire":
                document["lease"] = {
                    "lease_id": "l-0123456789ab",
                    "session": session,
                    "expires_at": self.now + args.ttl_seconds,
                }
            elif args.lease_command == "renew":
                document["lease"]["expires_at"] = self.now + args.ttl_seconds
            result = {"ok": True, "lease": copy.deepcopy(document["lease"])}
            if args.lease_command == "release":
                document["lease"] = None
            return result
        if getattr(args, "lease_id", None) is not None and (
            not document["lease"] or document["lease"]["lease_id"] != args.lease_id
        ):
            return self.failure("DocumentLeaseNotFound")
        if action == "document" and subcommand == "close":
            self.documents.pop(document_id)
            if self.active == document_id:
                self.active = next(reversed(self.documents), None)
            for owner, current in list(self.current.items()):
                if current == document_id:
                    self.current[owner] = None
            return {"ok": True}
        if action == "document" and subcommand == "inspect":
            if self.defect == "null-stamp":
                descriptor["update_stamp"] = None
            structure = {"bodies": {"count": document["count"]}}
            if document.get("type") == 2:
                structure.update({
                    "configurations": {"names": ["Default"], "active": "Default"},
                    "features": {"count": 1, "truncated": False, "items": [{"name": "Component1", "type": "Reference"}]},
                })
                if self.defect == "assembly-structure-changed" and document["path"].endswith("assembly.SLDASM"):
                    structure["features"]["items"][0]["name"] = "LostComponent"
            if document.get("type") == 3:
                structure["features"] = {"count": 1, "truncated": False,
                                         "items": [{"name": "Sheet1", "type": "DrawingSheet"}]}
                if document["read_only"] and document["path"].endswith("drawing.SLDDRW"):
                    if self.defect == "drawing-structure-changed":
                        structure["features"]["items"][0]["name"] = "LostSheet"
                    if self.defect == "drawing-structure-truncated":
                        structure["features"]["truncated"] = True
                    if self.defect == "drawing-structure-empty":
                        structure["features"].update(count=0, items=[])
            return {
                "ok": True,
                "document": descriptor,
                "structure": structure,
            }
        if action == "document" and subcommand == "save":
            target = self.directory / gate.PureWindowsPath(document["path"]).name
            if self.defect == "assembly-save-truncated" and target.suffix == ".SLDASM" or self.defect == "part-save-truncated" and target.suffix == ".SLDPRT":
                target.write_bytes(b"truncated")
            if document.get("type") == 3:
                if self.defect == "drawing-save-failed":
                    return self.failure("SaveFailed")
                if self.defect == "drawing-save-truncated":
                    target.write_bytes(b"truncated")
                if self.defect == "drawing-source-changed":
                    self.drawing_source.write_bytes(b"changed" * 100)
            return {"ok": True, "api_saved": True, "save_errors": 0,
                    "document_after": self.descriptor(document, session)}
        if action == "document" and subcommand == "diagnose":
            return {"ok": True, "needs_rebuild": 0, "diagnostics": {"healthy": True}}
        if action == "document" and subcommand == "measure":
            volume = document["volume"]
            if self.defect == "rejected-volume" and self.rejected:
                volume += 100
            return {
                "ok": True,
                "document": descriptor,
                "metrics": {
                    "solid_body_count": document["count"],
                    "volume_mm3": volume,
                    "surface_area_mm2": document["area"],
                    "centroid_mm": {"x": 10, "y": 20, "z": 10},
                },
            }
        if (
            getattr(args, "expected_update_stamp", None) is not None
            and args.expected_update_stamp != document["stamp"]
        ):
            return self.failure("DocumentUpdateConflict")
        if (
            document["lease"]
            and document["lease"]["session"] != session
            and not (action == "sketch" and subcommand == "inspect")
            and not (action == "feature" and subcommand in ("list", "inspect"))
            and not (action == "entity" and subcommand in ("list", "inspect"))
        ):
            return self.failure("DocumentLeaseConflict")
        if action == "entity":
            key = (document_id, document["stamp"], args.kind)
            if subcommand == "inspect":
                tokens = self.entity_ids.get(key, [])
                if args.entity_id not in tokens:
                    old = any(
                        args.entity_id in ids
                        for (owner, stamp, _), ids in self.entity_ids.items()
                        if owner == document_id and stamp != document["stamp"]
                    )
                    if old and args.kind == "edge" and self.defect == "edge-accepts-stale":
                        return {"ok": True}
                    return self.failure(
                        "EntityReferenceStale" if old else "EntityNotFound"
                    )
            elif key not in self.entity_ids:
                self.entity_ids[key] = []
                for _ in range(14 if args.kind == "edge" else 8):
                    self.serial += 1
                    self.entity_ids[key].append(f"e-{self.serial:06x}")
                if args.kind == "edge" and document["path"] and self.defect == "edge-reuses-reopened-ids":
                    previous = next((
                        ids for (owner, _, kind), ids in self.entity_ids.items()
                        if owner != document_id and kind == "edge"
                    ), None)
                    if previous:
                        self.entity_ids[key] = list(previous)
            profiles = list(document["profiles"].values())
            depth = next(
                profile["depth"] for profile in profiles if not profile["radius"]
            )
            hole = next(profile["depth"] for profile in profiles if profile["radius"])
            if args.kind == "edge":
                return self.edge_result(args, document, descriptor, key, depth, hole)
            planes = [
                ([1, 0, 0], [60, 0, 0]),
                ([-1, 0, 0], [-40, 0, 0]),
                ([0, 1, 0], [0, 45, 0]),
                ([0, -1, 0], [0, -5, 0]),
                ([0, 0, 1], [0, 0, depth]),
                ([0, 0, -1], [0, 0, 0]),
                ([0, 0, -1], [0, 0, hole]),
            ]
            faces = [
                {
                    "entity_id": token,
                    "kind": "face",
                    "surface_kind": "plane",
                    "area_mm2": 1000.0,
                    "area_accuracy": "approximate",
                    "surface_geometry": {
                        "available": True,
                        "coordinate_system": "part-model",
                        "boundary": "untrimmed-surface",
                        "face_normal_opposes_surface": False,
                        "plane": {
                            "point_mm": point,
                            "surface_normal": normal,
                            "outward_normal": normal,
                        },
                    },
                }
                for token, (normal, point) in zip(self.entity_ids[key], planes)
            ]
            faces.append(
                {
                    "entity_id": self.entity_ids[key][-1],
                    "kind": "face",
                    "surface_kind": "cylinder",
                    "area_mm2": 100.0,
                    "area_accuracy": "approximate",
                    "surface_geometry": {
                        "available": True,
                        "coordinate_system": "part-model",
                        "boundary": "untrimmed-surface",
                        "face_normal_opposes_surface": True,
                        "cylinder": {
                            "axis_point_mm": [10.0, 20.0, hole],
                            "axis_direction": [0.0, 0.0, -1.0],
                            "radius_mm": 3.0,
                        },
                    },
                }
            )
            state = {
                "configuration": "Default",
                "update_stamp": document["stamp"],
                "modified": document["modified"],
                "editing": False,
                "foreground_present": self.active is not None,
            }
            if self.defect == "entity-wrong-radius":
                faces[-1]["surface_geometry"]["cylinder"]["radius_mm"] = 4
            if self.defect == "entity-wrong-plane":
                faces[0]["surface_geometry"]["plane"]["point_mm"][0] = 61
            if self.defect == "entity-wrong-outward":
                faces[0]["surface_geometry"]["plane"]["outward_normal"] = [-1, 0, 0]
            if self.defect == "entity-duplicate-plane-geometry":
                for face in faces[:-1]:
                    face["surface_geometry"] = copy.deepcopy(
                        faces[1]["surface_geometry"]
                    )
            if self.defect == "entity-duplicate-cut-floor":
                faces[5]["surface_geometry"] = copy.deepcopy(
                    faces[6]["surface_geometry"]
                )
            if self.defect == "entity-tilted-plane":
                plane = faces[0]["surface_geometry"]["plane"]
                normal = [math.sqrt(1 - 1e-10), 1e-5, 0]
                plane["surface_normal"] = normal
                plane["outward_normal"] = normal
            if self.defect == "entity-reordered-faces":
                faces.reverse()
            result = {
                "ok": True,
                "action": f"entity.{subcommand}",
                "document": descriptor,
                "scope": "single-solid-part-faces",
                "body_count": 1,
                "face_count": 8,
                "observation": {
                    "before": state,
                    "after": state.copy(),
                    "unchanged": True,
                },
            }
            if subcommand == "list":
                result["entities"] = faces
            else:
                result["entity"] = next(
                    face for face in faces if face["entity_id"] == args.entity_id
                )
            if self.defect == "entity-extra-field":
                result["unexpected_geometry"] = []
            return result
        if action == "document" and subcommand in ("save-as", "export"):
            target = self.directory / gate.PureWindowsPath(args.output).name
            if target.exists():
                if self.defect == "overwrite-existing":
                    target.write_bytes(b"damaged")
                return self.failure("OutputExists")
            target.write_bytes(
                b"ISO-10303-21;" if subcommand == "export" else bytes(1024)
            )
            if self.defect == "assembly-save-as-truncated" and args.output.endswith(".SLDASM"):
                target.write_bytes(b"truncated")
            if subcommand == "save-as":
                document["path"], document["modified"] = args.output, False
                self.saved[args.output] = copy.deepcopy(document)
            return {
                "ok": True,
                "document": self.descriptor(document, session),
                "file_verification": {"minimum_size_valid": True},
                "artifact": {"format": gate.PureWindowsPath(args.output).suffix[1:].upper(), "size_bytes": target.stat().st_size},
            }
        if action == "sketch" and subcommand == "inspect":
            profile = document["profiles"][args.sketch_id]
            editing = self.defect == "editing" and self.rejected
            if self.defect == "editing-unknown" and self.rejected:
                editing = None
            return {
                "ok": True,
                "document": descriptor,
                "editing": editing,
                "geometry_complete": True,
                "profile_segment_count": 1,
                "sketch": {"absorbed": profile["absorbed"], "owner": {"name": "Cut1"}},
                "segments": [
                    {
                        "geometry": {
                            "complete_circle": True,
                            "radius_mm": profile["radius"],
                        }
                    }
                ],
            }
        if action == "sketch":
            if self.rejected and self.defect == "post-rejection-sketch":
                return self.failure("SketchCreationFailed")
            self.serial += 1
            profile = {
                "absorbed": False,
                "radius": getattr(args, "radius_mm", 0),
                "x": args.center_x_mm,
                "y": args.center_y_mm,
                "width": getattr(args, "width_mm", 0),
                "height": getattr(args, "height_mm", 0),
            }
            sketch_id = f"s-{self.serial:06x}"
            document["profiles"][sketch_id] = profile
            document["stamp"] += 1
            document["modified"] = True
            result = {
                "ok": True,
                "document": self.descriptor(document, session),
                "plane": args.plane,
                "editing": False,
                "coordinate_system": "sketch-local",
                "sketch": {"sketch_id": sketch_id},
                "geometry_verification": {
                    "passed": True,
                    "profile_segment_count": 4 if subcommand == "rectangle" else 1,
                    "complete_circle": True,
                    "actual_radius_mm": profile["radius"],
                    "actual_center_mm": {"x": profile["x"], "y": profile["y"], "z": 0},
                },
            }
            if self.rejected and self.defect == "lost-foreground":
                result["document"]["active"] = True
            return result
        if action == "feature" and subcommand == "set-depth":
            selected = next(
                (
                    key[1]
                    for key, value in self.feature_ids.items()
                    if key[0] == document_id and value == args.feature_id
                ),
                None,
            )
            if selected is None:
                return self.failure("FeatureNotFound")
            lifecycle = (
                "staging_attempted",
                "configuration_scope_applied",
                "commit_attempted",
                "committed",
            )
            access = (
                "attempted",
                "acquired",
                "release_attempted",
                "released",
                "state_restored",
            )
            if document["read_only"]:
                result = self.failure(
                    "DocumentNotWritable",
                    mutation={key: False for key in lifecycle},
                    selection_checks={
                        "preflight": {
                            "selection_access": {key: False for key in access}
                        }
                    },
                )
                if self.defect == "depth-readonly-mutated":
                    result["mutation"]["staging_attempted"] = True
                return result
            profile = document["profiles"][selected]
            changed = not math.isclose(
                profile["depth"], args.depth_mm, rel_tol=0, abs_tol=1e-6
            )
            if changed:
                area = (
                    math.pi * profile["radius"] ** 2
                    if profile["radius"]
                    else profile["width"] * profile["height"]
                )
                document["volume"] += (
                    area
                    * (args.depth_mm - profile["depth"])
                    * (-1 if profile["cut"] else 1)
                )
                document["stamp"] += 7
                document["modified"] = True
            profile["depth"] = args.depth_mm
            document["stamp"] += 2
            metrics = {
                "solid_body_count": document["count"],
                "volume_mm3": document["volume"],
                "surface_area_mm2": document["area"],
                "centroid_mm": {"x": 10, "y": 20, "z": 10},
            }
            result = {
                "ok": True,
                "document": self.descriptor(document, session),
                "feature_id": args.feature_id,
                "depth_changed": changed,
                "mutation": {key: changed for key in lifecycle},
                "definition_after": {"depth_mm": args.depth_mm},
                "measurement_after": metrics,
                "verification": {"passed": True},
                "selection_checks": {
                    phase: {
                        "ok": True,
                        "selection_access": {key: True for key in access},
                    }
                    for phase in (
                        ("preflight", "postflight") if changed else ("preflight",)
                    )
                },
            }
            if changed:
                result["rebuilt"] = True
            if self.defect == "depth-volume":
                result["measurement_after"]["volume_mm3"] += 1
            if self.defect == "depth-unreleased":
                result["selection_checks"]["preflight"]["selection_access"][
                    "released"
                ] = False
            if self.defect == "depth-equal-mutated" and not changed:
                result["mutation"]["staging_attempted"] = True
            if self.defect == "depth-equal-ulp" and not changed:
                for key in ("volume_mm3", "surface_area_mm2"):
                    metrics[key] = math.nextafter(metrics[key], math.inf)
                for axis in "xyz":
                    metrics["centroid_mm"][axis] = math.nextafter(
                        metrics["centroid_mm"][axis], math.inf
                    )
            if self.defect == "depth-equal-volume" and not changed:
                metrics["volume_mm3"] += 1e-4
            if self.defect == "depth-equal-area" and not changed:
                metrics["surface_area_mm2"] += 1e-4
            if self.defect == "depth-equal-centroid" and not changed:
                metrics["centroid_mm"]["z"] += 1e-4
            if self.defect == "depth-equal-count" and not changed:
                metrics["solid_body_count"] += 1
            if self.defect == "depth-equal-invalid" and not changed:
                metrics["volume_mm3"] = None
            if self.defect == "depth-foreground":
                result["document"]["active"] = True
            return result
        if action == "feature" and subcommand in ("list", "inspect"):
            state = {
                "configuration": "Default",
                "update_stamp": document["stamp"],
                "modified": document["modified"],
                "editing": False,
                "foreground_present": self.active is not None,
            }
            observed = {
                "before": state,
                "after": copy.deepcopy(state),
                "unchanged": True,
            }
            features = []
            for profile_id, profile in document["profiles"].items():
                if not profile["absorbed"]:
                    continue
                key = (document_id, profile_id)
                if key not in self.feature_ids:
                    self.serial += 1
                    self.feature_ids[key] = f"f-{self.serial:06x}"
                features.append(
                    {
                        "feature_id": self.feature_ids[key],
                        "name": profile_id,
                        "type": "Cut" if profile["cut"] else "Extrusion",
                        "native_type": "Cut" if profile["cut"] else "Extrusion",
                        "kind": "cut-extrude" if profile["cut"] else "boss-extrude",
                    }
                )
            if subcommand == "list":
                if len(features) > args.max_features:
                    return self.failure("FeatureListLimitExceeded")
                return {
                    "ok": True,
                    "document": descriptor,
                    "scope": "part-extrusions",
                    "count": len(features),
                    "features": features,
                    "observation": observed,
                }
            selected = next(
                (f for f in features if f["feature_id"] == args.feature_id), None
            )
            if selected is None:
                return self.failure("FeatureNotFound")
            profile = document["profiles"][selected["name"]]
            definition = {
                "depth_mm": profile["depth"],
                "end_condition": 0,
                "reverse_direction": profile["reverse"],
                "both_directions": False,
                "thin": False,
                "from_type": 0,
                "forward_draft": False,
                "reverse_draft": False,
                "feature_scope" if profile["cut"] else "merge": True,
            }
            if self.defect == "feature-read-depth":
                definition["depth_mm"] += 1
            if self.defect == "depth-reopen" and document["path"].endswith(
                "edited-depth.SLDPRT"
            ):
                definition["depth_mm"] += 1
            if self.defect == "feature-read-state":
                observed["after"]["modified"] = not observed["before"]["modified"]
            return {
                "ok": True,
                "document": descriptor,
                "feature": selected,
                "definition": definition,
                "observation": observed,
            }
        if action == "feature":
            profile = document["profiles"][args.sketch_id]
            if profile["absorbed"]:
                return self.failure("SketchUnavailable")
            if subcommand == "cut-extrude" and profile["x"] == 1000:
                self.rejected = True
                result = self.failure("CutExtrusionFailed")
                if self.defect == "cleanup-warning":
                    result["warnings"] = [{"code": "sketch-cleanup-failed"}]
                if self.defect == "wrong-rejection":
                    result["error"]["type"] = "HostDisconnected"
                return result
            profile["absorbed"] = True
            profile.update(
                depth=args.depth_mm,
                reverse=args.reverse,
                cut=subcommand == "cut-extrude",
            )
            document["stamp"] += 1
            document["modified"] = True
            removed = math.pi * profile["radius"] ** 2 * args.depth_mm
            if subcommand == "cut-extrude":
                document["volume"] -= removed
                document["area"] += 128 * math.pi
            else:
                document["count"] += 1
                document["volume"] += (
                    removed
                    if profile["radius"]
                    else profile["width"] * profile["height"] * args.depth_mm
                )
                document["area"] += 16000
            self.serial += 1
            feature_id = self.feature_ids[(document_id, args.sketch_id)] = (
                f"f-{self.serial:06x}"
            )
            return {
                "ok": True,
                "document": self.descriptor(document, session),
                "feature": {"name": "Cut1", "feature_id": feature_id},
                "bodies": {
                    "count": document["count"],
                    "items": [
                        {
                            "approximate_bounding_box": {
                                "size_mm": {"x": 100, "y": 50, "z": 20}
                            }
                        }
                    ],
                },
                "geometry_verification": {
                    "passed": True,
                    "actual_reverse": args.reverse,
                    "actual_merge": getattr(args, "merge", True),
                    "actual_depth_mm": args.depth_mm,
                    "volume_removed_mm3": removed,
                },
                "measurement_after": {"surface_area_mm2": document["area"]},
            }
        raise AssertionError(f"unhandled generated CLI call: {args}")

    def edge_result(self, args, document, descriptor, key, depth, hole):
        # Independent analytical fixture, not the production assertion helper.
        corners = list(product((-40, 60), (-5, 45), (0, depth)))
        pairs = [(a, b) for a, b in combinations(corners, 2)
                 if sum(x != y for x, y in zip(a, b)) == 1]
        edges = []
        for start, end in pairs:
            delta = [b - a for a, b in zip(start, end)]
            magnitude = math.hypot(*delta)
            edges.append({
                "kind": "edge", "curve_kind": "line",
                "parameter_data": {
                    "coordinate_system": "part-model", "interpretation": "native-edge-parameter-data",
                    "start_point_mm": list(start), "end_point_mm": list(end),
                    "u_min_native": 0., "u_max_native": magnitude / 1000,
                    "curve_and_edge_same_direction": True, "curve_type": 3001,
                },
                "curve_geometry": {
                    "available": True, "coordinate_system": "part-model", "boundary": "untrimmed-curve",
                    "line": {"root_point_mm": list(start), "direction": [v / magnitude for v in delta]},
                },
            })
        for z in (0, hole):
            edges.append({
                "kind": "edge", "curve_kind": "circle",
                "parameter_data": {
                    "coordinate_system": "part-model", "interpretation": "native-edge-parameter-data",
                    "start_point_mm": [13., 20., z], "end_point_mm": [13., 20., z],
                    "u_min_native": 0., "u_max_native": math.tau,
                    "curve_and_edge_same_direction": True, "curve_type": 3002,
                },
                "curve_geometry": {
                    "available": True, "coordinate_system": "part-model", "boundary": "untrimmed-curve",
                    "circle": {"center_mm": [10., 20., z], "axis_direction": [0., 0., 1.], "radius_mm": 3.},
                },
            })
        for token, edge in zip(self.entity_ids[key], edges):
            edge["entity_id"] = token
        if self.defect == "edge-wrong-radius":
            edges[-1]["curve_geometry"]["circle"]["radius_mm"] = 4.
        if self.defect == "edge-wrong-center":
            edges[-1]["curve_geometry"]["circle"]["center_mm"][0] = 11.
        if self.defect == "edge-duplicate-circle":
            other = copy.deepcopy(edges[-2])
            other["entity_id"] = edges[-1]["entity_id"]
            edges[-1] = other
        if self.defect == "edge-wrong-endpoint":
            edges[0]["parameter_data"]["end_point_mm"][0] += 1.
        if self.defect == "edge-circle-endpoint":
            edges[-1]["parameter_data"]["end_point_mm"][0] += 1.
        if self.defect == "edge-duplicate-line":
            other = copy.deepcopy(edges[0])
            other["entity_id"] = edges[1]["entity_id"]
            edges[1] = other
        if self.defect == "edge-root-off-line":
            # First pair is parallel to z; shift only the untrimmed root's x.
            edges[0]["curve_geometry"]["line"]["root_point_mm"][0] += 1.
        if self.defect == "edge-tilted-line":
            edges[0]["curve_geometry"]["line"]["direction"] = [1e-5, 0., math.sqrt(1 - 1e-10)]
        if self.defect == "edge-tilted-circle":
            edges[-1]["curve_geometry"]["circle"]["axis_direction"] = [1e-5, 0., math.sqrt(1 - 1e-10)]
        if self.defect == "edge-extra-length":
            edges[0]["length_mm"] = 20.
        if self.defect == "edge-opposite-sense":
            for edge in edges:
                edge["parameter_data"]["curve_and_edge_same_direction"] = False
        self.edge_reads += 1
        if self.defect == "edge-reordered" and self.edge_reads % 2 == 0:
            edges.reverse()
        if self.defect == "edge-evicts-faces" and args.entity_command == "list":
            self.entity_ids.pop((key[0], key[1], "face"), None)
        state = {"configuration": "Default", "update_stamp": document["stamp"],
                 "modified": document["modified"], "editing": False, "foreground_present": self.active is not None}
        return {
            "ok": True, "action": f"entity.{args.entity_command}", "document": descriptor,
            "scope": "single-solid-part-edges", "body_count": 1, "edge_count": 14,
            "observation": {"before": state, "after": state.copy(), "unchanged": True},
            **({"entities": edges} if args.entity_command == "list" else
               {"entity": next(e for e in edges if e["entity_id"] == args.entity_id)}),
        }


class ModelingSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "evidence with spaces"
        self.fake = FakeCLI(self.directory)
        self.arguments = [
            "--output-dir",
            str(self.directory),
            "--host-output-dir",
            "C:\\evidence with spaces",
        ]

    def run_gate(self, *, samples=False, drawing=False):
        arguments = self.arguments + (
            [
                "--sample-part",
                "C:\\samples\\Paper.SLDPRT",
                "--sample-assembly",
                "C:\\samples\\Mold.SLDASM",
            ]
            if samples
            else []
        )
        if drawing:
            source = Path(self.temporary.name) / "installed source.SLDDRW"
            source.write_bytes(b"drawing" * 100)
            arguments += ["--sample-drawing", "C:\\samples\\installed source.SLDDRW",
                          "--sample-drawing-local", str(source)]
        with (
            mock.patch.object(
                gate.subprocess, "run", side_effect=self.fake.run
            ) as command,
            mock.patch("sys.stdout", new=io.StringIO()),
        ):
            gate.main(arguments)
        return command

    def record(self):
        return json.loads(
            (self.directory / "modeling.json").read_text(encoding="utf-8")
        )

    def drawing_gate(self, defect=None):
        self.directory.mkdir(parents=True, exist_ok=True)
        source = Path(self.temporary.name) / "installed source.SLDDRW"
        source.write_bytes(b"drawing" * 100)
        self.fake = FakeCLI(self.directory)
        self.fake.defect = defect
        self.fake.drawing_source = source
        smoke = gate.ModelingSmoke(directory=self.directory,
                                   host_directory="C:\\evidence with spaces",
                                   endpoint="127.0.0.1:18495")
        smoke.record_path.write_text(json.dumps(smoke.record), encoding="utf-8")
        with mock.patch.object(gate.subprocess, "run", side_effect=self.fake.run), \
                mock.patch("sys.stdout", new=io.StringIO()):
            try:
                smoke.drawing_save_reopen("C:\\samples\\installed source.SLDDRW", source)
            finally:
                smoke.cleanup()
        return smoke, source

    def test_drawing_save_size_reopen_and_source_immutability(self):
        smoke, source = self.drawing_gate("drawing-readonly-warning")
        proof = smoke.record["drawing_save_reopen"]
        self.assertEqual(proof["source_sha256_before"], proof["source_sha256_after"])
        self.assertEqual(source.read_bytes(), b"drawing" * 100)
        self.assertEqual(proof["size_bytes"], 700)
        self.assertTrue(proof["structure_unchanged"])
        self.assertTrue(proof["fresh_document_id"])
        self.assertEqual(proof["observation_scope"], "top-level-feature-tree")
        self.assertEqual([item["api_warnings"] for item in proof["opens"]], [2, 0, 2])
        self.assertEqual(smoke.record["native_in_place_saves"],
                         [{"format": "SLDDRW", "size_bytes": 700}])
        self.assertEqual(self.fake.documents, {})
        saves = [call for call in self.fake.calls
                 if call.command == "document" and call.document_command == "save"]
        self.assertEqual(len(saves), 1)
        self.assertFalse(any(call.command == "document" and call.document_command == "save-as"
                             for call in self.fake.calls))

    def test_drawing_gate_rejects_save_reopen_structure_and_reference_defects(self):
        for defect, message in (
            ("drawing-save-failed", "SaveFailed"),
            ("drawing-save-truncated", "drawing in-place save produced an empty or truncated"),
            ("drawing-reopen-failed", "OpenFailed"),
            ("drawing-structure-changed", "changed the feature tree"),
            ("drawing-structure-truncated", "empty or truncated"),
            ("drawing-structure-empty", "empty or truncated"),
            ("drawing-reference-warning", "unexpected warnings: 4"),
            ("drawing-writable-warning", "unexpected warnings: 2"),
            ("drawing-open-error", "required type/read-only state"),
            ("drawing-readonly-missing", "required type/read-only state"),
            ("drawing-reused-id", "reused an expired document ID"),
            ("drawing-reopen-changed-file", "reopen changed the saved artifact"),
            ("drawing-source-changed", "changed the installed source"),
        ):
            with self.subTest(defect=defect):
                with self.assertRaisesRegex(RuntimeError, message):
                    self.drawing_gate(defect)
                self.assertEqual(self.fake.documents, {})
                (self.directory / "drawing.SLDDRW").unlink(missing_ok=True)

    def test_drawing_gate_does_not_overwrite_existing_evidence(self):
        self.directory.mkdir(parents=True)
        artifact = self.directory / "drawing.SLDDRW"
        artifact.write_bytes(b"existing proof")
        with self.assertRaises(FileExistsError):
            self.drawing_gate()
        self.assertEqual(artifact.read_bytes(), b"existing proof")

    def test_drawing_sample_requires_both_path_namespaces(self):
        for options in (["--sample-drawing", "C:\\samples\\Source.SLDDRW"],
                        ["--sample-drawing-local", "/samples/Source.SLDDRW"]):
            with self.subTest(options=options), mock.patch("sys.stderr", new=io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    gate.main(self.arguments + options)
                self.assertEqual(error.exception.code, 2)

    def test_shared_gate_runs_optional_drawing_case_and_keeps_one_host(self):
        self.run_gate(drawing=True)
        proof = self.record()
        self.assertTrue(proof["success"])
        self.assertIn("drawing-save-reopen", proof["cases"])
        self.assertEqual(proof["host"]["process_id"], proof["host_after"]["process_id"])
        self.assertEqual(proof["cleanup_errors"], [])

    def test_assembly_save_and_read_only_reopen_have_size_and_structure_evidence(self):
        self.run_gate(samples=True)
        proof = self.record()["assembly_save_reopen"]
        self.assertGreaterEqual(proof["save_as_bytes"], 512)
        self.assertGreaterEqual(proof["size_bytes"], 512)
        self.assertTrue(proof["structure_unchanged"])
        self.assertTrue(proof["fresh_document_id"])
        save_calls = [call for call in self.fake.calls
                      if call.command == "document" and call.document_command == "save"]
        self.assertEqual(len(save_calls), 2)
        saves = self.record()["native_in_place_saves"]
        self.assertEqual([saved["format"] for saved in saves], ["SLDPRT", "SLDASM"])
        self.assertTrue(all(saved["size_bytes"] >= 512 for saved in saves))
        saved_assemblies = [document for path, document in self.fake.saved.items()
                            if path.endswith(".SLDASM")]
        self.assertEqual(len(saved_assemblies), 1)

    def test_assembly_gate_rejects_bad_save_reopen_and_changed_structure(self):
        for defect, message in (
            ("part-save-truncated", "part in-place save produced an empty or truncated"),
            ("assembly-save-as-truncated", "empty or truncated"),
            ("assembly-save-truncated", "empty or truncated"),
            ("assembly-reopen-failed", "OpenFailed"),
            ("assembly-structure-changed", "changed configurations or feature tree"),
        ):
            with self.subTest(defect=defect):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "evidence"
                    fake = FakeCLI(path)
                    fake.defect = defect
                    arguments = ["--output-dir", str(path), "--host-output-dir", "C:\\proof",
                                 "--sample-part", "C:\\samples\\Paper.SLDPRT",
                                 "--sample-assembly", "C:\\samples\\Mold.SLDASM"]
                    with mock.patch.object(gate.subprocess, "run", side_effect=fake.run), \
                            mock.patch("sys.stdout", new=io.StringIO()):
                        with self.assertRaisesRegex(RuntimeError, message):
                            gate.main(arguments)

    def test_complete_shared_sequence_parses_real_cli_and_keeps_one_host(self):
        commands = self.run_gate(samples=True)
        record = self.record()
        self.assertEqual(record["request_timeout_seconds"], 120)
        self.assertEqual(record["cli_process_timeout_seconds"], 135)
        self.assertEqual(record["depth_request_timeout_seconds"], 600)
        for process, event, call in zip(
            commands.call_args_list, record["events"], self.fake.calls
        ):
            depth_write = (
                call.command == "feature"
                and call.feature_command == "set-depth"
                and event["returncode"] == 0
            )
            seconds = 600 if depth_write else 120
            self.assertEqual(process.kwargs["timeout"], seconds + 15)
            self.assertEqual(call.request_timeout, seconds)
            self.assertEqual(event["request_timeout_seconds"], seconds)
        self.assertTrue(record["success"])
        self.assertEqual(
            record["cases"],
            [
                "native-model",
                "reverse-cut",
                "feature-depth",
                "sample-exports",
                "rejected-cut-then-sketch",
            ],
        )
        self.assertEqual(
            record["host"]["process_id"], record["host_after"]["process_id"]
        )
        self.assertEqual(record["cleanup_errors"], [])
        self.assertTrue(record["entity_observation"]["verified"])
        self.assertEqual(record["entity_observation"]["edge_count"], 14)
        self.assertTrue(record["entity_observation"]["mixed_kind_ids_preserved"])
        self.assertTrue(all(
            event["result"].get("request_id")
            for event in record["events"]
            if "entity" in event["command"]
        ))
        self.assertEqual(self.fake.documents, {})
        calls = self.fake.calls
        failed = next(
            i
            for i, args in enumerate(calls)
            if args.command == "feature"
            and args.feature_command == "cut-extrude"
            and record["events"][i]["result"].get("error", {}).get("type")
            == "CutExtrusionFailed"
        )
        self.assertEqual(calls[failed + 1].document_command, "inspect")
        self.assertEqual(calls[failed + 2].sketch_command, "inspect")
        self.assertTrue(
            any(
                args.command == "sketch" and args.sketch_command == "circle"
                for args in calls[failed + 3 :]
            )
        )
        self.assertFalse(
            any(
                args.command == "daemon" and args.daemon_command != "status"
                for args in calls
            )
        )
        self.assertTrue(
            all(event["state"] == "completed" for event in record["events"])
        )
        self.assertTrue(
            all(event["stderr"] == "native stderr\n" for event in record["events"])
        )

    def test_entity_geometry_gate_refuses_plausible_but_wrong_native_values(self):
        for defect in (
            "entity-wrong-radius",
            "entity-wrong-plane",
            "entity-wrong-outward",
            "entity-duplicate-plane-geometry",
            "entity-duplicate-cut-floor",
            "entity-tilted-plane",
            "entity-extra-field",
        ):
            with (
                self.subTest(defect=defect),
                tempfile.TemporaryDirectory() as temporary,
            ):
                self.directory = Path(temporary) / "proof"
                self.fake = FakeCLI(self.directory)
                self.fake.defect = defect
                self.arguments[1] = str(self.directory)
                with self.assertRaises(RuntimeError):
                    self.run_gate()
                self.assertFalse(self.record()["success"])
                self.assertEqual(self.fake.documents, {})

    def test_entity_geometry_gate_accepts_complete_reordered_face_set(self):
        self.fake.defect = "entity-reordered-faces"
        self.run_gate()
        self.assertTrue(self.record()["entity_observation"]["verified"])
        self.assertEqual(self.fake.documents, {})

    def test_edge_geometry_and_mixed_kind_gate_refuse_wrong_native_evidence(self):
        for defect in (
            "edge-wrong-radius", "edge-wrong-center", "edge-duplicate-circle",
            "edge-wrong-endpoint", "edge-circle-endpoint", "edge-duplicate-line",
            "edge-root-off-line", "edge-tilted-line", "edge-tilted-circle",
            "edge-extra-length", "edge-evicts-faces",
        ):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temporary:
                self.directory = Path(temporary) / "proof"
                self.fake = FakeCLI(self.directory)
                self.fake.defect = defect
                self.arguments[1] = str(self.directory)
                with self.assertRaises(RuntimeError):
                    self.run_gate()
                self.assertFalse(self.record()["success"])
                self.assertEqual(self.fake.documents, {})

    def test_edge_gate_refuses_stale_acceptance_and_reopened_id_reuse(self):
        for defect in ("edge-accepts-stale", "edge-reuses-reopened-ids"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temporary:
                self.directory = Path(temporary) / "proof"
                self.fake = FakeCLI(self.directory)
                self.fake.defect = defect
                self.arguments[1] = str(self.directory)
                with self.assertRaises(RuntimeError):
                    self.run_gate()
                self.assertFalse(self.record()["success"])
                self.assertEqual(self.fake.documents, {})

    def test_edge_gate_accepts_opposite_sense_and_reordered_complete_reads(self):
        for defect in ("edge-opposite-sense", "edge-reordered"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temporary:
                self.directory = Path(temporary) / "proof"
                self.fake = FakeCLI(self.directory)
                self.fake.defect = defect
                self.arguments[1] = str(self.directory)
                self.run_gate()
                self.assertTrue(self.record()["entity_observation"]["verified"])
                self.assertEqual(self.fake.documents, {})

    def test_cli_metadata_is_retained_in_evidence_not_business_assertion_view(self):
        self.directory.mkdir()
        smoke = gate.ModelingSmoke(
            directory=self.directory, host_directory=r"C:\proof", endpoint="local"
        )
        smoke.record_path.write_text(json.dumps(smoke.record), encoding="utf-8")
        payload = {
            "ok": True, "action": "document.list", "documents": [],
            "request_id": "req-replay", "replayed": True, "unexpected": "retained",
        }
        with mock.patch.object(
            gate.subprocess, "run",
            return_value=subprocess.CompletedProcess(
                [], 0, json.dumps(payload).encode("utf-8"), b""
            ),
        ):
            result = smoke.command("document", "list")
        self.assertEqual(smoke.record["events"][0]["result"], payload)
        self.assertNotIn("request_id", result)
        self.assertNotIn("replayed", result)
        self.assertEqual(result["unexpected"], "retained")

    def test_custom_request_timeout_reaches_all_cli_calls_and_evidence(self):
        self.arguments.extend(
            ["--request-timeout", "300", "--depth-request-timeout", "300"]
        )
        commands = self.run_gate(samples=True)
        record = self.record()
        self.assertTrue(record["success"])
        self.assertEqual(record["request_timeout_seconds"], 300)
        self.assertEqual(record["cli_process_timeout_seconds"], 315)
        self.assertTrue(commands.call_args_list)
        self.assertTrue(
            all(call.kwargs["timeout"] == 315 for call in commands.call_args_list)
        )
        self.assertTrue(all(call.request_timeout == 300 for call in self.fake.calls))

    def test_equal_depth_independent_kernel_reads_allow_only_numeric_roundoff(self):
        self.fake.defect = "depth-equal-ulp"
        self.run_gate()
        self.assertTrue(self.record()["success"])
        self.assertEqual(self.fake.documents, {})

    def test_equal_depth_metric_check_refuses_invalid_baselines_and_counts(self):
        baseline = {
            "solid_body_count": 1,
            "volume_mm3": 125000.0,
            "surface_area_mm2": 18000.0,
            "centroid_mm": {"x": 0.0, "y": 20.0, "z": 12.5},
        }
        for key, value in (("solid_body_count", True), ("volume_mm3", math.inf)):
            with self.subTest(key=key):
                invalid = {**baseline, key: value}
                with self.assertRaises(RuntimeError):
                    gate.unchanged_depth_metrics(invalid, baseline)
        invalid = copy.deepcopy(baseline)
        invalid["centroid_mm"]["x"] = math.nan
        with self.assertRaises(RuntimeError):
            gate.unchanged_depth_metrics(invalid, baseline)
        for value in (True, math.nan, math.inf):
            with self.subTest(actual=value):
                invalid = {**baseline, "volume_mm3": value}
                with self.assertRaises(RuntimeError):
                    gate.unchanged_depth_metrics(baseline, invalid)

    def test_invalid_request_timeout_refused_before_work(self):
        for value in ("0", "-1", "nan", "inf", "-inf", "1e309", "3600.1", "invalid"):
            with (
                self.subTest(value=value),
                mock.patch.object(gate.subprocess, "run") as command,
                mock.patch("sys.stderr", new=io.StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                gate.main(self.arguments + [f"--request-timeout={value}"])
            self.assertEqual(error.exception.code, 2)
            command.assert_not_called()

    def test_invalid_depth_timeout_refused_before_work(self):
        for value in ("0", "-1", "nan", "inf", "3600.1", "invalid"):
            with (
                self.subTest(value=value),
                mock.patch.object(gate.subprocess, "run") as command,
                mock.patch("sys.stderr", new=io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    gate.main([*self.arguments, "--depth-request-timeout", value])
                command.assert_not_called()
            self.assertFalse(self.directory.exists())

    def test_request_timeout_preserves_fractional_and_maximum_values(self):
        for value in (0.25, 300.25, 300.1239, 3599.9999, 3600):
            smoke = gate.ModelingSmoke(
                directory=self.directory,
                host_directory=r"C:\proof",
                endpoint="local",
                request_timeout_seconds=value,
            )
            with (
                mock.patch.object(
                    gate.subprocess,
                    "run",
                    return_value=(
                        subprocess.CompletedProcess([], 0, b'{"ok":true}', b"")
                    ),
                ) as command,
                mock.patch.object(smoke, "checkpoint"),
            ):
                smoke.command("document", "list")
            arguments = command.call_args.args[0]
            self.assertEqual(
                float(arguments[arguments.index("--request-timeout") + 1]), value
            )
            self.assertEqual(command.call_args.kwargs["timeout"], value + 15)
            self.assertEqual(smoke.record["request_timeout_seconds"], value)
        with self.assertRaises(gate.argparse.ArgumentTypeError):
            gate.ModelingSmoke(
                directory=self.directory,
                host_directory=r"C:\proof",
                endpoint="local",
                request_timeout_seconds=True,
            )

    def test_native_failure_state_and_host_defects_fail_without_restart(self):
        for defect in (
            "cleanup-warning",
            "wrong-rejection",
            "feature-read-depth",
            "feature-read-state",
            "editing",
            "editing-unknown",
            "rejected-volume",
            "post-rejection-sketch",
            "lost-foreground",
            "host-replaced",
            "null-stamp",
            "overwrite-existing",
            "close-no-op",
            "depth-volume",
            "depth-unreleased",
            "depth-equal-mutated",
            "depth-equal-volume",
            "depth-equal-area",
            "depth-equal-centroid",
            "depth-equal-count",
            "depth-equal-invalid",
            "depth-foreground",
            "depth-reopen",
            "depth-readonly-mutated",
        ):
            with (
                self.subTest(defect=defect),
                tempfile.TemporaryDirectory() as temporary,
            ):
                self.directory = Path(temporary)
                self.fake = FakeCLI(self.directory)
                self.fake.defect = defect
                self.arguments = [
                    "--output-dir",
                    temporary,
                    "--host-output-dir",
                    "C:\\tests",
                ]
                with self.assertRaises(RuntimeError):
                    self.run_gate()
                self.assertFalse(self.record()["success"])
                self.assertEqual(self.fake.documents, {})
                self.assertFalse(
                    any(
                        args.command == "daemon" and args.daemon_command != "status"
                        for args in self.fake.calls
                    )
                )

    def test_slow_operations_preserve_leases_including_negative_tests(self):
        # No sleeps: every CLI call consumes 75 virtual seconds, exceeding
        # the old 60-second TTL while remaining below the 120-second deadline.
        self.fake.operation_seconds = 75
        self.run_gate(samples=True)
        self.assertTrue(self.record()["success"])
        self.assertEqual(self.record()["cleanup_errors"], [])
        self.assertGreater(self.fake.now, gate.LEASE_TTL_SECONDS)
        for index, args in enumerate(self.fake.calls):
            if args.command == "document" and args.document_command == "lease":
                if args.lease_command in ("acquire", "renew"):
                    self.assertEqual(args.ttl_seconds, gate.LEASE_TTL_SECONDS)
                continue
            if getattr(args, "lease_id", None) is not None:
                previous = self.fake.calls[index - 1]
                self.assertEqual(previous.command, "document")
                self.assertEqual(previous.document_command, "lease")
                self.assertEqual(previous.lease_command, "renew")
                self.assertEqual(previous.lease_id, args.lease_id)
                self.assertEqual(previous.session, args.session)

    def smoke_with_document(self):
        self.directory.mkdir()
        smoke = gate.ModelingSmoke(
            directory=self.directory, host_directory="C:\\proof", endpoint="local"
        )
        smoke.record_path.write_text("{}", encoding="utf-8")
        with mock.patch.object(gate.subprocess, "run", side_effect=self.fake.run):
            document = smoke.create()
            smoke.command(
                "document",
                "lease",
                "acquire",
                "--ttl-seconds",
                gate.LEASE_TTL_SECONDS,
                document=document,
            )
        return smoke, document

    def test_cleanup_renews_holder_lease_before_closing(self):
        smoke, document = self.smoke_with_document()
        self.fake.now += gate.LEASE_TTL_SECONDS - 5
        with mock.patch.object(gate.subprocess, "run", side_effect=self.fake.run):
            smoke.cleanup()
        self.assertEqual(smoke.record["cleanup_errors"], [])
        self.assertNotIn(document, self.fake.documents)
        renew, close = self.fake.calls[-2:]
        self.assertEqual(renew.lease_command, "renew")
        self.assertEqual(close.document_command, "close")
        self.assertEqual(close.lease_id, renew.lease_id)

    def test_expired_lease_fails_without_reacquiring_or_attempting_write(self):
        smoke, document = self.smoke_with_document()
        self.fake.now += gate.LEASE_TTL_SECONDS + 1
        with mock.patch.object(gate.subprocess, "run", side_effect=self.fake.run):
            with self.assertRaisesRegex(RuntimeError, "DocumentLeaseNotFound"):
                smoke.write(
                    "document", "save-as", "C:\\proof\\denied.SLDPRT", document=document
                )
            smoke.cleanup()
        self.assertEqual(len(smoke.record["cleanup_errors"]), 1)
        self.assertIn(document, self.fake.documents)
        self.assertFalse((self.directory / "denied.SLDPRT").exists())
        self.assertFalse(
            any(
                args.document_command in ("save-as", "close")
                for args in self.fake.calls
                if args.command == "document"
            )
        )
        self.assertEqual(
            sum(
                args.command == "document"
                and args.document_command == "lease"
                and args.lease_command == "acquire"
                for args in self.fake.calls
            ),
            1,
        )

    def test_existing_evidence_refused_before_any_cli_call(self):
        self.directory.mkdir()
        target = self.directory / "modeling.json"
        target.write_text('{"previous":true}', encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.run_gate()
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(target.read_text(), '{"previous":true}')

    def test_partial_sample_configuration_refused_before_any_cli_call(self):
        with self.assertRaises(SystemExit), mock.patch("sys.stderr", new=io.StringIO()):
            gate.main(self.arguments + ["--sample-part", "C:\\sample.SLDPRT"])
        self.assertEqual(self.fake.calls, [])

    def test_posix_output_needs_explicit_host_path(self):
        # Simulate the local POSIX namespace even on Windows runners. The real
        # Windows output path is valid without an override and must not cause
        # this offline unit test to contact an actual daemon.
        local_path = mock.Mock()
        local_path.expanduser.return_value.resolve.return_value = PurePosixPath(
            "/workspace/proof"
        )
        with (
            mock.patch.object(gate, "Path", return_value=local_path),
            mock.patch.object(gate.subprocess, "run") as command,
            self.assertRaises(gate.argparse.ArgumentTypeError),
        ):
            gate.main(["--output-dir", "/workspace/proof"])
        local_path.mkdir.assert_not_called()
        command.assert_not_called()
        self.assertFalse(self.directory.exists())


if __name__ == "__main__":
    unittest.main()
