"""Bounded capture of a newly verified temporary CAD output, before publication."""

import base64
import hashlib
import os
from pathlib import Path
import stat

MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_BASE64_CHARS = 4 * ((MAX_ARTIFACT_BYTES + 2) // 3)


def capture_content(path, expected_size):
    """Internal only: callers supply their own verified, still-temporary output.

    A transfer error must never replace the result of CAD generation/publication.
    This is deliberately not an operation that accepts an arbitrary file path.
    """
    info = {"limit_bytes": MAX_ARTIFACT_BYTES}
    if expected_size > MAX_ARTIFACT_BYTES:
        return {**info, "status": "too_large"}
    try:
        path = Path(path)
        identity = path.lstat()
        if not stat.S_ISREG(identity.st_mode):
            raise ValueError("artifact is not a regular file")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as source:
            before = os.fstat(source.fileno())
            if ((before.st_dev, before.st_ino) != (identity.st_dev, identity.st_ino)
                    or not stat.S_ISREG(before.st_mode) or before.st_size != expected_size):
                raise ValueError("artifact changed before capture")
            data = source.read(MAX_ARTIFACT_BYTES + 1)
            after = os.fstat(source.fileno())
        if (len(data) != expected_size or len(data) > MAX_ARTIFACT_BYTES
                or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)):
            raise ValueError("artifact changed during capture")
        return {**info, "status": "ready", "sha256": hashlib.sha256(data).hexdigest(),
                "data_base64": base64.b64encode(data).decode("ascii")}
    except (OSError, ValueError) as exc:
        return {**info, "status": "unavailable",
                "error": {"code": type(exc).__name__, "message": str(exc)}}
