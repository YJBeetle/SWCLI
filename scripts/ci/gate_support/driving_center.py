"""CenterCases extracted without changing full-suite assertions."""


from gate_support.driving_checks import (
    host_path,
    LEASE_TTL_SECONDS,
    require,
    assert_fixed_center,
)


class CenterCases:
    def center_constraints(self, plane):
        """Public proof, including native persistence; no COM fixture or retry."""
        document_id = self.create()
        origin_id = None
        if plane == "front":
            opened = self.call(
                "document.open", {"path": self.origin_path, "read_only": True}
            )
            origin_id = opened["document"]["document_id"]
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
            origin = self.call("sketch.list", document_id=origin_id)
            require(origin["count"] == 1 and len(origin["sketches"]) == 1,
                    "origin fixture must contain one exact native sketch")
            origin_sketch = origin["sketches"][0]["sketch_id"]
            origin_stamp = self.stamp(origin_id)
            proof["origin_refusal"] = self.write(
                "sketch.fix-center",
                {"sketch_id": origin_sketch},
                expected_error="UnsupportedCenterConstraint",
                **origin_write,
            )
            require(
                self.stamp(origin_id) == origin_stamp, "origin refusal changed stamp"
            )
            inspected = self.call(
                "sketch.inspect",
                {"sketch_id": origin_sketch},
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
