"""DiameterCases extracted without changing full-suite assertions."""

import math
import re


from gate_support.driving_checks import (
    host_path,
    LEASE_TTL_SECONDS,
    require,
    assert_dimension,
    assert_circle,
    assert_measurement,
    assert_discovered_diameter,
)


class DiameterCases:
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
