"""NativeModelCases extracted without changing full-suite assertions."""

import hashlib
import math
from pathlib import PureWindowsPath
import re


from gate_support.model_checks import (
    host_directory,
    LEASE_TTL_SECONDS,
    require,
    near,
)


class NativeModelCases:
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
        self.unicode_file_roundtrip(local_model)

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
