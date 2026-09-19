"""Manifest-driven export utility built from typed SWCLI operations."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..hosts.windows import PROG_ID, _com_value, _error
from ..hosts.windows_documents import (
    close_active_windows_document,
    export_active_windows_document,
    open_windows_document,
)


def _parse_manifest_lines(lines: Iterable[str]) -> List[str]:
    items = []
    for raw_line in lines:
        item = raw_line.split("#", 1)[0].strip()
        if item:
            items.append(item)
    return items


def _resolve_manifest_item(workspace: Path, item: str) -> Path:
    normalized = item.replace("\\", "/")
    path = Path(normalized)
    if not path.is_absolute():
        path = workspace / path
    return path.resolve()


def _batch_targets(source: Path, outdir: Path) -> List[Path]:
    name = source.name.casefold()
    extension = source.suffix.casefold()
    if name.endswith(".rend.sldasm"):
        return [outdir / f"{source.stem}.GLB"]
    if extension in {".sldprt", ".sldasm"}:
        return [outdir / f"{source.stem}.STEP"]
    if extension == ".slddrw":
        return [
            outdir / f"{source.stem}.PDF",
            outdir / f"{source.stem}.DWG",
        ]
    return []


def _plan_batch(
    items: Iterable[str], workspace: Path, outdir: Path, *, overwrite: bool = False
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    plans = []
    issues = []
    claimed_outputs: Dict[str, str] = {}
    for item in items:
        source = _resolve_manifest_item(workspace, item)
        targets = _batch_targets(source, outdir)
        if not source.is_file():
            issues.append(
                {"item": item, "type": "FileNotFound", "path": str(source)}
            )
            continue
        if not targets:
            issues.append(
                {
                    "item": item,
                    "type": "UnsupportedDocumentType",
                    "path": str(source),
                }
            )
            continue

        collision = False
        for target in targets:
            if target.exists() and not overwrite:
                issues.append(
                    {
                        "item": item,
                        "type": "OutputExists",
                        "output": str(target),
                    }
                )
                collision = True
            key = str(target).casefold()
            previous = claimed_outputs.get(key)
            if previous is not None:
                issues.append(
                    {
                        "item": item,
                        "type": "OutputCollision",
                        "output": str(target),
                        "conflicts_with": previous,
                    }
                )
                collision = True
            else:
                claimed_outputs[key] = item
        if not collision:
            plans.append(
                {
                    "item": item,
                    "source": source,
                    "targets": targets,
                }
            )
    return plans, issues


def batch_export_windows(
    manifest: str,
    *,
    workspace: str,
    outdir: Optional[str] = None,
    overwrite: bool = False,
    app: Any = None,
) -> Dict[str, Any]:
    """Export every manifest item using the typed document lifecycle."""

    if sys.platform != "win32":
        return {
            "ok": False,
            "action": "batch.export",
            "error": {
                "type": "UnsupportedPlatform",
                "message": "batch export requires Windows or a Wine Windows worker",
            },
        }

    manifest_path = Path(manifest).expanduser().resolve()
    workspace_path = Path(workspace).expanduser().resolve()
    outdir_path = (
        Path(outdir).expanduser().resolve()
        if outdir is not None
        else workspace_path / "export"
    )
    result: Dict[str, Any] = {
        "ok": False,
        "action": "batch.export",
        "manifest": str(manifest_path),
        "workspace": str(workspace_path),
        "outdir": str(outdir_path),
        "overwrite": overwrite,
    }
    if not manifest_path.is_file():
        result["error"] = {
            "type": "ManifestNotFound",
            "message": f"manifest does not exist: {manifest_path}",
        }
        return result
    if not workspace_path.is_dir():
        result["error"] = {
            "type": "WorkspaceNotFound",
            "message": f"workspace directory does not exist: {workspace_path}",
        }
        return result

    try:
        lines = manifest_path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        result["error"] = _error(exc)
        return result
    items = _parse_manifest_lines(lines)
    if not items:
        result["error"] = {
            "type": "EmptyManifest",
            "message": "manifest contains no export items",
        }
        return result

    plans, issues = _plan_batch(
        items, workspace_path, outdir_path, overwrite=overwrite
    )
    result["planned_count"] = len(plans)
    if issues:
        result["preflight_issues"] = issues
        result["error"] = {
            "type": "PreflightFailed",
            "message": "batch manifest failed validation before SOLIDWORKS was used",
        }
        return result
    outdir_path.mkdir(parents=True, exist_ok=True)

    import pythoncom
    import win32com.client

    owns_com = app is None
    if owns_com:
        pythoncom.CoInitialize()
    try:
        if app is None:
            try:
                app = win32com.client.GetActiveObject(PROG_ID)
            except Exception as exc:
                result["error"] = {
                    "type": "HostNotRunning",
                    "message": "SOLIDWORKS is not running; run 'sw-cli host start' first",
                    "cause": _error(exc),
                }
                return result
        if _com_value(app, "ActiveDoc") is not None:
            result["error"] = {
                "type": "ActiveDocument",
                "message": "close the active document before batch export",
            }
            return result
        item_results = []
        artifacts = []
        failed_count = 0
        for plan in plans:
            item_result: Dict[str, Any] = {
                "item": plan["item"],
                "source": str(plan["source"]),
                "ok": False,
                "exports": [],
            }
            opened = open_windows_document(str(plan["source"]), app=app)
            item_result["open"] = opened
            if opened["ok"]:
                for target in plan["targets"]:
                    exported = export_active_windows_document(
                        str(target),
                        overwrite=overwrite,
                        allow_source_modification=True,
                        app=app,
                    )
                    item_result["exports"].append(exported)
                    if exported["ok"]:
                        artifacts.append(exported["artifact"])
                closed = close_active_windows_document(discard=True, app=app)
                item_result["close"] = closed
                item_result["ok"] = (
                    all(exported["ok"] for exported in item_result["exports"])
                    and closed["ok"]
                )
            if not item_result["ok"]:
                failed_count += 1
            item_results.append(item_result)

            close_result = item_result.get("close")
            if close_result is not None and not close_result["ok"]:
                result["aborted"] = True
                break
    finally:
        if owns_com:
            pythoncom.CoUninitialize()

    result["results"] = item_results
    result["artifacts"] = artifacts
    result["total"] = len(item_results)
    result["ok_count"] = len(item_results) - failed_count
    result["failed_count"] = failed_count
    result["ok"] = failed_count == 0 and len(item_results) == len(plans)
    if not result["ok"]:
        result["error"] = {
            "type": "BatchExportFailed",
            "message": "one or more batch export items failed",
        }
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    from ..cli import main as swcli_main

    arguments = list(sys.argv[1:] if argv is None else argv)
    return swcli_main(["batch", "export", *arguments])


if __name__ == "__main__":
    raise SystemExit(main())
