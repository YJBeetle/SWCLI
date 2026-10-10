"""Shared Toolbox deployment/read-only CLI gate; never installs or repairs it.

No COM imports or updater invocation. Host wrappers select policy and provide
the Wine prefix or an explicit local/Windows path pair. Inventory success is
not proof of add-in loading, specification selection or assembly insertion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

MAX_FILES = 50000
MAX_XML_BYTES = 2 * 1024 * 1024


def require(value, message):
    if not value:
        raise RuntimeError(message)


def windows_path(value):
    path = PureWindowsPath(value)
    require(path.is_absolute() and "\0" not in value and ".." not in path.parts,
            "Toolbox data location must be an absolute Windows path")
    return str(path)


def wine_locations(text):
    general, paths = False, set()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            general = bool(re.fullmatch(
                r"\[Software\\\\(?:Wow6432Node\\\\)?SolidWorks\\\\SOLIDWORKS [^\]]+\\\\General\](?: .*)?",
                line, re.IGNORECASE))
        elif general:
            match = re.fullmatch(r'"Toolbox Data Location"="([^"\r\n]*)"', line,
                                 re.IGNORECASE)
            if match:
                paths.add(windows_path(match[1].replace("\\\\", "\\")))
    return paths


def configured_location(prefix=None):
    # Current-user settings take precedence, matching the running host's
    # configuration. Multiple distinct version locations fail, never guess.
    if prefix is not None:
        for name in ("user.reg", "system.reg"):
            hive = prefix / name
            if hive.is_file():
                paths = wine_locations(hive.read_text(encoding="utf-8"))
                if paths:
                    require(len(paths) == 1, "Ambiguous Toolbox data locations")
                    return paths.pop()
        return None
    require(sys.platform == "win32", "Provide --wine-prefix or explicit data paths")
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        paths = set()
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                parent = winreg.OpenKey(hive, r"Software\SolidWorks", 0,
                                        winreg.KEY_READ | view)
            except FileNotFoundError:
                continue
            with parent:
                for index in range(winreg.QueryInfoKey(parent)[0]):
                    version = winreg.EnumKey(parent, index)
                    if not version.lower().startswith("solidworks "):
                        continue
                    try:
                        with winreg.OpenKey(parent, version + r"\General") as key:
                            value, kind = winreg.QueryValueEx(key, "Toolbox Data Location")
                    except FileNotFoundError:
                        continue
                    require(kind == winreg.REG_SZ, "Unexpected Toolbox registry value type")
                    paths.add(windows_path(value))
        if paths:
            require(len(paths) == 1, "Ambiguous Toolbox data locations")
            return paths.pop()
    return None


def local_location(host_path, prefix=None):
    if prefix is None:
        return Path(host_path)
    path = PureWindowsPath(host_path)
    require(re.fullmatch(r"[A-Za-z]:", path.drive),
            "UNC Toolbox locations require explicit --data-dir/--host-data-dir")
    mapping = prefix / "dosdevices" / path.drive.lower()
    require(mapping.is_dir(), "Toolbox drive has no actual Wine mapping")
    return mapping.resolve().joinpath(*path.parts[1:])


def nonempty(path, label):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size > 0,
            label + " is missing, empty or a symlink: " + str(path))


def inventory(root):
    root = root.resolve()
    config = root / "ToolboxStandards.xml"
    nonempty(config, "Toolbox standards configuration")
    require(config.stat().st_size <= MAX_XML_BYTES, "Toolbox XML exceeds size limit")
    xml = config.read_bytes()
    declarations = xml.replace(b"\0", b"").upper()
    require(len(xml) <= MAX_XML_BYTES and b"<!DOCTYPE" not in declarations and b"<!ENTITY" not in declarations,
            "Toolbox XML must not contain DTD/entity declarations")
    tree = ET.fromstring(xml)
    require(tree.tag == "ToolboxStandards", "Unexpected Toolbox XML root")
    standards, names = [], set()
    for node in tree.findall("Standard"):
        name = (node.findtext("Name") or "").strip()
        source = (node.findtext("Source") or "").strip()
        enabled = (node.findtext("Install") or "").strip().lower()
        require(enabled in ("yes", "no"), "Invalid Toolbox standard Install value")
        if enabled == "no":
            continue
        require(all(value and value not in (".", "..")
                    and not any(c in value for c in '/\\:\0')
                    for value in (name, source)) and source.lower().endswith(".zip"),
                "Unsafe/invalid Toolbox standard name or source")
        require(name.casefold() not in names, "Duplicate Toolbox standard")
        names.add(name.casefold())
        standards.append({"name": name, "source": source})
    require(standards, "No enabled Toolbox standards to verify")
    browser = root / "browser"
    for folder in (browser, root / "lang", root / "lang/english"):
        require(folder.is_dir() and not folder.is_symlink(),
                "Toolbox directory is missing or a symlink: " + str(folder))
    nonempty(browser / "ToolboxFiles.index", "Official Toolbox index")
    nonempty(root / "lang/english/swbrowser.sldedb", "Toolbox database")
    scanned, total = 0, 0
    for standard in sorted(standards, key=lambda item: item["name"].casefold()):
        folder = browser / standard["name"]
        require(folder.is_dir() and not folder.is_symlink(),
                "Toolbox standard directory missing: " + standard["name"])
        models = []
        for directory, folders, files in os.walk(folder, followlinks=False):
            scanned += len(folders)
            require(scanned <= MAX_FILES, "Toolbox file count exceeds bound")
            require(not any((Path(directory) / name).is_symlink() for name in folders),
                    "Toolbox model tree contains a directory symlink")
            for name in files:
                scanned += 1
                require(scanned <= MAX_FILES, "Toolbox file count exceeds bound")
                path = Path(directory) / name
                if path.suffix.lower() == ".sldprt":
                    nonempty(path, "Toolbox part model")
                    models.append(path.relative_to(root).as_posix())
        require(models, "No Toolbox part models for enabled standard: " + standard["name"])
        standard.update(model_count=len(models), representative=sorted(models)[0])
        total += len(models)
    standards.sort(key=lambda item: item["name"].casefold())
    return {"data_dir": str(root), "enabled_standards": standards,
            "model_count": total, "index_bytes": (browser / "ToolboxFiles.index").stat().st_size,
            "standards_sha256": hashlib.sha256(xml).hexdigest()}


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class Gate:
    def __init__(self, args):
        self.args = args
        args.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = args.output_dir / "toolbox.json"
        # Reserve before any check/action: never overwrite a previous run.
        with self.path.open("x", encoding="utf-8") as stream:
            stream.write("{}\n")
        self.record = {"completed": False, "outcome": "running", "stage": "initializing",
                       "events": [], "cleanup_errors": [], "evidence_errors": [],
                       "native_test": "not-run", "updater_exit_code": None,
                       "limitations": ["No add-in/specification/assembly insertion verification",
                                       "Index presence is not index-content validation"]}
        self.cli = ([args.cli_command] if args.cli_command else [sys.executable, "-I", "-m", "swcli"])
        self.session = "toolbox-" + uuid.uuid4().hex
        self.document = None
        self.preexisting_ids = set()
        self.checkpoint()

    def checkpoint(self):
        scratch = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             delete=False) as stream:
                scratch = Path(stream.name)
                json.dump(self.record, stream, indent=2, ensure_ascii=False, allow_nan=False)
                stream.write("\n")
            scratch.replace(self.path)
        finally:
            if scratch is not None and scratch.exists():
                scratch.unlink()

    def checkpoint_after(self, *, preserve_error=False):
        try:
            self.checkpoint()
        except Exception as exc:
            self.record["evidence_errors"].append({"stage": self.record["stage"],
                "type": type(exc).__name__, "message": str(exc)})
            print("Toolbox evidence checkpoint failed: " + str(exc), file=sys.stderr, flush=True)
            if not preserve_error:
                raise

    def command(self, *arguments, document=None, cleanup=False):
        from swcli.result_schemas import validate_operation_result
        command = [*self.cli, "--endpoint", self.args.endpoint, "--session", self.session,
                   "--request-timeout", str(self.args.request_timeout), *arguments]
        if document is not None:
            command += ["--document", document]
        command += ["--json"]
        event = {"command": command, "state": "running"}
        self.record["events"].append(event)
        self.record["stage"] = ".".join(arguments[:2])
        self.checkpoint_after(preserve_error=cleanup)
        print("Toolbox gate: " + self.record["stage"], flush=True)
        try:
            result = subprocess.run(command, capture_output=True,
                                    timeout=self.args.request_timeout + 15,
                                    env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            event.update(returncode=result.returncode,
                         stdout=result.stdout.decode("utf-8-sig"),
                         stderr=result.stderr.decode("utf-8", errors="replace"))
            payload = json.loads(event["stdout"])
            event["result"] = payload
            # Register a successful open before later assertion/Schema errors
            # so the gate can close ONLY its own newly opened document.
            if arguments[:2] == ("document", "open") and payload.get("ok") is True:
                opened_id = payload.get("document", {}).get("document_id")
                require(opened_id not in self.preexisting_ids,
                        "Toolbox open reused a pre-existing document; refusing to adopt/close it")
                self.document = opened_id
            if arguments[:2] == ("daemon", "status"):
                require(result.returncode == 0 and payload.get("success") is True,
                        "Toolbox daemon status failed")
                business = payload["result"]
            else:
                require(result.returncode == 0 and payload.get("ok") is True,
                        "Toolbox CLI operation failed: " + str(payload.get("error")))
                business = {key: value for key, value in payload.items()
                            if key not in ("request_id", "replayed")}
                validate_operation_result(".".join(arguments[:2]), business)
            event["state"] = "completed"
            return business
        except Exception as exc:
            event.update(state="failed", error={"type": type(exc).__name__, "message": str(exc)})
            raise
        finally:
            self.checkpoint_after(preserve_error=cleanup or event["state"] == "failed")

    def run(self):
        try:
            host_path = self.args.host_data_dir or configured_location(self.args.wine_prefix)
            if host_path is None:
                require(not self.args.require_toolbox, "Required Toolbox data location is unconfigured")
                self.record.update(outcome="skipped", reason="Toolbox was not requested and is unconfigured")
            else:
                self.record["stage"] = "inventory"
                root = self.args.data_dir or local_location(host_path, self.args.wine_prefix)
                self.record["inventory"] = inventory(root)
                self.record["host_data_dir"] = host_path
                self.checkpoint()
                if not self.args.inventory_only:
                    self.verify_model(root, host_path)
                require(not self.record["evidence_errors"], "Toolbox evidence could not be fully recorded")
                self.record.update(completed=True, outcome="passed")
        except Exception as exc:
            self.record.update(outcome="failed", error={"type": type(exc).__name__, "message": str(exc)})
        finally:
            self.checkpoint_after(preserve_error=True)
            if self.record["evidence_errors"]:
                self.record.update(completed=False, outcome="failed")
                self.record.setdefault("error", {"type": "EvidenceWriteFailed",
                                                "message": "Toolbox evidence could not be fully recorded"})
        return 0 if self.record["outcome"] in ("passed", "skipped") else 1

    def verify_model(self, root, host_path):
        sample = self.record["inventory"]["enabled_standards"][0]["representative"]
        local = root / sample
        path = str(PureWindowsPath(host_path).joinpath(*Path(sample).parts))
        original = checksum(local)
        self.record["sample"] = {"relative_path": sample, "sha256_before": original}
        host = self.command("daemon", "status")
        require(host.get("host_connected") is True and not host.get("recovery_required"),
                "Toolbox requires an already connected host; no automatic restart")
        before = self.command("document", "list")
        self.preexisting_ids = {doc["document_id"] for doc in before["documents"]}
        require(all(PureWindowsPath(doc["path"]) != PureWindowsPath(path)
                    for doc in before["documents"]), "Toolbox sample is already open; refusing to adopt/close it")
        try:
            opened = self.command("document", "open", path, "--read-only")
            require(opened["read_only"] is True and opened["api_errors"] == 0,
                    "Toolbox sample did not open read-only")
            baseline = opened["document"]
            require(type(baseline["update_stamp"]) is int,
                    "Toolbox read-only state cannot be verified without an update stamp")
            diagnosed = self.command("document", "diagnose", document=self.document)
            diagnostics = diagnosed["diagnostics"]
            require(diagnosed["needs_rebuild"] == 0 and diagnostics["healthy"] is True
                    and diagnostics["truncated"] is False
                    and not any(issue["severity"] == "error" for issue in diagnostics["issues"]),
                    "Toolbox sample has rebuild errors or requires rebuilding")
            measured = self.command("document", "measure", document=self.document)
            metrics = measured["metrics"]
            require(metrics["solid_body_count"] > 0 and type(metrics["volume_mm3"]) in (int, float)
                    and math.isfinite(metrics["volume_mm3"]) and metrics["volume_mm3"] > 0,
                    "Toolbox sample has no measurable solid geometry")
            require(all(result["document"][key] == baseline[key]
                        for result in (diagnosed, measured) for key in ("document_id", "modified", "update_stamp")),
                    "Toolbox read-only observation changed document state")
        finally:
            if self.document is not None:
                try:
                    closed = self.command("document", "close", "--discard", document=self.document, cleanup=True)
                    require(closed["closed"] is True, "Toolbox document did not close")
                    self.document = None
                except Exception as exc:
                    self.record["cleanup_errors"].append(str(exc))
            try:
                self.record["sample"]["sha256_after"] = checksum(local)
            except Exception as exc:
                self.record["cleanup_errors"].append("Source readback: " + str(exc))
        require(not self.record["cleanup_errors"], "Toolbox document cleanup failed")
        require(self.record["sample"]["sha256_after"] == original, "Toolbox source model changed on disk")
        after = self.command("document", "list")
        require({doc["document_id"]: doc for doc in after["documents"]}
                == {doc["document_id"]: doc for doc in before["documents"]},
                "Toolbox gate changed pre-existing documents")
        end = self.command("daemon", "status")
        require(end.get("host_connected") is True and end.get("host") == host.get("host"),
                "Toolbox gate disconnected or replaced the original host")
        self.record["native_test"] = "passed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--wine-prefix", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--host-data-dir", type=windows_path)
    parser.add_argument("--require-toolbox", action="store_true")
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--cli-command")
    parser.add_argument("--endpoint", default=os.environ.get("SWCLI_ENDPOINT", "127.0.0.1:18495"))
    parser.add_argument("--request-timeout", type=float, default=120)
    args = parser.parse_args()
    if bool(args.data_dir) != bool(args.host_data_dir):
        parser.error("--data-dir and --host-data-dir must be supplied together")
    if not math.isfinite(args.request_timeout) or not 0 < args.request_timeout <= 3600:
        parser.error("--request-timeout must be finite, > 0 and <= 3600")
    if args.cli_command and not (Path(args.cli_command).is_absolute()
                                and Path(args.cli_command).is_file()
                                and os.access(args.cli_command, os.X_OK)):
        parser.error("--cli-command must be one absolute executable path")
    return Gate(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
