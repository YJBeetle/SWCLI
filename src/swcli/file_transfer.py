"""Stream workspace files without putting whole files in CLI/MCP messages."""

import base64
import hashlib
import uuid

from .daemon.client import call_daemon, DEFAULT_ENDPOINT
from .safe_workspace import CHUNK_BYTES, SafeWorkspace, file_hash, signature


class TransferError(RuntimeError):
    def __init__(self, message, *, transfer_id=None, session_id=None):
        super().__init__(message)
        self.transfer_id, self.session_id = transfer_id, session_id


class FileTransferClient:
    def __init__(self, root, *, endpoint=DEFAULT_ENDPOINT, session_id=None,
                 timeout_seconds=600, connect_timeout_seconds=3):
        if not root:
            raise ValueError("Configure SWCLI_CLIENT_WORKSPACE or --client-workspace first")
        self.root = root
        self.endpoint = endpoint
        self.session_id = session_id or "default"
        self.timeout_seconds = timeout_seconds
        self.connect_timeout_seconds = connect_timeout_seconds

    def rpc(self, name, parameters, *, request_id=None):
        from .result_schemas import validate_operation_result
        result = call_daemon("workspace." + name, parameters, endpoint=self.endpoint,
            session_id=self.session_id, request_id=request_id or str(uuid.uuid4()),
            timeout_seconds=self.timeout_seconds, connect_timeout_seconds=self.connect_timeout_seconds)
        if not result.get("success"):
            error = result.get("error", {})
            raise TransferError(error.get("code", "WorkspaceError") + ": " + error.get("message", "Workspace transfer failed"))
        value = result["result"]
        validate_operation_result("workspace." + name, value)
        return value

    def upload(self, source, destination, *, overwrite=False, request_id=None, resume_transfer=None, progress=None):
        transfer_id = None
        with SafeWorkspace(self.root) as root, root.open_read(source) as stream:
            before = signature(stream)
            digest = file_hash(stream)
            if signature(stream) != before:
                raise ValueError("Upload source changed while hashing")
            try:
                if resume_transfer:
                    record = self.rpc("upload-status", {"transfer_id": resume_transfer})
                else:
                    record = self.rpc("upload-begin", {"path": destination, "size_bytes": before[2],
                        "sha256": digest, "overwrite": overwrite}, request_id=request_id)
                transfer_id = record["transfer_id"]
                from .safe_workspace import relative_parts
                if (record["sha256"] != digest or record["size_bytes"] != before[2]
                        or record["path"] != "/".join(relative_parts(destination))):
                    raise ValueError("Resumed upload does not match the source and destination")
                if record["state"] == "committed":
                    return self._result("upload", record)
                if record["state"] != "uploading" or not 0 <= record["offset"] <= before[2]:
                    raise ValueError("Upload is not resumable")
                offset = record["offset"]
                stream.seek(offset)
                if progress:
                    progress(offset, before[2])
                while offset < before[2]:
                    if signature(stream) != before:
                        raise ValueError("Upload source changed during transfer")
                    data = stream.read(min(CHUNK_BYTES, before[2] - offset))
                    if not data:
                        raise ValueError("Upload source ended early")
                    record = self.rpc("upload-chunk", {"transfer_id": transfer_id, "offset": offset,
                        "data": base64.b64encode(data).decode("ascii")})
                    offset += len(data)
                    if record["offset"] != offset or record["transfer_id"] != transfer_id:
                        raise ValueError("Daemon acknowledged an unexpected upload range")
                    if progress:
                        progress(offset, before[2])
                if signature(stream) != before:
                    raise ValueError("Upload source changed before commit")
                record = self.rpc("upload-commit", {"transfer_id": transfer_id})
                if record["state"] != "committed" or record["sha256"] != digest:
                    raise ValueError("Daemon did not confirm a verified upload commit")
                return self._result("upload", record)
            except Exception as exc:
                error = TransferError(str(exc), transfer_id=transfer_id, session_id=self.session_id)
                error._swcli_transport_phase = getattr(exc, "_swcli_transport_phase", None)
                raise error from exc

    def download(self, source, destination, *, overwrite=False, request_id=None, progress=None):
        record = self.rpc("download-begin", {"path": source}, request_id=request_id)
        transfer_id = record["transfer_id"]
        if record["state"] != "downloading":
            raise TransferError("Download handle is no longer active", transfer_id=transfer_id, session_id=self.session_id)
        failure = None
        try:
            with SafeWorkspace(self.root) as root, root.stage(destination, overwrite=overwrite) as target:
                offset, digest = 0, hashlib.sha256()
                if progress:
                    progress(0, record["size_bytes"])
                while offset < record["size_bytes"]:
                    chunk = self.rpc("download-chunk", {"transfer_id": transfer_id, "offset": offset, "length": CHUNK_BYTES})
                    if (chunk["transfer_id"] != transfer_id or chunk["offset"] != offset
                            or chunk["sha256"] != record["sha256"] or chunk["size_bytes"] != record["size_bytes"]):
                        raise ValueError("Daemon returned an unexpected download manifest or range")
                    data = base64.b64decode(chunk["data"], validate=True)
                    if not data or len(data) > min(CHUNK_BYTES, record["size_bytes"] - offset):
                        raise ValueError("Invalid download chunk size")
                    if target.stream.write(data) != len(data):
                        raise OSError("Short workspace download write")
                    digest.update(data)
                    offset += len(data)
                    if progress:
                        progress(offset, record["size_bytes"])
                if digest.hexdigest() != record["sha256"]:
                    raise ValueError("Downloaded file SHA256 mismatch")
                target.publish()
                result = self._result("download", record)
                result.update(local_path=str(root.path.joinpath(*destination.replace("\\", "/").split("/"))))
        except Exception as exc:
            failure = TransferError(str(exc), transfer_id=transfer_id, session_id=self.session_id)
            failure._swcli_transport_phase = getattr(exc, "_swcli_transport_phase", None)
        try:
            self.rpc("download-end", {"transfer_id": transfer_id})
        except Exception as exc:
            if failure is None:
                result["cleanup_error"] = str(exc)
            else:
                failure.add_note(str(exc)) if hasattr(failure, "add_note") else None
        if failure:
            raise failure
        return result

    @staticmethod
    def _result(direction, record):
        return {"success": True, "direction": direction,
                **{key: record[key] for key in ("transfer_id", "path", "size_bytes", "sha256")}}


