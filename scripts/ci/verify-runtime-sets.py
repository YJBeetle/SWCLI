"""Shared functional CAD sets with one fresh daemon/owned SW per set.

Install/container/renderer preparation remains platform-owned. The plan,
functional scripts, ownership checks and set-boundary restarts are shared by
all three platforms. Never retry a failed operation or restart inside a set.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_support.runtime_plan import runtime_plan
from gate_support.model_checks import host_directory, require
from gate_support.host_processes import solidworks_process_ids

SCRIPTS = Path(__file__).resolve().parent


class DaemonUnavailable(RuntimeError):
    """Only a positively refused connection, never an arbitrary health failure."""


class DaemonStarting(RuntimeError):
    """The foreground daemon has bound its endpoint but is not ready yet."""


class DaemonTransportPending(RuntimeError):
    """A status probe timed out/reset; this is NOT proof of a stopped endpoint."""


class DaemonConnectTimeout(DaemonTransportPending):
    """Windows may time out connecting to a closed loopback port instead of refusing."""


def host_join(root, *parts):
    return str(PureWindowsPath(root).joinpath(*parts))


class Runner:
    def __init__(self, args):
        self.args = args
        self.plan = runtime_plan(args.suite)
        self.python_paths = getattr(args, "python_path", [])
        require(not self.python_paths or args.cli_command,
                "Explicit import directories require an adapter-owned CLI executable")
        for path in self.python_paths:
            require(path.is_absolute() and path.is_dir(),
                    "Python import directory must exist and be absolute")
        self.cli = [args.cli_command] if args.cli_command else [sys.executable, "-I", "-m", "swcli"]
        self.directory = args.output_dir.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.record_path = self.directory / "runtime-sets.json"
        with self.record_path.open("x") as stream:
            stream.write("{}\n")
        self.server = None
        self.server_log = None
        self.record = {"completed": False, "success": False, "suite": args.suite, "mode": args.mode,
                       "session_policy": "fresh-per-test-set", "expected_sets": [item.name for item in self.plan],
                       "budgets_seconds": {"request": args.request_timeout, "startup": args.startup_timeout,
                                           "test_set": args.set_timeout, "host_exit": 30},
                       "sets": [], "commands": [], "cleanup_errors": [], "active_set": None}
        self.record["python_import_paths"] = [str(path.resolve()) for path in self.python_paths]
        endpoint_host, endpoint_port = args.endpoint.rsplit(":", 1)
        self.bind_host, self.bind_port = endpoint_host.strip("[]"), int(endpoint_port)
        require(ipaddress.ip_address(self.bind_host).is_loopback and 0 < self.bind_port <= 65535,
                "Functional runner may only own a dedicated loopback endpoint")
        self.checkpoint()

    def checkpoint(self):
        scratch = self.record_path.with_suffix(".tmp")
        scratch.write_text(json.dumps(self.record, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
        scratch.replace(self.record_path)

    def command(self, args, *, timeout, label, json_result=False):
        # Regular files, not pipes: Wine descendants may retain inherited FDs.
        stdout_path = self.directory / (label + "-stdout.log")
        stderr_path = self.directory / (label + "-stderr.log")
        event = {"label": label, "started_utc": datetime.now(timezone.utc).isoformat(), "timeout": timeout}
        self.record["commands"].append(event)
        self.checkpoint()
        process = None
        started = time.monotonic()
        with stdout_path.open("xb") as output, stderr_path.open("xb") as errors:
            try:
                process = subprocess.Popen(list(map(str, args)), stdin=subprocess.DEVNULL, stdout=output, stderr=errors)
                event["process_id"] = process.pid
                observed = 0
                while process.poll() is None:
                    if time.monotonic() - started >= timeout:
                        raise subprocess.TimeoutExpired(args, timeout)
                    if not json_result:
                        with stdout_path.open("rb") as reader:
                            reader.seek(observed)
                            lines = reader.read(65536).splitlines(keepends=True)
                        for line in lines:
                            if not line.endswith(b"\n"):
                                break
                            observed += len(line)
                            text = line.decode("utf-8", errors="replace").strip()
                            if re.fullmatch(r"(?:Modeling gate|Driving-dimension gate|Toolbox gate): [a-z0-9_. -]{1,96}", text):
                                print(text, flush=True)
                    time.sleep(0.2)
                event["exit_code"] = process.returncode
                if json_result and process.returncode != 0:
                    rejected = json.loads(stdout_path.read_text(encoding="utf-8-sig"))
                    if list(args[-3:]) == ["daemon", "status", "--json"] and rejected.get("success") is False:
                        code = rejected.get("error", {}).get("code")
                        if code == "ConnectionRefusedError":
                            raise DaemonUnavailable("Dedicated daemon endpoint is not listening")
                        if code == "Starting":
                            raise DaemonStarting("Dedicated daemon is initializing its worker")
                        if code == "TimeoutError" and rejected["error"].get("transport_phase") == "connect":
                            raise DaemonConnectTimeout("Lifecycle status could not connect to the endpoint")
                        if code in ("TimeoutError", "ConnectionResetError"):
                            raise DaemonTransportPending("Lifecycle status probe returned " + code)
                require(process.returncode == 0, "Functional command failed: " + label)
            except BaseException as error:
                event["error_type"] = type(error).__name__
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(10)
                raise
            finally:
                event["seconds"] = time.monotonic() - started
                try:
                    self.checkpoint()
                except OSError:
                    if "error_type" not in event:
                        raise
        if json_result:
            result = json.loads(stdout_path.read_text(encoding="utf-8-sig"))
            require(result.get("success") is True or result.get("ok") is True, "CLI command rejected: " + label)
            return result.get("result", result)

    def public(self, *args, label, timeout=60):
        return self.command([*self.cli, "--endpoint", self.args.endpoint, *args, "--json"],
                            timeout=timeout, label=label, json_result=True)

    def health(self, label, *, timeout=60):
        return self.public("daemon", "status", label=label, timeout=timeout)

    def exclusive(self, health):
        host = health.get("host", {})
        require(health.get("host_connected") is True and health.get("recovery_required") is False
                and host.get("owned_by_daemon") is True and host.get("shared_interactive") is False
                and type(host.get("process_id")) is int and host["process_id"] > 0,
                "Exclusive connected daemon-owned SW required")
        require(host.get("visible") is (self.args.mode == "visible"), "Unexpected SW visibility")
        return host

    def empty(self, label):
        result = self.public("document", "list", label=label)
        require(result.get("documents") == [] and result.get("count") == 0,
                "Unknown open documents block test-set transitions")

    def wait_host_exit(self, item, stage):
        # This runner owns an isolated VM/container. A remaining SW process,
        # including an unknown one, blocks a new session; never kill it here.
        started = time.monotonic()
        deadline = started + 30
        while True:
            remaining = deadline - time.monotonic()
            require(remaining > 0, "SLDWORKS process remained at test-set boundary: " + stage)
            ids = solidworks_process_ids(timeout=min(10, remaining))
            item[stage] = {"native_process_ids": ids, "verified": not ids,
                           "pid_namespace": "windows" if sys.platform == "win32" else "unix",
                           "seconds": time.monotonic() - started}
            self.checkpoint()
            if not ids:
                return
            time.sleep(0.2)

    def start(self, item):
        # The previous owned server must have exited, not merely acknowledged.
        require(self.server is None, "Previous session was not fully stopped")
        self.wait_host_exit(item, "before_start")
        item["instance_id"] = uuid.uuid4().hex
        command = [*self.cli, "daemon", "serve", "--host", self.bind_host, "--port", str(self.bind_port),
                   "--startup-timeout", str(self.args.startup_timeout)]
        if self.args.mode == "visible":
            command.append("--visible")
        log = self.args.daemon_log or self.directory / "daemon.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        self.server_log = log.open("ab")
        self.server = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                       stdout=self.server_log, stderr=self.server_log)
        deadline = time.monotonic() + self.args.startup_timeout + 30
        poll = 0
        while time.monotonic() < deadline:
            require(self.server.poll() is None, "Owned daemon exited during startup")
            poll += 1
            try:
                health = self.health(item["name"] + "-startup-" + str(poll),
                                     timeout=min(60, max(0.01, deadline - time.monotonic())))
            except (DaemonUnavailable, DaemonStarting, DaemonTransportPending):
                time.sleep(1)
                continue  # Startup observation only; never replay CAD calls.
            require(self.server.poll() is None, "Owned daemon exited during startup")
            item["host"] = self.exclusive(health)
            # A Windows/Wine PID may be recycled after exit. Session freshness
            # follows from verified process absence and a new owned launcher,
            # not global PID uniqueness. Within-set host checks stay unchanged.
            item["server_process_id"] = self.server.pid
            self.empty(item["name"] + "-before")
            self.checkpoint()
            return
        raise RuntimeError("Owned SW startup exceeded its deadline")

    def stop(self, item):
        if self.server is None:
            return
        error = None
        try:
            if self.server.poll() is None and "host" in item:
                self.public("daemon", "stop", label=item["name"] + "-stop")
            elif self.server.poll() is None:
                # Startup never established endpoint ownership. Terminate only
                # our foreground launcher; do not shut down an unknown server.
                self.server.terminate()
            self.server.wait(30)
            require(self.server.returncode == 0, "Owned daemon exited abnormally")
            self.wait_host_exit(item, "after_stop")
        except BaseException as failure:
            error = failure
            if self.server.poll() is None:
                self.server.terminate()
                try:
                    self.server.wait(10)
                except subprocess.TimeoutExpired:
                    self.server.kill()
                    self.server.wait(10)
        finally:
            item["server_exit_code"] = self.server.returncode
            self.server = None
            self.server_log.close()
            self.server_log = None
        if error is not None:
            raise error

    def step_args(self, test_set, step, fixture, host_fixture):
        output = self.directory / test_set.name / step.kind
        output.mkdir(parents=True, exist_ok=True)
        arguments = [sys.executable, "-I"]
        if self.python_paths:
            arguments.append(SCRIPTS / "gate_support/python_entrypoint.py")
            for path in self.python_paths:
                arguments += ["--python-path", path.resolve()]
        arguments += [SCRIPTS / step.script, "--output-dir", output,
                     "--endpoint", self.args.endpoint, "--request-timeout", str(self.args.request_timeout)]
        if self.args.cli_command:
            arguments += ["--cli-command", self.args.cli_command]
        if step.kind != "toolbox":
            arguments += ["--suite", self.args.suite,
                          "--host-output-dir", host_join(self.args.host_output_dir, test_set.name, step.kind)]
        if step.kind == "modeling":
            arguments += ["--sample-part", self.args.sample_part, "--sample-assembly", self.args.sample_assembly]
            if test_set.name.startswith("drawing-"):
                arguments += ["--sample-drawing", self.args.sample_drawing,
                              "--sample-drawing-local", self.args.sample_drawing_local,
                              "--drawing-work-dir", fixture, "--host-drawing-work-dir", host_fixture]
        if step.kind == "toolbox":
            arguments += ["--require-toolbox"]
            if self.args.wine_prefix:
                arguments += ["--wine-prefix", self.args.wine_prefix]
        arguments += list(step.args)
        if "--after-modeling" in step.args:
            arguments.append(output.parent / "modeling/modeling.json")
        return arguments, output

    def run(self):
        # Prepared wrappers may already own a host. Adopt only for its bounded
        # shutdown; no CAD set is run in that pre-warmed session.
        existing = None
        try:
            existing = self.health("preflight-status")
        except DaemonUnavailable:
            pass  # No daemon is expected for adapters that only prepared Wine.
        if existing is not None:
            self.exclusive(existing)
            self.empty("preflight-documents")
            stopped = self.public("daemon", "stop", label="preflight-stop")
            require(stopped.get("stopping") is True, "Exclusive daemon shutdown was not acknowledged")
            deadline = time.monotonic() + 30
            poll = 0
            while time.monotonic() < deadline:
                poll += 1
                try:
                    self.health("preflight-shutdown-" + str(poll),
                                timeout=min(60, max(0.01, deadline - time.monotonic())))
                except DaemonUnavailable:
                    break
                except DaemonConnectTimeout:
                    break  # Known stop acknowledged; the socket never connected.
                except DaemonTransportPending:
                    pass  # Stop was acknowledged for an exclusive empty host.
                    # Reset/timeout is transitional, NOT stopped. Require a
                    # failed connection (not an RPC response timeout) before
                    # starting any new host.
                time.sleep(0.2)
            else:
                raise RuntimeError("Previous owned endpoint did not stop")
        self.args.fixture_work_dir.mkdir(parents=True, exist_ok=True)
        for test_set in self.plan:
            started = time.monotonic()
            item = {"name": test_set.name, "success": False, "steps": [], "cleanup_errors": [],
                    "started_utc": datetime.now(timezone.utc).isoformat()}
            self.record["sets"].append(item)
            self.record["active_set"] = test_set.name
            self.checkpoint()
            print("Runtime sets: " + test_set.name + " starting", flush=True)
            failure = None
            try:
                with tempfile.TemporaryDirectory(prefix="drawing-", dir=self.args.fixture_work_dir) as temporary:
                    fixture = Path(temporary)
                    host_fixture = host_join(self.args.host_fixture_work_dir, fixture.name)
                    if test_set.name.startswith("drawing-"):
                        shutil.copytree(self.args.sample_drawing_local.parent, fixture, dirs_exist_ok=True)
                    self.start(item)
                    set_deadline = time.monotonic() + self.args.set_timeout
                    for step in test_set.steps:
                        arguments, output = self.step_args(test_set, step, fixture, host_fixture)
                        remaining = set_deadline - time.monotonic()
                        require(remaining > 0, "Functional test-set budget exhausted")
                        self.command(arguments, timeout=remaining,
                                     label=test_set.name + "-" + step.kind)
                        filename = {"modeling": "modeling.json", "driving": "driving-dimensions.json",
                                    "toolbox": "toolbox.json"}[step.kind]
                        proof = json.loads((output / filename).read_text())
                        if step.kind == "toolbox":
                            require(proof.get("completed") is True and proof.get("native_test") == "passed"
                                    and proof.get("cleanup_errors") == [], "Toolbox set did not pass")
                        else:
                            require(proof.get("success") is True and proof.get("state") == "completed"
                                    and proof.get("cleanup_errors") == [], "Functional set did not pass")
                            require(proof.get("suite") == self.args.suite and proof.get("host") == item["host"]
                                    and proof.get("host_after") == item["host"], "Incorrect functional coverage/host proof")
                            if step.kind == "modeling":
                                require(proof.get("cases"), "Empty modeling proof")
                            else:
                                plane = step.args[step.args.index("--plane") + 1]
                                require(proof.get("selection", {}).get("plane") == plane
                                        and proof.get("case_cleanup", [])[-1:]
                                        and proof["case_cleanup"][-1].get("empty") is True,
                                        "Incomplete driving selection/cleanup proof")
                        after = self.exclusive(self.health(test_set.name + "-" + step.kind + "-after"))
                        require(after == item["host"], "SW was replaced INSIDE a functional set")
                        self.empty(test_set.name + "-" + step.kind + "-documents")
                        item["steps"].append({"script": step.script, "record": str(output / filename), "success": True})
                        self.checkpoint()
                    item["success"] = True
            except BaseException as error:
                failure = error
                item["error"] = {"type": type(error).__name__, "message": str(error)}
            finally:
                try:
                    self.stop(item)
                except BaseException as cleanup_error:
                    item["success"] = False
                    item["cleanup_errors"].append(type(cleanup_error).__name__)
                    if failure is None:
                        failure = cleanup_error
                self.record["active_set"] = None
                item["finished_utc"] = datetime.now(timezone.utc).isoformat()
                item["seconds"] = time.monotonic() - started
                try:
                    self.checkpoint()
                except OSError:
                    if failure is None:
                        raise
            if failure is not None:
                raise failure
            print("Runtime sets: " + test_set.name + " passed", flush=True)
        require([item["name"] for item in self.record["sets"]] == self.record["expected_sets"]
                and all(item["success"] for item in self.record["sets"]), "Incomplete functional coverage")
        self.record.update(completed=True, success=True)
        self.checkpoint()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("core", "full"), default="full")
    parser.add_argument("--mode", choices=("visible", "hidden"), default="visible")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--host-output-dir", type=host_directory, required=True)
    parser.add_argument("--cli-command")
    parser.add_argument("--python-path", action="append", type=Path, default=[],
                        help="Explicit trusted source/dependency directory for source-only adapters; repeatable")
    parser.add_argument("--endpoint", default=os.environ.get("SWCLI_ENDPOINT", "127.0.0.1:18495"))
    parser.add_argument("--sample-part", type=host_directory, required=True)
    parser.add_argument("--sample-assembly", type=host_directory, required=True)
    parser.add_argument("--sample-drawing", type=host_directory, required=True)
    parser.add_argument("--sample-drawing-local", type=Path, required=True)
    parser.add_argument("--fixture-work-dir", type=Path, required=True)
    parser.add_argument("--host-fixture-work-dir", type=host_directory, required=True)
    parser.add_argument("--wine-prefix", type=Path)
    parser.add_argument("--daemon-log", type=Path)
    parser.add_argument("--request-timeout", type=float, default=120)
    parser.add_argument("--startup-timeout", type=float, default=300)
    parser.add_argument("--set-timeout", type=float, default=1800)
    args = parser.parse_args(argv)
    import math
    for value in (args.request_timeout, args.startup_timeout, args.set_timeout):
        require(math.isfinite(value) and 0 < value <= 7200, "Invalid finite runtime budget")
    require(args.request_timeout <= 3600, "Request timeout exceeds product maximum")
    if args.cli_command:
        require(Path(args.cli_command).is_absolute() and Path(args.cli_command).is_file()
                and os.access(args.cli_command, os.X_OK), "One absolute executable CLI path required")
    require(args.sample_drawing_local.is_file(), "Installed official drawing fixture is missing")
    runner = Runner(args)
    try:
        runner.run()
    except BaseException as error:
        runner.record["error"] = {"type": type(error).__name__, "message": str(error)}
        try:
            runner.checkpoint()
        except OSError:
            pass  # Never replace the original native/test failure.
        raise


if __name__ == "__main__":
    main()
