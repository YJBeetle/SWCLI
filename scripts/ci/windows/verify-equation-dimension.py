"""TEST ONLY: prove native equation ownership cannot be overwritten by typed edits.

The public daemon creates and owns the fixture document. The only direct COM
mutation is adding an equation to that exact fixture and rebuilding it; there
is no Dispatch, host startup/shutdown, eval or production raw-COM entry point.
Run with the installed package on Windows while its daemon is already ready.
"""

from __future__ import annotations

import argparse
import json
import math
import ntpath
from pathlib import Path
import sys
import uuid

from swcli.daemon.client import DEFAULT_ENDPOINT, call_daemon
from swcli.hosts.windows import PROG_ID, _com_value


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def close_enough(actual, expected, message):
    require(
        isinstance(actual, (int, float))
        and not isinstance(actual, bool)
        and math.isfinite(actual)
        and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-6),
        message,
    )


def add_native_equation(*, process_id, document_descriptor, native_name):
    """Attach to the exact existing host and mutate only its fresh active fixture."""
    import pythoncom
    import win32com.client

    require(
        isinstance(process_id, int)
        and not isinstance(process_id, bool)
        and process_id > 0,
        "daemon did not report an exact SOLIDWORKS process ID",
    )
    require(
        isinstance(native_name, str)
        and native_name.count("@") >= 2
        and not any(character in native_name for character in ('"', "\r", "\n")),
        "fixture requires an unambiguous native dimension name",
    )
    pythoncom.CoInitialize()
    app = document = manager = None
    try:
        # GetActiveObject never starts a missing host. Refuse a different ROT
        # instance rather than falling back to Dispatch or an active document.
        app = win32com.client.GetActiveObject(PROG_ID)
        require(
            int(_com_value(app, "GetProcessID")) == process_id,
            "ROT SOLIDWORKS PID differs from the daemon-owned fixture host",
        )
        document = _com_value(app, "ActiveDoc")
        require(document is not None, "fixture document is not active")
        title = str(_com_value(document, "GetTitle"))
        path = str(_com_value(document, "GetPathName"))
        require(
            title == document_descriptor["title"]
            and ntpath.normcase(ntpath.normpath(path))
            == ntpath.normcase(ntpath.normpath(document_descriptor["path"]))
            and int(_com_value(document, "GetType")) == 1,
            "active document is not the exact fresh part created by this gate",
        )
        configurations = tuple(_com_value(document, "GetConfigurationNames") or ())
        require(
            len(configurations) == 1, "Add2 fixture requires one fresh configuration"
        )
        require(
            _com_value(_com_value(document, "SketchManager"), "ActiveSketch") is None,
            "fixture must not overwrite or exit an existing sketch edit",
        )
        configuration = str(
            _com_value(
                _com_value(document, "ConfigurationManager"), "ActiveConfiguration"
            ).Name
        )
        manager = _com_value(document, "GetEquationMgr")
        require(manager is not None, "native equation manager is unavailable")
        count_before = int(_com_value(manager, "GetCount"))
        require(
            count_before == 0, "fixture part unexpectedly already contains equations"
        )
        alias = native_name.rsplit("@", 1)[0]
        expression = f'"{alias}" = 16mm'
        index = int(manager.Add2(-1, expression, True))
        require(index >= 0, "SOLIDWORKS rejected the fixture dimension equation")
        require(
            bool(_com_value(document, "EditRebuild3")),
            "equation fixture did not rebuild",
        )
        # EquationMgr is configuration-associated. Reacquire after the native
        # rebuild; inspect the indexed property using the same late binding as
        # the production equation-ownership guard, not a generated interop shim.
        manager = _com_value(document, "GetEquationMgr")
        require(manager is not None, "equation manager disappeared after rebuild")
        count_after = int(_com_value(manager, "GetCount"))
        require(
            count_after == count_before + 1 and index < count_after,
            "native equation count/index did not match the fixture addition",
        )
        native_expression = str(manager.Equation(index))
        require(
            native_expression.split("=", 1)[0].strip() == f'"{alias}"',
            "indexed native Equation getter returned a different assignment target",
        )
        require(
            str(
                _com_value(
                    _com_value(document, "ConfigurationManager"), "ActiveConfiguration"
                ).Name
            )
            == configuration,
            "fixture unexpectedly switched configuration",
        )
        return {
            "process_id": process_id,
            "document_title": title,
            "document_path": path,
            "configuration": configuration,
            "count_before": count_before,
            "count_after": count_after,
            "equation_index": index,
            "equation": native_expression,
            "binding": "native-indexed-Equation-property",
        }
    finally:
        manager = document = app = None
        pythoncom.CoUninitialize()


