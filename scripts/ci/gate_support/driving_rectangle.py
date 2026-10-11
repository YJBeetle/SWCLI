"""RectangleCases extracted without changing full-suite assertions."""


from swcli.result_schemas import validate_operation_result


from gate_support.driving_checks import (
    host_path,
    LEASE_TTL_SECONDS,
    require,
    close_enough,
    assert_linear_dimension,
)


class RectangleCases:
    def rectangle_dimensions(self, plane):
        """Installed exact size edits on a leased background part, same host."""
        document_id = self.create()
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
        # Positioning is explicit and independently covered by the center gate.
        self.write("sketch.fix-center", {"sketch_id": sketch_id}, **write)
        values = {"sketch_id": sketch_id, "width_mm": 40, "height_mm": 30}
        stamp = self.stamp(document_id)
        self.call(
            "sketch.dimension-rectangle",
            values,
            document_id=document_id,
            expected_error="DocumentLeaseConflict",
            session_id=self.session + "-contender",
        )
        self.write(
            "sketch.dimension-rectangle",
            values,
            expected_update_stamp=stamp + 1,
            expected_error="DocumentUpdateConflict",
            **write,
        )
        require(
            self.stamp(document_id) == stamp, "rejected size creation changed stamp"
        )
        created = (
            self.write_command(
                [
                    "sketch",
                    "dimension-rectangle",
                    "--document",
                    document_id,
                    sketch_id,
                    "--width-mm",
                    "40",
                    "--height-mm",
                    "30",
                    "--lease",
                    lease,
                    "--if-update-stamp",
                    str(stamp),
                ],
                document_id=document_id,
            )
            if plane == "front"
            else self.write("sketch.dimension-rectangle", values, **write)
        )
        validate_operation_result("sketch.dimension-rectangle", created)
        ids = {
            kind: created["dimensions"][kind]["dimension_id"]
            for kind in ("width", "height")
        }
        require(len(set(ids.values())) == 2, "width/height share a wire dimension ID")
        proof = {
            "plane": plane,
            "sketch_id": sketch_id,
            "created": created,
            "edits": [],
        }
        self.record.setdefault("rectangle_dimensions", []).append(proof)
        self.checkpoint(f"rectangle-dimensions.{plane}.created")
        self.assert_background(document_id, foreground_id)
        stamp = self.stamp(document_id)
        self.write(
            "sketch.dimension-rectangle",
            values,
            expected_error="SketchAlreadyDimensioned",
            **write,
        )
        require(self.stamp(document_id) == stamp, "duplicate dimensions changed stamp")

        def observe(width, height):
            before = self.stamp(document_id)
            for kind, dimension_id in ids.items():
                read = self.call(
                    "dimension.inspect",
                    {"dimension_id": dimension_id},
                    document_id=document_id,
                    session_id=self.session + "-observer",
                )
                assert_linear_dimension(
                    read, dimension_id, sketch_id, kind, width, height
                )
                self.assert_background(document_id, foreground_id)
            require(
                self.stamp(document_id) == before,
                "background linear reads changed stamp",
            )

        observe(40, 30)
        self.write("feature.extrude", {"sketch_id": sketch_id, "depth_mm": 10}, **write)
        stamp = self.stamp(document_id)
        edit = {"dimension_id": ids["width"], "value_mm": 50}
        self.call(
            "dimension.set",
            edit,
            document_id=document_id,
            expected_error="DocumentLeaseConflict",
        )
        self.write(
            "dimension.set",
            edit,
            expected_update_stamp=stamp + 1,
            expected_error="DocumentUpdateConflict",
            **write,
        )
        require(self.stamp(document_id) == stamp, "rejected linear edits changed stamp")
        for kind, value, width, height in (
            ("width", 50, 50, 30),
            ("height", 35, 50, 35),
        ):
            changed = (
                self.write_command(
                    [
                        "dimension",
                        "set",
                        "--document",
                        document_id,
                        ids[kind],
                        "--value-mm",
                        str(value),
                        "--lease",
                        lease,
                    ],
                    document_id=document_id,
                )
                if plane == "front" and kind == "width"
                else self.write(
                    "dimension.set",
                    {"dimension_id": ids[kind], "value_mm": value},
                    **write,
                )
            )
            validate_operation_result("dimension.set", changed)
            require(
                changed["downstream"]["applicable"] is True,
                "absorbed linear edit lacks downstream evidence",
            )
            observe(width, height)
            measured = self.call("document.measure", document_id=document_id)
            require(
                measured["metrics"]["solid_body_count"] == 1,
                "rectangle edit changed solid body count",
            )
            close_enough(
                measured["metrics"]["volume_mm3"],
                width * height * 10,
                "rectangle edit produced incorrect native volume",
            )
            proof["edits"].append(
                {"kind": kind, "changed": changed, "measured": measured}
            )
            self.assert_background(document_id, foreground_id)
        self.checkpoint(f"rectangle-dimensions.{plane}.verified")
        native_path = host_path(
            self.output_directory, f"{self.session}-{plane}-rectangle.SLDPRT"
        )
        proof["saved"] = self.write(
            "document.save-as", {"output": native_path}, **write
        )
        require(
            proof["saved"]["artifact"]["size_bytes"] >= 512,
            "rectangle native save produced an invalid file",
        )
        self.close(document_id)
        for dimension_id in ids.values():
            self.call(
                "dimension.inspect",
                {"dimension_id": dimension_id},
                document_id=foreground_id,
                expected_error="DimensionNotFound",
            )
        proof["expired_handles_rejected"] = True
        proof["reopened"] = self.discover_reopened_rectangle(
            native_path, sketch_id, ids, plane=plane, current_id=foreground_id
        )
        self.close(foreground_id)

    def discover_reopened_rectangle(
        self, native_path, expired_sketch, expired_ids, *, plane, current_id
    ):
        """Native persistence, fresh pair identity and unchanged background reads."""
        reopen_session = self.session + "-reopen"
        opened = self.call(
            "document.open",
            {"path": native_path, "read_only": True},
            session_id=reopen_session,
        )
        document_id = opened["document"]["document_id"]
        foreground_id = self.create(session_id=reopen_session)
        before_stamp = self.stamp(document_id)
        before_selection = {
            "main": self.selection_state(session_id=self.session),
            "reopen": self.selection_state(session_id=reopen_session),
        }
        require(
            before_selection
            == {
                "main": {
                    "current_document_id": current_id,
                    "active_document_id": foreground_id,
                },
                "reopen": {
                    "current_document_id": foreground_id,
                    "active_document_id": foreground_id,
                },
            },
            "rectangle reopen lost foreground/session isolation",
        )
        proof = {
            "document_id": document_id,
            "update_stamp_before": before_stamp,
            "selection_before": before_selection,
        }
        self.record.setdefault("reopened_rectangle_discoveries", []).append(proof)
        self.checkpoint(f"rectangle-discovery.{plane}.started")
        self.call(
            "sketch.inspect",
            {"sketch_id": expired_sketch},
            document_id=document_id,
            expected_error="SketchNotFound",
        )
        for token in expired_ids.values():
            self.call(
                "dimension.inspect",
                {"dimension_id": token},
                document_id=document_id,
                expected_error="DimensionNotFound",
            )
        listed = self.call("sketch.list", document_id=document_id)
        proof["listed"] = listed
        require(
            listed["count"] == 1 and len(listed["sketches"]) == 1,
            "reopened rectangle lacks one exact native profile",
        )
        sketch = listed["sketches"][0]
        sketch_id = sketch["sketch_id"]
        require(
            sketch_id != expired_sketch
            and sketch["type"] == "ProfileFeature"
            and sketch["absorbed"]
            and sketch["owner"] is not None,
            "reopened rectangle reused an expired or unverified sketch binding",
        )
        self.call(
            "dimension.discover-rectangle",
            {"sketch_id": sketch_id},
            document_id=document_id,
            expected_update_stamp=before_stamp + 1,
            expected_error="DocumentUpdateConflict",
        )

        def discover():
            return (
                self.command(
                    [
                        "dimension",
                        "discover-rectangle",
                        "--document",
                        document_id,
                        sketch_id,
                    ]
                )
                if plane == "front"
                else self.call(
                    "dimension.discover-rectangle",
                    {"sketch_id": sketch_id},
                    document_id=document_id,
                    expected_update_stamp=before_stamp,
                )
            )

        discovered = discover()
        proof["discovered"] = discovered
        validate_operation_result("dimension.discover-rectangle", discovered)
        ids = {
            kind: discovered["dimensions"][kind]["dimension_id"]
            for kind in ("width", "height")
        }
        require(
            len(set(ids.values())) == 2
            and not set(ids.values()) & set(expired_ids.values()),
            "rectangle discovery reused expired or conflicting dimension IDs",
        )
        self.checkpoint(f"rectangle-discovery.{plane}.discovered")
        repeated = discover()
        proof["repeated"] = repeated
        validate_operation_result("dimension.discover-rectangle", repeated)
        require(
            repeated["dimensions"] == discovered["dimensions"],
            "repeated rectangle discovery changed its live pair",
        )
        inspected = {}
        for kind, token in ids.items():
            inspected[kind] = self.call(
                "dimension.inspect", {"dimension_id": token}, document_id=document_id
            )
            assert_linear_dimension(inspected[kind], token, sketch_id, kind, 50, 35)
        proof["inspected"] = inspected
        measured = self.call("document.measure", document_id=document_id)
        proof["measured"] = measured
        require(
            measured["metrics"]["solid_body_count"] == 1,
            "rectangle reopen changed native solid body count",
        )
        close_enough(
            measured["metrics"]["volume_mm3"],
            17500,
            "rectangle reopen changed native volume",
        )
        after_stamp = self.stamp(document_id)
        after_selection = {
            "main": self.selection_state(session_id=self.session),
            "reopen": self.selection_state(session_id=reopen_session),
        }
        proof.update(update_stamp_after=after_stamp, selection_after=after_selection)
        require(
            after_stamp == before_stamp,
            "reopened rectangle discovery/inspection changed native stamp",
        )
        require(
            before_selection == after_selection,
            "reopened rectangle discovery changed foreground/session state",
        )
        for observed in (listed, discovered, repeated, *inspected.values()):
            require(
                observed["document"]["document_id"] == document_id
                and not observed["document"]["active"]
                and not observed["document"]["current"],
                "rectangle discovery changed background document identity",
            )
        self.checkpoint(f"rectangle-discovery.{plane}.completed")
        self.close(document_id)
        self.close(foreground_id)
        return proof
