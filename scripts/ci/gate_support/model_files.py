"""NativeFileCases extracted without changing full-suite assertions."""

import hashlib
from pathlib import (
    Path,
    PureWindowsPath,
)

from swcli.hosts.export_validation import export_file_valid
from swcli.result_schemas import validate_operation_result


from gate_support.model_checks import (
    host_directory,
    LEASE_TTL_SECONDS,
    require,
)


class NativeFileCases:
    def sample_exports(self, part, assembly):
        document = self.command("document", "open", part, "--read-only")["document"][
            "document_id"
        ]
        stamp = self.command("document", "inspect", document=document)["document"][
            "update_stamp"
        ]
        require(
            type(stamp) is int, "GetUpdateStamp unavailable on the installed sample"
        )
        lease = self.command(
            "document",
            "lease",
            "acquire",
            "--ttl-seconds",
            LEASE_TTL_SECONDS,
            document=document,
        )["lease"]["lease_id"]
        denied = str(PureWindowsPath(self.host_directory) / "lease-denied.STEP")
        self.command(
            "document",
            "export",
            "--document",
            document,
            denied,
            session=self.session + "-contender",
            expected_error="DocumentLeaseConflict",
        )
        require(
            not (self.directory / "lease-denied.STEP").exists(),
            "denied export created an artifact",
        )
        self.renew(document)
        self.command(
            "document",
            "export",
            "--document",
            document,
            str(PureWindowsPath(self.host_directory) / "leased.STEP"),
            lease=lease,
        )
        self.verify_step("leased.STEP")
        self.command("document", "lease", "release", lease)
        foreground = self.command("document", "open", assembly, "--read-only")[
            "document"
        ]["document_id"]
        self.command(
            "document",
            "export",
            "--document",
            document,
            str(PureWindowsPath(self.host_directory) / "multi-document.STEP"),
        )
        self.verify_step("multi-document.STEP")
        documents = self.command("document", "list")
        by_id = {item["document_id"]: item for item in documents["documents"]}
        self.background({"document": by_id[document]}, document)
        require(
            by_id[foreground]["active"] is True
            and by_id[foreground]["current"] is True,
            "background export did not restore the foreground assembly",
        )
        self.close(foreground)
        self.close(document)

    def model_exports(self, document, stem, native_files):
        """Exercise all mesh translators against our saved, clean native fixture.

        Evidence stays in the modeling directory, outside the host project's
        six formal delivery exports. Structural validation is not a claim of
        tessellation accuracy, watertightness or material fidelity.
        """
        proofs = self.record.setdefault("model_exports", [])
        before = self.command("document", "inspect", document=document)
        descriptor = before["document"]
        require(descriptor["document_id"] == document
                and descriptor["type"] in (1, 2) and bool(descriptor["path"])
                and descriptor["modified"] is False and before["needs_rebuild"] == 0,
                "mesh export fixture is not a saved, rebuilt part or assembly")
        source_hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in native_files}
        for format_name in ("STL", "3MF", "AMF", "GLB"):
            name = f"{stem}-export.{format_name}"
            target = str(PureWindowsPath(self.host_directory) / name)
            artifact_file = self.directory / name
            exported = self.write("document", "export", target, "--strict",
                                  document=document)
            validate_operation_result("document.export", exported)
            artifact = exported["artifact"]
            require(PureWindowsPath(exported["output"]) == PureWindowsPath(target)
                    and PureWindowsPath(artifact["path"]) == PureWindowsPath(target)
                    and artifact["format"] == format_name
                    and artifact_file.is_file()
                    and artifact["size_bytes"] == artifact_file.stat().st_size
                    and not exported.get("warnings"),
                    f"{format_name} export artifact metadata/file verification failed")
            require(export_file_valid(format_name, artifact_file),
                    f"{format_name} export has invalid mesh container structure")
            after = self.command("document", "inspect", document=document)
            require(all(after["document"][key] == descriptor[key]
                        for key in ("document_id", "path", "type", "modified",
                                    "active", "current"))
                    and after["needs_rebuild"] == 0,
                    f"{format_name} export changed native document state")
            require(all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
                        for path, digest in source_hashes.items()),
                    f"{format_name} export changed native source bytes")
            proofs.append({"document_id": document, "document_type": descriptor["type"],
                           "artifact": artifact,
                           "sha256": hashlib.sha256(artifact_file.read_bytes()).hexdigest(),
                           "strict": True, "source_state_unchanged": True,
                           "source_bytes_unchanged": True,
                           "verification_scope": "bounded-mesh-container-structure"})
            self.checkpoint(f"{stem}-export.{format_name}.verified")

    def generated_assembly(self):
        """Save our own solid part and one-component ASM, with no sample exception."""
        part = self.create()
        profile = self.rectangle(part)
        self.feature(part, profile["sketch"]["sketch_id"], depth=10)
        metrics = self.measure(part, volume=12000)["metrics"]
        require(metrics["solid_body_count"] == 1, "generated component is not one solid")
        source_path = str(PureWindowsPath(self.host_directory) / "component.SLDPRT")
        source_file = self.directory / "component.SLDPRT"
        saved_part = self.write("document", "save-as", source_path, document=part)
        require(saved_part["document"]["modified"] is False
                and source_file.is_file() and source_file.stat().st_size >= 512
                and saved_part["artifact"]["size_bytes"] == source_file.stat().st_size,
                "generated component save-as failed size/modified verification")
        source_digest = hashlib.sha256(source_file.read_bytes()).hexdigest()
        self.close(part)
        loaded = self.command("document", "open", source_path, "--read-only")
        source = loaded["document"]["document_id"]
        require(source != part and loaded["document"]["type"] == 1
                and loaded["read_only"] is True and loaded["api_errors"] == 0
                and loaded["api_warnings"] in (0, 2)
                and loaded["document"]["modified"] is False,
                "generated component did not reopen clean and read-only")
        self.measure(source, volume=12000, area=metrics["surface_area_mm2"])
        source_structure = self.command("document", "inspect", "--detail", "structure",
                                        document=source)["structure"]
        configuration = source_structure["configurations"]["active"]
        require(bool(configuration), "generated component has no active configuration")
        self.model_exports(source, "component", (source_file,))
        created = self.command("document", "create", "--type", "assembly")
        assembly = created["document"]["document_id"]
        require(created["created"] is True and created["document"]["type"] == 2
                and created["document"]["path"] == "" and assembly != source,
                "assembly creation did not return a new unsaved assembly")
        inserted = self.write("assembly", "add-component", source_path,
                              "--configuration", configuration, document=assembly)
        require(inserted["inserted"] is True and inserted["document"]["document_id"] == assembly
                and inserted["component_count_before"] == 0
                and inserted["component_count_after"] == 1
                and PureWindowsPath(inserted["component"]["path"]) == PureWindowsPath(source_path)
                and inserted["component"]["configuration"] == configuration,
                "generated assembly did not insert exactly the requested component")

        def signature(document):
            observed = self.command("document", "inspect", "--detail", "structure",
                                    document=document)
            structure = observed["structure"]
            features = structure["features"]
            require(features["count"] > 0 and not features["truncated"],
                    "generated assembly feature tree is empty or truncated")
            return {"configurations": structure["configurations"],
                    "features": [(item["name"], item["type"]) for item in features["items"]]}

        expected = signature(assembly)
        require(sum(kind == "Reference" for _, kind in expected["features"]) == 1,
                "generated assembly tree does not contain exactly one component reference")
        target = str(PureWindowsPath(self.host_directory) / "generated.SLDASM")
        native_file = self.directory / "generated.SLDASM"
        saved = self.write("document", "save-as", target, document=assembly)
        # Unlike the official fixture preparation, ALL errors are rejected here.
        require(saved["api_saved"] is True and saved["save_errors"] == 0
                and saved["document"]["document_id"] == assembly
                and saved["document"]["modified"] is False
                and PureWindowsPath(saved["document"]["path"]) == PureWindowsPath(target)
                and saved["artifact"]["format"] == "SLDASM"
                and native_file.is_file() and native_file.stat().st_size >= 512
                and saved["artifact"]["size_bytes"] == native_file.stat().st_size,
                "generated assembly save-as failed native/file verification")
        save_as_bytes = native_file.stat().st_size
        self.verify_in_place_save(assembly, native_file)
        digest = hashlib.sha256(native_file.read_bytes()).hexdigest()
        self.model_exports(assembly, "assembly", (native_file, source_file))
        self.close(assembly)
        # Unload the explicitly opened part too: assembly reopens must not be
        # satisfied solely by this fixture's still-live source COM object.
        # Closing the assembly can already unload its referenced source. Observe
        # this before issuing a second close; never swallow DocumentNotFound.
        remaining = self.command("document", "list")["documents"]
        if any(item["document_id"] == source for item in remaining):
            self.close(source)
        else:
            self.owned.pop(source, None)
            self.leases.pop(source, None)
        self.require_empty()
        ids = {assembly}
        opens = []
        for read_only in (False, True):
            opened = self.command("document", "open", target,
                                  *(("--read-only",) if read_only else ()))
            reopened = opened["document"]["document_id"]
            opens.append({"read_only": opened["read_only"], "api_errors": opened["api_errors"],
                          "api_warnings": opened["api_warnings"],
                          "modified": opened["document"]["modified"]})
            require(reopened not in ids and opened["document"]["type"] == 2
                    and opened["read_only"] is read_only and opened["api_errors"] == 0
                    and opened["api_warnings"] in ((0, 2) if read_only else (0,))
                    and opened["document"]["modified"] is False,
                    "generated assembly did not reopen clean with a fresh document ID")
            ids.add(reopened)
            require(signature(reopened) == expected,
                    "generated assembly save/reopen changed configurations or feature tree")
            self.close(reopened)
            require(hashlib.sha256(native_file.read_bytes()).hexdigest() == digest,
                    "generated assembly reopen changed its saved bytes")
        require(hashlib.sha256(source_file.read_bytes()).hexdigest() == source_digest,
                "generated assembly insertion/save changed the source part")
        self.record["generated_assembly"] = {
            "component": inserted["component"], "component_sha256": source_digest,
            "component_metrics": metrics, "save_as_bytes": save_as_bytes,
            "size_bytes": native_file.stat().st_size, "sha256": digest,
            "opens": opens, "structure_unchanged": True, "fresh_document_id": True,
            "source_unloaded_before_reopen": True,
            "scope": "one-component-native-save-reopen",
        }
        self.checkpoint("generated-assembly.verified")

    def assembly_save_reopen(self, assembly):
        # Rename only the assembly into the evidence directory. Referenced
        # parts remain at their original paths: this is not Pack and Go.
        opened = self.command("document", "open", assembly)
        document = opened["document"]["document_id"]
        require(opened["document"]["type"] == 2 and opened["api_errors"] == 0
                and opened["api_warnings"] == 0 and opened["read_only"] is False,
                "sample did not open as a writable assembly without errors/warnings")
        before = self.command(
            "document", "inspect", "--detail", "structure", document=document
        )["structure"]

        def signature(structure):
            features = structure["features"]
            require(features["count"] > 0 and not features["truncated"],
                    "assembly feature tree is empty or truncated")
            return {
                "configurations": structure["configurations"],
                "features": [(item["name"], item["type"]) for item in features["items"]],
            }

        expected = signature(before)
        target = str(PureWindowsPath(self.host_directory) / "assembly.SLDASM")
        # Installed samples can retain a modified flag after their first SaveAs
        # (also observed on native Windows). Prepare a NEW file, never Save3 the
        # installed source. Only this precise post-save error is permitted here;
        # production save-as and every subsequent save remain strict.
        saved = self.write("document", "save-as", target, document=document,
                           allowed_error="DocumentStillModified")
        require(saved["document"]["document_id"] == document
                and saved["api_saved"] is True and saved["save_errors"] == 0
                and PureWindowsPath(saved["document"]["path"]) == PureWindowsPath(target)
                and saved["artifact"]["format"] == "SLDASM"
                and PureWindowsPath(saved["artifact"]["path"]) == PureWindowsPath(target)
                and saved["file_verification"]["minimum_size_valid"] is True,
                "assembly preparation save-as left an invalid document/file state")
        initial_modified = saved["document"]["modified"]
        require((saved["ok"] is True and initial_modified is False)
                or (saved["ok"] is False and initial_modified is True
                    and saved["error"]["type"] == "DocumentStillModified"),
                "assembly preparation has inconsistent modified/error evidence")
        native_file = self.directory / "assembly.SLDASM"
        require(native_file.is_file() and native_file.stat().st_size >= 512,
                "assembly save-as produced an empty or truncated file")
        save_as_bytes = native_file.stat().st_size
        require(saved["artifact"]["size_bytes"] == save_as_bytes,
                "assembly save-as size evidence disagrees with the artifact")
        proof = self.record["assembly_save_reopen"] = {
            "source": assembly,
            "preparation": {"path": target, "size_bytes": save_as_bytes,
                            "modified_after_save_as": initial_modified,
                            "error": saved.get("error")},
        }
        self.checkpoint("assembly-preparation.saved")
        self.close(document)
        prepared = self.command("document", "open", target)
        prepared_id = prepared["document"]["document_id"]
        require(prepared_id != document and prepared["document"]["type"] == 2
                and prepared["read_only"] is False and prepared["api_errors"] == 0
                and prepared["api_warnings"] == 0,
                "prepared assembly did not reopen as a fresh writable assembly")
        require(prepared["document"]["modified"] is False,
                "prepared assembly still needs saving on writable reopen")
        structure = self.command("document", "inspect", "--detail", "structure",
                                 document=prepared_id)["structure"]
        require(signature(structure) == expected,
                "assembly preparation changed configurations or feature tree")
        document = prepared_id
        # Save3 on the prepared file is strictly checked, including modified.
        self.verify_in_place_save(document, native_file)
        digest = hashlib.sha256(native_file.read_bytes()).hexdigest()
        self.close(document)
        reopened = self.command("document", "open", target, "--read-only")
        reopened_id = reopened["document"]["document_id"]
        require(reopened_id != document and reopened["document"]["type"] == 2
                and reopened["read_only"] is True and reopened["api_errors"] == 0
                and reopened["api_warnings"] in (0, 2)
                and reopened["document"]["modified"] is False,
                "saved assembly did not reopen as a fresh read-only assembly")
        after = self.command(
            "document", "inspect", "--detail", "structure", document=reopened_id
        )["structure"]
        require(signature(after) == expected,
                "assembly save/reopen changed configurations or feature tree")
        self.close(reopened_id)
        require(hashlib.sha256(native_file.read_bytes()).hexdigest() == digest,
                "read-only assembly reopen changed the saved artifact")
        proof.update({
            "save_as_bytes": save_as_bytes,
            "size_bytes": native_file.stat().st_size,
            "sha256": digest,
            "structure_unchanged": True,
            "fresh_document_id": True,
            "writable_reopen_clean": True,
        })
        self.checkpoint("assembly-save-reopen.verified")

    def verify_in_place_save(self, document, native_file):
        kind = {".SLDASM": "assembly", ".SLDDRW": "drawing", ".SLDPRT": "part"}[
            native_file.suffix.upper()
        ]
        saved = self.write("document", "save", document=document)
        require(saved["api_saved"] is True and saved["save_errors"] == 0
                and saved["document_after"]["modified"] is False,
                f"{kind} in-place save failed")
        require(native_file.is_file() and native_file.stat().st_size >= 512,
                f"{kind} in-place save produced an empty or truncated file")
        self.record.setdefault("native_in_place_saves", []).append({
            "format": native_file.suffix[1:].upper(),
            "size_bytes": native_file.stat().st_size,
        })

    def drawing_copy_first(self, local_drawing, *, work_directory, host_work_directory,
                           reopen=False, inspect_structure=True):
        # Diagnostic control: no baseline source open/close, no save, no retry.
        # The coordinator has already cloned the sibling reference bundle.
        source = Path(local_drawing)
        require(source.is_file() and source.suffix.lower() == ".slddrw",
                "drawing source must be a readable local SLDDRW file")
        data = source.read_bytes()
        require(len(data) >= 512, "drawing source is empty or truncated")
        require(work_directory is not None and host_work_directory is not None,
                "copy-first diagnosis requires both private fixture namespaces")
        host_directory(host_work_directory)
        target = Path(work_directory) / "drawing.SLDDRW"
        require(target.parent.is_dir() and target.resolve() != source.resolve(),
                "copy-first diagnosis requires a separate private work directory")
        with target.open("xb") as stream:
            stream.write(data)
        digest = hashlib.sha256(data).hexdigest()
        path = str(PureWindowsPath(host_work_directory) / target.name)
        proof = {"path": path, "source_sha256_before": digest,
                 "baseline_source_opened": False, "save_attempted": False,
                 "reopen_requested": reopen, "structure_inspected": False,
                 "structure_inspection_requested": inspect_structure}
        self.record["drawing_copy_first"] = proof
        self.checkpoint("drawing-copy-first.opening")
        try:
            opened = self.command("document", "open", path)
            document = opened["document"]["document_id"]
            require(opened["document"]["type"] == 3 and opened["read_only"] is False
                    and opened["api_errors"] == 0 and opened["api_warnings"] == 0,
                    "private drawing did not open writable without warnings")
            proof["opened"] = opened
            self.checkpoint("drawing-copy-first.opened")
            if inspect_structure:
                structure = self.command("document", "inspect", "--detail", "structure",
                                         document=document)["structure"]
                require(structure["features"]["count"] > 0 and not structure["features"]["truncated"],
                        "private drawing structure is empty or truncated")
                proof["structure"] = structure
                proof["structure_inspected"] = True
            self.close(document)
            if reopen:
                # A second lifecycle operation, not retrying a failed open.
                # Do not reset the host, change paths/mode, or save the copy.
                self.require_empty(after_case="drawing-copy-first-close")
                self.checkpoint("drawing-copy-reopen.opening")
                reopened = self.command("document", "open", path)
                fresh = reopened["document"]["document_id"]
                proof["reopened"] = reopened
                require(fresh != document and reopened["document"]["type"] == 3
                        and reopened["read_only"] is False
                        and reopened["api_errors"] == 0 and reopened["api_warnings"] == 0,
                        "private drawing reopen is not fresh, writable and warning-free")
                if inspect_structure:
                    observed = self.command("document", "inspect", "--detail", "structure",
                                            document=fresh)["structure"]
                    features = observed["features"]
                    require(features["count"] > 0 and not features["truncated"]
                            and [(item["name"], item["type"]) for item in features["items"]]
                            == [(item["name"], item["type"]) for item in structure["features"]["items"]],
                            "private drawing reopen changed the feature structure")
                    proof["reopened_structure"] = observed
                self.close(fresh)
        finally:
            proof["source_sha256_after"] = hashlib.sha256(source.read_bytes()).hexdigest()
            proof["copy_sha256_after"] = hashlib.sha256(target.read_bytes()).hexdigest()
            require(proof["source_sha256_after"] == digest and proof["copy_sha256_after"] == digest,
                    "copy-first diagnosis changed drawing bytes without saving")

    def drawing_save_reopen(self, drawing, local_drawing, *,
                            work_directory=None, host_work_directory=None,
                            save_as=False):
        # Only save a private copy. The installed source is opened read-only
        # for the baseline. Neither mode copies or requests saving references.
        case = "drawing-save-as-reopen" if save_as else "drawing-save-reopen"
        source = Path(local_drawing)
        require(source.is_file() and source.suffix.lower() == ".slddrw",
                "drawing source must be a readable local SLDDRW file")
        source_bytes = source.read_bytes()
        require(len(source_bytes) >= 512, "drawing source is empty or truncated")
        source_digest = hashlib.sha256(source_bytes).hexdigest()
        require((work_directory is None) == (host_work_directory is None),
                "drawing work directories must supply both path namespaces")
        work_directory = (Path(work_directory).expanduser().resolve()
                          if work_directory is not None else self.directory)
        require(work_directory.is_dir(), "drawing work directory does not exist")
        host_work_directory = (self.host_directory if host_work_directory is None
                               else host_work_directory)
        host_directory(host_work_directory)
        native_file = work_directory / ("drawing-save-as.SLDDRW" if save_as else "drawing.SLDDRW")
        input_file = work_directory / "drawing-save-as-source.SLDDRW" if save_as else native_file
        input_path = str(PureWindowsPath(host_work_directory) / input_file.name)
        target = str(PureWindowsPath(host_work_directory) / native_file.name)
        evidence_file = self.directory / native_file.name
        proof = {
            "source": drawing,
            "source_sha256_before": source_digest,
            "observation_scope": "top-level-feature-tree",
            "work_path": target,
            "opens": [],
        }
        self.record[case.replace("-", "_")] = proof

        def open_checked(path, *, read_only):
            result = self.command("document", "open", path,
                                  *(("--read-only",) if read_only else ()))
            proof["opens"].append({
                "path": path, "read_only": result["read_only"],
                "api_errors": result["api_errors"],
                "api_warnings": result["api_warnings"],
                "document_id": result["document"]["document_id"],
                "modified": result["document"]["modified"],
            })
            require(result["document"]["type"] == 3
                    and result["read_only"] is read_only
                    and result["api_errors"] == 0,
                    "drawing did not open with the required type/read-only state")
            # swFileLoadWarning_ReadOnly = 2 is expected only for explicit
            # read-only opens. All other warnings (including lost references)
            # fail the gate rather than silently weakening the reopen proof.
            require(result["api_warnings"] in ((0, 2) if read_only else (0,)),
                    f"drawing open has unexpected warnings: {result['api_warnings']}")
            return result["document"]["document_id"]

        def signature(document):
            structure = self.command("document", "inspect", "--detail", "structure",
                                     document=document)["structure"]
            features = structure["features"]
            require(features["count"] > 0 and not features["truncated"],
                    "drawing feature tree is empty or truncated")
            return [(item["name"], item["type"]) for item in features["items"]]

        try:
            original = open_checked(drawing, read_only=True)
            expected = signature(original)
            self.close(original)
            with input_file.open("xb") as stream:
                stream.write(source_bytes)
            document = open_checked(input_path, read_only=False)
            require(signature(document) == expected,
                    "drawing copy changed the source feature tree")
            if save_as:
                saved = self.write("document", "save-as", target, document=document)
                require(saved["api_saved"] is True and saved["save_errors"] == 0
                        and saved["document"]["document_id"] == document
                        and saved["document"]["type"] == 3
                        and saved["document"]["modified"] is False
                        and PureWindowsPath(saved["document"]["path"]) == PureWindowsPath(target)
                        and saved["artifact"]["format"] == "SLDDRW"
                        and PureWindowsPath(saved["artifact"]["path"]) == PureWindowsPath(target)
                        and saved["file_verification"]["minimum_size_valid"] is True
                        and native_file.is_file() and native_file.stat().st_size >= 512
                        and saved["artifact"]["size_bytes"] == native_file.stat().st_size,
                        "drawing save-as failed native/file verification")
                require(hashlib.sha256(input_file.read_bytes()).hexdigest() == source_digest,
                        "drawing save-as changed the private input file")
                proof["save_as_bytes"] = native_file.stat().st_size
            else:
                self.verify_in_place_save(document, native_file)
            proof["size_bytes"] = native_file.stat().st_size
            digest = hashlib.sha256(native_file.read_bytes()).hexdigest()
            self.close(document)
            if save_as:
                self.require_empty()
                writable = open_checked(target, read_only=False)
                require(writable not in (original, document)
                        and proof["opens"][-1]["modified"] is False,
                        "drawing save-as writable reopen is not fresh and clean")
                require(signature(writable) == expected,
                        "drawing save-as writable reopen changed the feature tree")
                self.close(writable)
                self.require_empty()
                require(hashlib.sha256(native_file.read_bytes()).hexdigest() == digest,
                        "writable drawing reopen changed the saved artifact")
            reopened = open_checked(target, read_only=True)
            require(reopened != document and (not save_as or reopened not in (original, writable)),
                    "drawing reopen reused an expired document ID")
            if save_as:
                require(proof["opens"][-1]["modified"] is False,
                        "drawing save-as read-only reopen is not clean")
            require(signature(reopened) == expected,
                    "drawing save/reopen changed the feature tree")
            self.close(reopened)
            if save_as:
                self.require_empty()
                require(hashlib.sha256(input_file.read_bytes()).hexdigest() == source_digest,
                        "drawing save-as reopen changed the private input file")
                proof["input_sha256_unchanged"] = True
            require(hashlib.sha256(native_file.read_bytes()).hexdigest() == digest,
                    "read-only drawing reopen changed the saved artifact")
            proof.update(sha256=digest, structure_unchanged=True, fresh_document_id=True)
        finally:
            proof["source_sha256_after"] = hashlib.sha256(source.read_bytes()).hexdigest()
            require(proof["source_sha256_after"] == source_digest,
                    "drawing gate changed the installed source")
        # Keep reference bundles outside the evidence tree. Publish only after
        # all checks, including source protection, without replacing evidence.
        # The host adapter owns fixture preparation and cleanup on every exit.
        if native_file.resolve() != evidence_file.resolve():
            verified_bytes = native_file.read_bytes()
            require(hashlib.sha256(verified_bytes).hexdigest() == digest,
                    "drawing changed before copying verified evidence")
            stream = evidence_file.open("xb")  # Failure here never owns an existing file.
            try:
                with stream:
                    stream.write(verified_bytes)
            except Exception:
                evidence_file.unlink()  # Remove only this call's incomplete copy.
                raise
        proof["evidence_path"] = str(evidence_file)
        self.checkpoint(case + ".verified")

    def verify_step(self, name):
        path = self.directory / name
        require(
            path.is_file() and b"ISO-10303-21" in path.read_bytes()[:512],
            f"export did not produce a valid local STEP file: {path}",
        )