class EquationSmoke:
    def __init__(self, *, endpoint, session_id, fixture=add_native_equation):
        self.endpoint = endpoint
        self.session_id = session_id
        self.fixture = fixture
        self.owned_document_id = None
        self.record = {"session_id": session_id, "endpoint": endpoint, "events": []}

    def call(self, operation, parameters=None, *, expected_error=None, **context):
        response = call_daemon(
            operation,
            parameters,
            endpoint=self.endpoint,
            timeout_seconds=120,
            session_id=self.session_id,
            **context,
        )
        self.record["events"].append({"operation": operation, "response": response})
        if operation == "document.create":
            partial = response.get("result")
            if isinstance(partial, dict):
                document = partial.get("document")
                if isinstance(document, dict) and isinstance(
                    document.get("document_id"), str
                ):
                    self.owned_document_id = document["document_id"]
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

    def stamp(self, document_id):
        result = self.call("document.inspect", document_id=document_id)
        stamp = result["document"]["update_stamp"]
        require(
            isinstance(stamp, int) and not isinstance(stamp, bool),
            "native update stamp is unavailable",
        )
        return stamp

    def observe(self, document_id, sketch_id, dimension_id, equation_index):
        dimension = self.call(
            "dimension.inspect", {"dimension_id": dimension_id}, document_id=document_id
        )
        description = dimension["dimension"]
        require(
            description["dimension_id"] == dimension_id
            and description["sketch_id"] == sketch_id
            and description["kind"] == "diameter"
            and description["unit"] == "millimeter"
            and not dimension["editing"]
            and dimension["equation_control"]["controlled"]
            and equation_index in dimension["equation_control"]["equation_indices"],
            "typed dimension inspect did not retain exact equation-controlled identity",
        )
        close_enough(description["value"], 16, "equation-owned native diameter changed")
        circle = self.call(
            "sketch.inspect", {"sketch_id": sketch_id}, document_id=document_id
        )
        require(
            circle["geometry_complete"]
            and not circle["editing"]
            and circle["coordinate_system"] == "sketch-local"
            and circle["profile_segment_count"] == 1
            and circle["segment_count"] == 1
            and circle["sketch"]["absorbed"],
            "equation-owned sketch observation is incomplete or ambiguous",
        )
        segment = circle["segments"][0]
        geometry = segment["geometry"]
        require(
            not segment["construction"]
            and geometry["kind"] == "arc"
            and geometry["complete_circle"],
            "equation-owned profile is not one complete circle",
        )
        close_enough(geometry["radius_mm"], 8, "equation-owned circle radius changed")
        for axis, value in (("x", 3), ("y", 4), ("z", 0)):
            close_enough(
                geometry["center_mm"][axis],
                value,
                "equation-owned circle center changed",
            )
        measurement = self.call("document.measure", document_id=document_id)
        metrics = measurement["metrics"]
        require(
            metrics["solid_body_count"] == 1,
            "equation-owned cylinder lost its solid body",
        )
        close_enough(
            metrics["volume_mm3"],
            math.pi * 8**2 * 10,
            "equation-owned cylinder volume changed",
        )
        close_enough(
            metrics["surface_area_mm2"],
            2 * math.pi * 8 * (8 + 10),
            "equation-owned cylinder surface area changed",
        )
        return {"dimension": dimension, "sketch": circle, "measurement": measurement}

    def run(self):
        health = self.call("daemon.health")
        require(
            health.get("host_connected") and health.get("host"),
            "existing SOLIDWORKS daemon host is disconnected",
        )
        require(
            all(
                operation in health["operations"]
                for operation in (
                    "sketch.dimension-diameter",
                    "dimension.inspect",
                    "dimension.set",
                )
            ),
            "daemon does not provide the driving-dimension operations",
        )
        created = self.call("document.create", {"type": "part"})
        document_id = created["document"]["document_id"]
        self.owned_document_id = document_id
        write = {"document_id": document_id}
        circle = self.call(
            "sketch.circle",
            {"plane": "front", "radius_mm": 5, "center_x_mm": 3, "center_y_mm": 4},
            **write,
        )
        sketch_id = circle["sketch"]["sketch_id"]
        diameter = self.call(
            "sketch.dimension-diameter",
            {"sketch_id": sketch_id, "diameter_mm": 16},
            **write,
        )
        dimension_id = diameter["dimension"]["dimension_id"]
        self.call("feature.extrude", {"sketch_id": sketch_id, "depth_mm": 10}, **write)
        descriptor = self.call("document.inspect", **write)["document"]
        require(
            descriptor["document_id"] == document_id and descriptor["active"],
            "created fixture document is no longer the exact active document",
        )
        # Confirm host identity again immediately before the private native
        # mutation rather than trusting the initial health snapshot forever.
        current_health = self.call("daemon.health")
        require(
            current_health.get("host_connected") and current_health.get("host"),
            "daemon host disconnected before fixture attachment",
        )
        require(
            current_health["host"]["process_id"] == health["host"]["process_id"],
            "daemon host was replaced during fixture setup",
        )
        native = self.fixture(
            process_id=current_health["host"]["process_id"],
            document_descriptor=descriptor,
            native_name=diameter["dimension"]["native_name"],
        )
        self.record["native_fixture"] = native
        require(
            isinstance(native.get("equation_index"), int)
            and native["equation_index"] >= 0,
            "fixture returned an invalid native equation index",
        )
        before_stamp = self.stamp(document_id)
        before = self.observe(
            document_id, sketch_id, dimension_id, native["equation_index"]
        )
        require(
            self.stamp(document_id) == before_stamp,
            "read-only equation observation changed native update stamp",
        )
        rejection = self.call(
            "dimension.set",
            {"dimension_id": dimension_id, "value_mm": 20},
            expected_error="DimensionExternallyControlled",
            expected_update_stamp=before_stamp,
            **write,
        )
        after = self.observe(
            document_id, sketch_id, dimension_id, native["equation_index"]
        )
        after_stamp = self.stamp(document_id)
        require(
            after_stamp == before_stamp,
            "rejected equation-owned edit changed native update stamp",
        )
        require(
            before["sketch"]["segments"] == after["sketch"]["segments"]
            and before["measurement"]["metrics"] == after["measurement"]["metrics"],
            "rejected equation-owned edit changed exact observed geometry",
        )
        self.record.update(
            document_id=document_id,
            sketch_id=sketch_id,
            dimension_id=dimension_id,
            before=before,
            rejection=rejection,
            after=after,
            update_stamp_before=before_stamp,
            update_stamp_after=after_stamp,
        )

    def cleanup(self):
        errors = []
        if self.owned_document_id is not None:
            try:
                self.call(
                    "document.close",
                    {"discard": True},
                    document_id=self.owned_document_id,
                )
                self.owned_document_id = None
            except Exception as exc:
                errors.append(
                    {"document_id": self.owned_document_id, "message": str(exc)}
                )
        self.record["cleanup_errors"] = errors
        return errors


