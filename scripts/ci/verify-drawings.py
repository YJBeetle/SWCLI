"""Public CLI drawing creation gate; host/template supplied by the caller.

No COM, host restart or operation retries. Reopened public structure/diagnostics
and strict exports are checked; persistent view transforms/references are NOT
exposed by public inspect and remain independently tested by native calibration.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath

spec = importlib.util.spec_from_file_location(
    "drawing_modeling_base", Path(__file__).with_name("verify-modeling.py"))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
require = base.require


class DrawingSmoke(base.ModelingSmoke):
    def observe_catalog(self, stage, source):
        documents = self.command("document", "list")["documents"]
        self.record.setdefault("source_lifecycle", []).append({
            "stage": stage, "source_document_id": source,
            "documents": documents,
        })
        self.checkpoint(stage)
        return documents

    def retire_unloaded(self, candidates, documents):
        # Closing a drawing may unload its background model dependencies too.
        # Only retire our known handles absent from the actual native catalog.
        opened = {item["document_id"] for item in documents}
        for document in candidates:
            if document not in opened:
                self.owned.pop(document, None)
                self.leases.pop(document, None)
        return opened

    @staticmethod
    def structure_signature(structure):
        features = structure["features"]
        require(features["count"] > 0 and not features["truncated"],
                "drawing/source feature structure empty or truncated")
        return {"configurations": structure["configurations"],
                "features": [(item["name"], item["type"]) for item in features["items"]]}

    def target(self, name):
        return str(PureWindowsPath(self.host_directory) / name)

    def clean_source(self, document):
        result = self.command("document", "inspect", "--detail", "structure", document=document)
        require(result["document"]["modified"] is False and result["needs_rebuild"] == 0,
                "drawing source is modified or needs rebuilding")
        return result

    def save_native(self, document, name):
        result = self.write("document", "save-as", self.target(name), document=document)
        path = self.directory / name
        require(result["api_saved"] is True and result["save_errors"] == 0
                and result["document"]["modified"] is False
                and path.is_file() and path.stat().st_size >= 512
                and result["artifact"]["size_bytes"] == path.stat().st_size,
                "drawing fixture native save failed")
        return path

    def drawing_case(self, kind, projection, template):
        stem = kind + "-" + projection
        part = self.create()
        sketch = self.rectangle(part)
        self.feature(part, sketch["sketch"]["sketch_id"], depth=10)
        part_file = self.save_native(part, stem + ".SLDPRT")
        source = part
        files = [part_file]
        if kind == "assembly":
            config = self.clean_source(part)["structure"]["configurations"]["active"]
            source = self.command("document", "create", "--type", "assembly")["document"]["document_id"]
            self.write("assembly", "add-component", self.target(part_file.name),
                       "--configuration", config, document=source)
            files.append(self.save_native(source, stem + ".SLDASM"))
        before = self.clean_source(source)
        config = before["structure"]["configurations"]["active"]
        hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
        created = self.command("document", "create", "--type", "drawing",
                               "--template", template, "--projection", projection)
        drawing = created["document"]["document_id"]
        require(created["document"]["type"] == 3 and created["views"] == []
                and created["sheet"]["projection"] == projection,
                "drawing did not start empty with requested projection")
        blocker = self.create()  # Both session current and foreground must survive.
        lease = self.command("document", "lease", "acquire", "--ttl-seconds", 600,
                             document=drawing)["lease"]["lease_id"]
        arguments = ("drawing", "standard-views", source, "--configuration", config)
        self.command(*arguments, document=drawing, expected_error="DocumentLeaseConflict")
        stamp = self.command("document", "inspect", document=drawing)["document"]["update_stamp"]
        require(type(stamp) is int, "drawing update stamp unavailable")
        self.command(*arguments, "--if-update-stamp", stamp + 1, document=drawing,
                     lease=lease, expected_error="DocumentUpdateConflict")
        foreign = self.session + "-foreign"
        source_lease = self.command("document", "lease", "acquire", "--ttl-seconds", 600,
                                    document=source, session=foreign)["lease"]["lease_id"]
        self.command(*arguments, document=drawing, lease=lease,
                     expected_error="DocumentLeaseConflict")
        self.command("document", "lease", "release", source_lease,
                     session=foreign)
        inserted = self.write(*arguments, "--if-update-stamp", stamp, document=drawing)
        self.background(inserted, drawing)
        require(inserted["verification"]["passed"] is True
                and inserted["verification"]["source_unchanged"] is True
                and inserted["sheet"]["projection"] == projection
                and len(inserted["views"]) == 3,
                "standard views did not verify exact source/projection/layout")
        current = self.command("document", "inspect")["document"]
        require(current["document_id"] == blocker and current["active"] is True,
                "background drawing write changed current/foreground")
        rejected = self.write(*arguments, document=drawing, expected_error="RuntimeError")
        require(rejected["mutation"]["attempted"] is False
                and "already contains model views" in rejected["error"]["message"],
                "nonempty drawing was not rejected before native insertion")
        native = self.save_native(drawing, stem + ".SLDDRW")
        structure = self.command("document", "inspect", "--detail", "structure",
                                 document=drawing)["structure"]
        require(self.clean_source(source)["structure"] == before["structure"],
                "drawing changed source public structure before close")
        self.observe_catalog(stem + ".before-drawing-close", source)
        self.close(drawing)
        closed_catalog = self.observe_catalog(stem + ".after-drawing-close", source)
        self.retire_unloaded((source, part), closed_catalog)
        reopened = self.command("document", "open", self.target(native.name))["document"]["document_id"]
        self.observe_catalog(stem + ".after-drawing-reopen", source)
        observed = self.command("document", "inspect", "--detail", "structure", document=reopened)
        require(reopened != drawing and observed["document"]["modified"] is False
                and self.structure_signature(observed["structure"]) == self.structure_signature(structure),
                "drawing reopen changed public document structure/state")
        diagnosis = self.command("document", "diagnose", document=reopened)
        require(diagnosis["diagnostics"]["healthy"] is True and diagnosis["needs_rebuild"] == 0,
                "drawing reopen has rebuild/feature errors")
        for extension in ("PDF", "DWG"):
            self.write("document", "export", self.target(stem + "." + extension),
                       "--strict", document=reopened)
            require(base.export_file_valid(extension, self.directory / (stem + "." + extension)),
                    "drawing export failed bounded file validation")
        # Resolve the saved source explicitly after the deliberate drawing
        # close/reopen. Never assume a handle survives native dependency unload.
        for index, path in enumerate(files):
            opened = self.command("document", "open", self.target(path.name))["document"]["document_id"]
            if index == 0:
                part = opened
            if index == len(files) - 1:
                source = opened
        require(self.clean_source(source)["structure"] == before["structure"],
                "drawing changed source public structure")
        require(all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
                    for path, digest in hashes.items()), "drawing modified source bytes")
        self.close(reopened)
        documents = self.observe_catalog(stem + ".after-final-drawing-close", source)
        opened_ids = self.retire_unloaded((source, part), documents)
        self.close(blocker)
        if source != part and source in opened_ids:
            self.close(source)
        # Closing an assembly can unload its referenced component implicitly.
        opened = self.command("document", "list")["documents"]
        if any(doc["document_id"] == part for doc in opened):
            self.close(part)
        else:
            self.owned.pop(part, None)
            self.leases.pop(part, None)
        self.record["cases"].append(stem)
        self.checkpoint(stem + ".verified")

    def run_drawings(self, template):
        self.record["host"] = self.health()["host"]
        self.command("capabilities", "--full")
        self.require_empty()
        self.record["persistence_scope"] = (
            "Public structure, diagnostics and strict exports after reopen; persisted view "
            "references/transforms are not exposed by public inspect and are not claimed here.")
        for kind, projection in (("part", "first-angle"), ("assembly", "third-angle")):
            self.drawing_case(kind, projection, template)
            self.require_empty(after_case=kind + "-" + projection)
        self.record["host_after"] = self.health()["host"]
        require(self.record["host_after"]["process_id"] == self.record["host"]["process_id"],
                "drawing gate replaced SOLIDWORKS")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--host-output-dir", type=base.host_directory)
    parser.add_argument("--drawing-template", type=base.host_directory, required=True)
    parser.add_argument("--cli-command", type=base.executable)
    parser.add_argument("--endpoint", default=os.environ.get("SWCLI_ENDPOINT", base.DEFAULT_ENDPOINT))
    parser.add_argument("--request-timeout", type=base.request_timeout, default=120)
    args = parser.parse_args(argv)
    directory = args.output_dir.expanduser().resolve()
    host = base.host_directory(args.host_output_dir or str(directory))
    directory.mkdir(parents=True, exist_ok=True)
    smoke = DrawingSmoke(directory=directory, host_directory=host, endpoint=args.endpoint,
                         cli=[args.cli_command] if args.cli_command else None,
                         request_timeout_seconds=args.request_timeout)
    smoke.record_path = directory / "drawings.json"
    with smoke.record_path.open("x", encoding="utf-8") as stream:
        json.dump(smoke.record, stream)
    error = None
    try:
        smoke.run_drawings(args.drawing_template)
    except Exception as exc:
        error = exc
        smoke.record["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        smoke.cleanup()
        smoke.record.update(state="completed", success=error is None and not smoke.record["cleanup_errors"])
        smoke.checkpoint("completed")
    if error:
        raise error
    require(smoke.record["success"] and smoke.checkpoint_error is None, "drawing gate cleanup/checkpoint failed")


if __name__ == "__main__":
    main()
