"""Targeted installed client -> daemon -> COM-worker STL calibration.

Disposable GitHub runner only; one host, 600s requests, 1800s group, no native
retry/restart. Native .SLDPRT save/reopen and actual STL bytes are mandatory.
This internal calibration is not full/public acceptance.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time
import traceback

from swcli.daemon.client import call_daemon
from swcli.result_schemas import validate_operation_result
from swcli.hosts.export_validation import export_file_valid


# Explicit calibration requests derived from retained native 33.5.0 readback,
# run 42266554774; 0.5 mm itself was rejected and is not treated as success.
COARSE_DEVIATION_MM = 0.5335936864527374
FINE_DEVIATION_MM = 0.015392125570752039
COARSE_ANGLE_DEGREES = 30
FINE_ANGLE_DEGREES = 10

def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def mesh_metrics(path, *, unit, expected_encoding):
    require(export_file_valid("STL", path), "invalid actual STL content")
    raw = path.read_bytes()
    triangles = []
    binary = len(raw) >= 84 and len(raw) == 84 + 50 * struct.unpack_from("<I", raw, 80)[0]
    if binary:
        for offset in range(84, len(raw), 50):
            values = struct.unpack_from("<12fH", raw, offset)
            triangles.append(tuple(tuple(values[i:i+3]) for i in (3, 6, 9)))
    else:
        vertices = [tuple(map(float, line.split()[1:])) for line in raw.decode("ascii").splitlines()
                    if line.split()[:1] == ["vertex"]]
        triangles = [tuple(vertices[i:i+3]) for i in range(0, len(vertices), 3)]
    require(binary == (expected_encoding == "binary"), "STL encoding did not follow its parameter")
    scale = {"mm": 1, "cm": 10, "m": 1000, "inch": 25.4, "foot": 304.8}[unit]
    triangles = [tuple(tuple(v * scale for v in point) for point in tri) for tri in triangles]
    vertices = [p for tri in triangles for p in tri]
    minimum = [min(p[i] for p in vertices) for i in range(3)]
    maximum = [max(p[i] for p in vertices) for i in range(3)]
    spans = [b-a for a,b in zip(minimum,maximum)]
    # Front-plane cylinder has a 20 mm circular diameter and 15 mm height.
    axial = min(range(3), key=lambda i: abs(spans[i] - 15))
    radial = [i for i in range(3) if i != axial]
    require(abs(spans[axial] - 15) < 0.001 and all(abs(spans[i] - 20) < 0.5 for i in radial),
            "STL coordinate extents do not match requested output units / cylinder")
    center = [(minimum[i] + maximum[i]) / 2 for i in range(3)]
    chord_errors = []
    volume = 0.0
    for a,b,c in triangles:
        # Determinant volume works regardless of STL's translated origin.
        volume += (a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0])
                   + a[2]*(b[0]*c[1]-b[1]*c[0])) / 6
        for p,q in ((a,b),(b,c),(c,a)):
            rp = math.hypot(*(p[i]-center[i] for i in radial))
            rq = math.hypot(*(q[i]-center[i] for i in radial))
            # Side edges connect adjacent tessellated circular points. Cap
            # diagonals also have radius-10 endpoints: remove long chords
            # and edges lying in a cap plane (handled by volume separately).
            if abs(rp-10) < 0.001 and abs(rq-10) < 0.001 and abs(p[axial]-q[axial]) > 1:
                mid = [(p[i]+q[i])/2-center[i] for i in radial]
                chord_errors.append(max(0.0, 10-math.hypot(*mid)))
    require(chord_errors, "curved wall chord measurements are missing")
    expected_volume = math.pi * 10**2 * 15
    volume = abs(volume)
    return dict(sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw),
                triangle_count=len(triangles), encoding="binary" if binary else "ascii", unit=unit,
                spans_mm=spans, max_wall_chord_error_mm=max(chord_errors),
                volume_mm3=volume, analytic_volume_mm3=expected_volume,
                volume_relative_error=abs(volume-expected_volume)/expected_volume)


async def mcp_stdio_export(endpoint, context, options, path, error_log):
    """Use the official MCP client against the installed public stdio server."""
    from datetime import timedelta
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    parameters = StdioServerParameters(command=sys.executable, args=[
        "-I", "-m", "swcli", "--endpoint", endpoint, "--session", "stl-calibration",
        "--request-timeout", "600", "mcp", "serve"],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    with error_log.open("a", encoding="utf-8") as errors:
        async with stdio_client(parameters, errlog=errors) as streams:
            async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=610)) as session:
                initialized = await session.initialize()
                tools = [tool.name for tool in (await session.list_tools()).tools]
                require(initialized.serverInfo.name == "swcli" and "execute" in tools,
                        "installed public MCP server discovery failed")
                reply = await session.call_tool("execute", {"operation": "document.export",
                    "parameters": dict(output=str(path), strict=True, stl_options=options, include_content=False), **context})
                payload = reply.structuredContent
                require(isinstance(payload, dict) and reply.content
                        and json.loads(reply.content[0].text) == payload,
                        "MCP structured/text receipts differ")
                return payload, dict(transport="official-sdk-stdio", server_name=initialized.serverInfo.name,
                                     protocol_version=initialized.protocolVersion, tools=tools, is_error=reply.isError)


def configuration_trace_proof(path, request_id):
    """Prove the existing legal STL request used modern source configuration reads."""
    records = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
               if line.startswith('{')]
    records = [r for r in records if r.get("event") == "swcli.native-call"]
    rows = [r for r in records if r.get("request_id") == request_id]
    require(rows and all(r.get("operation") == "document.export" for r in rows), "STL request trace missing")
    begins = [(r["sequence"], r["call"]) for r in rows if r["phase"] == "begin"]
    ends = [(r["sequence"], r["call"]) for r in rows if r["phase"] == "end"]
    require(sorted(begins) == sorted(ends) and len(set(begins)) == len(begins)
            and all(r["phase"] in ("begin", "end") for r in rows)
            and len({r["worker_pid"] for r in rows}) == 1, "STL native trace failed or incomplete")
    calls = [r["call"] for r in rows if r["phase"] == "begin"]
    require("GetActiveConfiguration" not in calls, "STL source guard used obsolete configuration getter")
    modern = [call for call in calls if call in ("ConfigurationManager", "ActiveConfiguration", "Name")]
    triples = sum(calls[i:i+3] == ["ConfigurationManager", "ActiveConfiguration", "Name"] for i in range(len(calls)-2))
    require(triples >= 2, "STL source guard lacks modern before/after configuration evidence")
    return dict(request_id=request_id, modern_configuration_triples=triples,
                observations=modern, native_trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--phase", choices=("internal", "public"), default="internal")
    args = parser.parse_args(argv)
    require(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("RUNNER_OS") == "Windows",
            "calibration requires a disposable GitHub Windows runner")
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / "stl-calibration.json"
    require(not report_path.exists(), "evidence directory was already used; do not overwrite original evidence")
    report = dict(success=False, scope=("internal-stl-options-calibration" if args.phase == "internal" else "public-isolated-stl-options"), public_acceptance=False,
                  full_acceptance=False, source_commit=os.environ.get("GITHUB_SHA"),
                  native_timeout_seconds=600, group_timeout_seconds=1800, events=[], cases=[], cleanup_errors=[])
    started = time.monotonic()
    documents = {}
    leases = {}
    endpoint = None
    daemon = None
    def checkpoint():
        next_report = report_path.with_name("stl-calibration.next.json")
        next_report.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        next_report.replace(report_path)
    def call(operation, parameters=None, *, document=None, expected=None):
        require(time.monotonic()-started < 1800, "STL group exceeded 1800 seconds")
        context = {}
        if document:
            context["document_id"] = document
            if document in leases:
                context["lease_id"] = leases[document]
                context["expected_update_stamp"] = documents[document]["update_stamp"]
        event = dict(operation=operation, parameters=parameters or {}, context=context, state="started")
        report["events"].append(event)
        checkpoint()
        response = call_daemon(operation, parameters, endpoint=endpoint, session_id="stl-calibration",
                               timeout_seconds=600, **context)
        event.update(response=response, state="completed")
        result = response.get("result")
        if result is not None:
            validate_operation_result(operation, result)
        if expected:
            require(not response.get("success") and response.get("error", {}).get("code") == expected,
                    "expected guard rejection missing: " + str(response))
        else:
            require(response.get("success") is True, "first native operation failure: " + str(response))
        if isinstance(result, dict) and "document" in result:
            documents[result["document"]["document_id"]] = result["document"]
        if operation == "document.lease.acquire":
            leases[document] = result["lease"]["lease_id"]
        if operation == "document.close" and not expected:
            documents.pop(document, None)
            leases.pop(document, None)
        checkpoint()
        return result
    def lease(document):
        call("document.lease.acquire", {"ttl_seconds": 3600}, document=document)
    def cli_export(document, path, options, route="cli"):
        require(time.monotonic()-started < 1800, "STL group exceeded 1800 seconds")
        if route != "cli":
            event = dict(route=route, operation="document.export", options=options, path=str(path), state="started")
            report["events"].append(event)
            checkpoint()
            context = dict(document_id=document, expected_update_stamp=documents[document]["update_stamp"],
                           lease_id=leases[document])
            if route == "sdk":
                from swcli.sdk import Client
                response = Client(endpoint=endpoint, session_id="stl-calibration", timeout_seconds=600).document.export(
                    output=str(path), strict=True, stl_options=options, **context)
                event["response"] = dict(response.raw)
                checkpoint()
                result = dict(response.require_result())
                result["request_id"] = response.request_id
            else:
                import asyncio
                response, transport = asyncio.run(asyncio.wait_for(
                    mcp_stdio_export(endpoint, context, options, path, root / "mcp.stderr.log"), timeout=615))
                event["response"] = response
                event["mcp_transport"] = transport
                checkpoint()
                require(response.get("success") is True and not transport["is_error"],
                        "first MCP STL failure: " + str(response))
                result = {**response["result"], "request_id": response["request_id"]}
            event.update(result=result, state="completed")
            documents[document] = result["document"]
            checkpoint()
            return result

        argv = [sys.executable, "-I", "-m", "swcli", "--endpoint", endpoint, "--session", "stl-calibration",
                "--request-timeout", "600", "document", "export", str(path), "--document", document,
                "--if-update-stamp", str(documents[document]["update_stamp"]), "--lease", leases[document],
                "--strict", "--stl-encoding", options["encoding"], "--stl-unit", options["unit"],
                "--stl-deviation-mm", str(options["deviation_mm"]), "--stl-angle-degrees", str(options["angle_degrees"]), "--json"]
        event = dict(command=argv, state="started")
        report["events"].append(event)
        checkpoint()
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=615)
        event.update(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
        result = json.loads(completed.stdout)
        event["result"] = result
        event["state"] = "completed"
        checkpoint()
        require(completed.returncode == 0 and result.get("ok") is True, "first CLI STL failure: " + str(result))
        business = {k:v for k,v in result.items() if k not in ("request_id", "replayed")}
        validate_operation_result("document.export", business)
        documents[document] = result["document"]
        return result
    checkpoint()
    try:
        probe = subprocess.run(["tasklist.exe", "/FI", "IMAGENAME eq SLDWORKS.exe", "/FO", "CSV", "/NH"],
                               capture_output=True, text=True, check=True, timeout=10)
        report["initial_process_inventory"] = probe.stdout
        require('"sldworks.exe"' not in probe.stdout.lower(), "runner already has SOLIDWORKS; refusing attachment")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        endpoint = "127.0.0.1:" + str(port)
        env = {**os.environ, "SWCLI_STL_SWCONST": str(args.swconst.resolve()),
               "SWCLI_TRACE_NATIVE_CALLS": "1", "PYTHONIOENCODING": "utf-8"}
        env.pop("SWCLI_STL_CALIBRATION", None)
        env.pop("SWCLI_STL_EXCLUSIVE_RUNNER", None)
        if args.phase == "internal":
            env["SWCLI_STL_CALIBRATION"] = "1"
        else:
            env["SWCLI_STL_EXCLUSIVE_RUNNER"] = "1"
        report["daemon_export_mode"] = dict(internal_calibration="SWCLI_STL_CALIBRATION" in env,
                                          explicit_exclusive_runner="SWCLI_STL_EXCLUSIVE_RUNNER" in env)
        with (root / "daemon.stdout.log").open("w") as stdout, (root / "daemon.stderr.log").open("w") as stderr:
            daemon = subprocess.Popen([sys.executable, "-I", "-m", "swcli", "daemon", "serve", "--host", "127.0.0.1",
                                      "--port", str(port), "--tray", "off", "--startup-timeout", "600"],
                                     env=env, stdout=stdout, stderr=stderr)
            deadline = time.monotonic()+600
            while True:
                require(daemon.poll() is None, "single owned daemon exited during startup; see original logs")
                try:
                    health = call_daemon("daemon.health", endpoint=endpoint, timeout_seconds=1)
                except (OSError, ConnectionError):
                    health = None
                if health and health.get("success"):
                    if health["result"].get("host_connected"):
                        break
                require(time.monotonic() < deadline, "single daemon startup timed out")
                time.sleep(1)
            report["health"] = health
            host = health["result"]["host"]
            require(host["owned_by_daemon"] is True and host["visible"] is False, "host is not owned and hidden")
            made = call("document.create", {"type": "part"})
            doc = made["document"]["document_id"]
            lease(doc)
            sketch = call("sketch.circle", {"plane": "front", "radius_mm": 10}, document=doc)
            call("feature.extrude", {"sketch_id": sketch["sketch"]["sketch_id"], "depth_mm": 15}, document=doc)
            native = root / "curved-cylinder.SLDPRT"
            call("document.save-as", {"output": str(native)}, document=doc)
            digest = hashlib.sha256(native.read_bytes()).hexdigest()
            call("document.close", {"discard": False}, document=doc)
            opened = call("document.open", {"path": str(native)})
            doc = opened["document"]["document_id"]
            lease(doc)
            report["saved_reopened_fixture"] = dict(path=str(native), sha256=digest, open_result=opened)
            front = call("document.create", {"type": "part"})["document"]["document_id"]
            lease(front)
            plan = [
                ("coarse", dict(encoding="binary", unit="mm", deviation_mm=COARSE_DEVIATION_MM, angle_degrees=COARSE_ANGLE_DEGREES)),
                ("deviation-fine", dict(encoding="binary", unit="mm", deviation_mm=FINE_DEVIATION_MM, angle_degrees=COARSE_ANGLE_DEGREES)),
                ("angle-fine", dict(encoding="binary", unit="mm", deviation_mm=COARSE_DEVIATION_MM, angle_degrees=FINE_ANGLE_DEGREES)),
                ("fine", dict(encoding="binary", unit="mm", deviation_mm=FINE_DEVIATION_MM, angle_degrees=FINE_ANGLE_DEGREES)),
                ("ascii-inch", dict(encoding="ascii", unit="inch", deviation_mm=FINE_DEVIATION_MM, angle_degrees=FINE_ANGLE_DEGREES)),
                ("binary-meter", dict(encoding="binary", unit="m", deviation_mm=FINE_DEVIATION_MM, angle_degrees=FINE_ANGLE_DEGREES)),
            ]
            if args.phase == "public":
                require("SWCLI_STL_CALIBRATION" not in env, "public gate must not enable internal calibration")
                from swcli.stl_calibrated_profiles import QUALIFICATION
                report["qualification"] = QUALIFICATION
                fine_options = dict(encoding="binary", unit="mm", deviation_mm=FINE_DEVIATION_MM, angle_degrees=FINE_ANGLE_DEGREES)
                plan.extend([("sdk-fine", fine_options), ("mcp-fine", fine_options)])
                report["negative_guards"] = []
                def refuse(label, *, options=None, stamp=None, session="stl-calibration", expected):
                    path = root / ("refused-"+label+".stl")
                    response = call_daemon("document.export", dict(output=str(path), stl_options=options or fine_options),
                        endpoint=endpoint, session_id=session, timeout_seconds=600, document_id=doc,
                        expected_update_stamp=documents[doc]["update_stamp"] if stamp is None else stamp,
                        lease_id=leases[doc])
                    report["negative_guards"].append(dict(name=label, response=response, expected_error=expected))
                    checkpoint()
                    require(response.get("success") is False and response.get("error", {}).get("code") == expected,
                            "public negative guard did not refuse before setters: " + str(response))
                    require(not path.exists(), "guard refusal published an output")
                    if "result" in response:
                        validate_operation_result("document.export", response["result"])
                refuse("stale-stamp", stamp=documents[doc]["update_stamp"]+1, expected="DocumentUpdateConflict")
                refuse("foreign-lease", session="foreign-session", expected="DocumentLeaseConflict")
                refuse("uncalibrated-profile", options={**fine_options, "deviation_mm": 0.2}, expected="StlOptionsProfileUncalibrated")
            baseline_preferences = None
            for name, options in plan:
                path = root / (name + ".stl")
                case = dict(name=name, options=options, path=str(path), success=False)
                report["cases"].append(case)
                checkpoint()
                route = "sdk" if name == "sdk-fine" else "mcp" if name == "mcp-fine" else "cli"
                result = cli_export(doc, path, options, route=route)
                source_state = result["stl_source_state"]
                require(source_state["unchanged"] is True and source_state["before"] == source_state["after"]
                        and isinstance(source_state["before"]["configuration"], str)
                        and bool(source_state["before"]["configuration"].strip()), "STL source configuration/state changed")
                case["configuration_trace"] = configuration_trace_proof(root / "daemon.stderr.log", result["request_id"])
                case["route"] = route
                if route == "mcp":
                    case["mcp_transport"] = report["events"][-1]["mcp_transport"]
                case["result"] = result
                if args.phase == "public":
                    require(result["stl_preferences"].get("execution_mode") == "public-isolated",
                            "public export used an internal or unqualified worker mode")
                    catalog = call("document.list")
                    case["post_export_catalog"] = catalog
                    require([row["document_id"] for row in catalog["documents"] if row["active"]] == [front]
                            and [row["document_id"] for row in catalog["documents"] if row["current"]] == [front],
                            "public export did not restore exact foreground/session-current identity")
                require(result["document"]["document_id"] == doc and result["document"]["active"] is False,
                        "STL export did not preserve background source/foreground identity")
                prefs = result["stl_preferences"]
                require(prefs["restored"] and prefs["before"] == prefs["after"] and not prefs["cleanup_errors"],
                        "global STL preferences were not restored")
                if baseline_preferences is None:
                    baseline_preferences = prefs["before"]
                require(prefs["before"] == baseline_preferences, "global preferences leaked between exports")
                case["mesh"] = mesh_metrics(path, unit=options["unit"], expected_encoding=options["encoding"])
                require(case["mesh"]["max_wall_chord_error_mm"] <= options["deviation_mm"] + 0.001,
                        "actual curved mesh exceeds deviation parameter")
                case["success"] = True
                checkpoint()
            cases = {case["name"]:case["mesh"] for case in report["cases"]}
            coarse, fine = cases["coarse"], cases["fine"]
            for name in ("deviation-fine", "angle-fine", "fine"):
                require(cases[name]["triangle_count"] > coarse["triangle_count"], "individual STL tolerance did not refine triangle count: " + name)
                require(cases[name]["volume_relative_error"] < coarse["volume_relative_error"], "tolerance did not improve analytic mesh volume: " + name)
            require(fine["max_wall_chord_error_mm"] < coarse["max_wall_chord_error_mm"], "refinement did not improve curved wall error")
            for name in (("ascii-inch", "binary-meter", "sdk-fine", "mcp-fine") if args.phase == "public"
                         else ("ascii-inch", "binary-meter")):
                require(cases[name]["triangle_count"] == fine["triangle_count"], "unit/encoding changed tessellation")
                require(abs(cases[name]["volume_mm3"]-fine["volume_mm3"]) / fine["volume_mm3"] < 1e-4,
                        "unit/encoding geometric scale mismatch")
            require(hashlib.sha256(native.read_bytes()).hexdigest() == digest, "exports modified saved source bytes")
            if args.phase == "public":
                call("document.close", {"discard": False}, document=doc)
                readonly = call("document.open", {"path": str(native), "read_only": True})
                doc = readonly["document"]["document_id"]
                lease(doc)
                refuse("read-only-source", expected="DocumentReadOnly")
                require(hashlib.sha256(native.read_bytes()).hexdigest() == digest, "read-only refusal changed source bytes")
            call("document.close", {"discard": False}, document=front)
            call("document.close", {"discard": False}, document=doc)
            report["shutdown"] = call_daemon("daemon.shutdown", endpoint=endpoint, timeout_seconds=600)
            require(report["shutdown"]["success"], "owned daemon shutdown failed")
            daemon.wait(timeout=30)
            report.update(success=True, public_acceptance=args.phase == "public", elapsed_seconds=time.monotonic()-started)
    except BaseException as exc:
        report["error"] = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
        raise
    finally:
        # No CAD rollback, retry, or replacement host after the first failure.
        if daemon is not None and daemon.poll() is None:
            report["cleanup_errors"].append(dict(stage="host-retained-on-failure", message="remaining owned resources are recorded for runner cleanup"))
        if report["cleanup_errors"]:
            report["success"] = False
        checkpoint()

if __name__ == "__main__":
    main()