def configure_parser(subcommands):
    parser = subcommands.add_parser("transfer", help="stream files between configured client and daemon workspaces")
    commands = parser.add_subparsers(dest="transfer_command", required=True)
    for name in ("upload", "download"):
        command = commands.add_parser(name)
        command.add_argument("source", help="source workspace-relative path")
        command.add_argument("destination", help="destination workspace-relative path")
        command.add_argument("--overwrite", action="store_true")
        command.add_argument("--json", action="store_true", dest="as_json")
        if name == "upload":
            command.add_argument("--resume", dest="resume_transfer", help="resume an upload ID in the same session")


def run(args):
    import json
    import sys
    try:
        client = FileTransferClient(args.client_workspace, endpoint=args.endpoint, session_id=args.session,
            timeout_seconds=args.request_timeout, connect_timeout_seconds=args.connect_timeout)
        kwargs = dict(overwrite=args.overwrite, request_id=args.request_id)
        if args.transfer_command == "upload":
            kwargs["resume_transfer"] = args.resume_transfer
        result = getattr(client, args.transfer_command)(args.source, args.destination, **kwargs)
    except Exception as exc:
        result = {"success": False, "error": {"code": type(exc).__name__, "message": str(exc)}}
        if isinstance(exc, TransferError):
            result.update(transfer_id=exc.transfer_id, session_id=exc.session_id)
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False))
    elif result["success"]:
        print(f"{result['direction']}: {result['path']} ({result['size_bytes']} bytes, SHA256 {result['sha256']})")
    else:
        print(result["error"]["message"], file=sys.stderr)
    return 0 if result["success"] else 1
