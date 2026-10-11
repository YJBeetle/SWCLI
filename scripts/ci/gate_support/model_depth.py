"""FeatureDepthCases extracted without changing full-suite assertions."""

import math
from pathlib import PureWindowsPath

from swcli.result_schemas import validate_operation_result


from gate_support.model_checks import (
    host_directory,
    LEASE_TTL_SECONDS,
    require,
    near,
    unchanged_depth_metrics,
    verify_fixture_edges,
)


class FeatureDepthCases:
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
