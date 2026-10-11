"""Daily positive geometry cases; shared protocol guards run on Front."""


from gate_support.driving_checks import (
    LEASE_TTL_SECONDS,
    require,
    close_enough,
    assert_dimension,
    assert_measurement,
    assert_fixed_center,
    assert_linear_dimension,
)


class GeometryCases:
    def plane_geometry(self, plane):
        """Positive geometry on non-front planes; shared guards run on front."""
        document = self.create()
        lease = self.call("document.lease.acquire", {"ttl_seconds": LEASE_TTL_SECONDS},
                          document_id=document)["lease"]["lease_id"]
        sketch = self.write("sketch.circle", {
            "plane": plane, "radius_mm": 5, "center_x_mm": 3, "center_y_mm": 4,
        }, document_id=document, lease_id=lease)["sketch"]["sketch_id"]
        dimension = self.write("sketch.dimension-diameter", {
            "sketch_id": sketch, "diameter_mm": 16,
        }, document_id=document, lease_id=lease)["dimension"]["dimension_id"]
        self.observe(document, sketch, dimension, 16, absorbed=False)
        self.write("feature.extrude", {"sketch_id": sketch, "depth_mm": 10},
                   document_id=document, lease_id=lease)
        changed = self.write("dimension.set", {"dimension_id": dimension, "value_mm": 20},
                             document_id=document, lease_id=lease)
        assert_dimension(changed, dimension, sketch, 20)
        self.observe(document, sketch, dimension, 20, absorbed=True)
        cylinder = self.call("document.measure", document_id=document)
        assert_measurement(cylinder, 10)
        self.close(document)
        self.require_empty(f"plane.{plane}.circle-geometry")

        document = self.create()
        lease = self.call("document.lease.acquire", {"ttl_seconds": LEASE_TTL_SECONDS},
                          document_id=document)["lease"]["lease_id"]
        sketch = self.write("sketch.rectangle", {
            "plane": plane, "width_mm": 40, "height_mm": 30,
            "center_x_mm": 3, "center_y_mm": 4,
        }, document_id=document, lease_id=lease)["sketch"]["sketch_id"]
        fixed = self.write("sketch.fix-center", {"sketch_id": sketch}, document_id=document, lease_id=lease)
        assert_fixed_center(fixed, sketch, created=True)
        dimensions = self.write("sketch.dimension-rectangle", {
            "sketch_id": sketch, "width_mm": 40, "height_mm": 30,
        }, document_id=document, lease_id=lease)["dimensions"]
        ids = {kind: dimensions[kind]["dimension_id"] for kind in ("width", "height")}
        require(len(set(ids.values())) == 2, "width/height share a wire dimension ID")
        self.write("feature.extrude", {"sketch_id": sketch, "depth_mm": 10},
                   document_id=document, lease_id=lease)
        for kind, value in (("width", 50), ("height", 35)):
            self.write("dimension.set", {"dimension_id": ids[kind], "value_mm": value},
                       document_id=document, lease_id=lease)
        for kind, dimension in ids.items():
            observed = self.call("dimension.inspect", {"dimension_id": dimension},
                                 document_id=document)
            assert_linear_dimension(observed, dimension, sketch, kind, 50, 35)
        rectangle = self.call("document.measure", document_id=document)
        require(rectangle["metrics"]["solid_body_count"] == 1, "rectangle body count changed")
        close_enough(rectangle["metrics"]["volume_mm3"], 50 * 35 * 10,
                     "rectangle dimensions did not drive the solid")
        self.record["planes"].append({"plane": plane, "coverage": "geometry",
                                     "cylinder_metrics": cylinder["metrics"],
                                     "rectangle_metrics": rectangle["metrics"]})
        self.close(document)