def run_gate(*, endpoint, session_id, output_dir=None, fixture=add_native_equation):
    smoke = EquationSmoke(endpoint=endpoint, session_id=session_id, fixture=fixture)
    stream = None
    smoke.record["evidence_path"] = None
    if output_dir is not None:
        directory = Path(output_dir).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
        record_path = directory / "equation-dimension-result.json"
        smoke.record["evidence_path"] = str(record_path)
        # Reserve and exercise the evidence destination before touching the
        # daemon. Existing proof is never replaced, even on a failed rerun.
        stream = record_path.open("x", encoding="utf-8")
        try:
            _write_record(
                stream, {**smoke.record, "success": False, "status": "running"}
            )
        except Exception:
            try:
                stream.close()
            except OSError:
                pass
            raise
    failure = None
    try:
        smoke.run()
    except Exception as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
        smoke.record["failure"] = failure
    finally:
        cleanup_errors = smoke.cleanup()
    smoke.record["success"] = failure is None and not cleanup_errors
    if stream is not None:
        try:
            _write_record(stream, smoke.record)
        except Exception as exc:
            _evidence_failure(smoke.record, exc)
        finally:
            try:
                stream.close()
            except Exception as exc:
                _evidence_failure(smoke.record, exc)
    return smoke.record


def _write_record(stream, record):
    stream.seek(0)
    json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
    stream.write("\n")
    stream.truncate()
    stream.flush()


def _evidence_failure(record, exc):
    error = {"type": type(exc).__name__, "message": str(exc)}
    record.setdefault("evidence_errors", []).append(error)
    record.setdefault("failure", {"type": "EvidenceWriteFailed", "message": str(exc)})
    record["success"] = False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--session", default="equation-smoke-" + uuid.uuid4().hex[:12])
    parser.add_argument(
        "--output-dir", help="local directory for the UTF-8 evidence record"
    )
    arguments = parser.parse_args(argv)
    try:
        record = run_gate(
            endpoint=arguments.endpoint,
            session_id=arguments.session,
            output_dir=arguments.output_dir,
        )
    except Exception as exc:
        record = {
            "success": False,
            "failure": {"type": type(exc).__name__, "message": str(exc)},
            "cleanup_errors": [],
            "evidence_path": (
                str(
                    Path(arguments.output_dir).expanduser().resolve()
                    / "equation-dimension-result.json"
                )
                if arguments.output_dir is not None
                else None
            ),
        }
    # Full runtime health includes every operation Schema: keep that proof in
    # the evidence file, not in CI's routine stdout or the agent's tool output.
    summary = {
        "success": record["success"],
        "failure": record.get("failure"),
        "cleanup_errors": record.get("cleanup_errors", []),
        "evidence_path": record.get("evidence_path"),
    }
    if "evidence_errors" in record:
        summary["evidence_errors"] = record["evidence_errors"]
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False))
    return 0 if record["success"] else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
