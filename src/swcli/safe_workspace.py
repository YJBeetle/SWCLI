"""Rooted regular-file access and atomic publication for workspace transfers."""

import hashlib
import os
from pathlib import Path
import re
import stat
import uuid

CHUNK_BYTES = 1024 * 1024


def relative_parts(value):
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise ValueError("A workspace-relative file path is required")
    parts = value.replace("\\", "/").split("/")
    for part in parts:
        base = part.split(".")[0].upper()
        if (not part or part in (".", "..") or len(part) > 240 or part.endswith((" ", "."))
                or part.lower().startswith(".swcli-")
                or any(ord(c) < 32 or c in '<>:"|?*' for c in part)
                or base in ("CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$")
                or re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", base)):
            raise ValueError("Invalid workspace-relative file path")
    return parts


def signature(stream):
    value = os.fstat(stream.fileno())
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise ValueError("Workspace files must be regular files without hard links")
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def file_hash(stream):
    stream.seek(0)
    digest = hashlib.sha256()
    while True:
        data = stream.read(CHUNK_BYTES)
        if not data:
            break
        digest.update(data)
    stream.seek(0)
    return digest.hexdigest()


def _windows_handle(path, *, directory=False, create=False):
    import win32con
    import win32file
    flags = 0x00200000  # FILE_FLAG_OPEN_REPARSE_POINT (not exported by win32con)
    if directory:
        flags |= win32con.FILE_FLAG_BACKUP_SEMANTICS
    access = 0x0080 if directory else win32con.GENERIC_READ
    if create:
        access |= win32con.GENERIC_WRITE
    share = win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE
    if create:
        share |= win32con.FILE_SHARE_DELETE
    handle = win32file.CreateFile(str(path), access, share, None,
        win32con.CREATE_NEW if create else win32con.OPEN_EXISTING, flags, None)
    try:
        info = win32file.GetFileInformationByHandle(handle)
        attributes = info[0]
        if attributes & 0x0400 or bool(attributes & win32con.FILE_ATTRIBUTE_DIRECTORY) != directory:
            raise ValueError("Workspace paths cannot traverse reparse points")
        return handle
    except BaseException:
        handle.Close()
        raise


class SafeWorkspace:
    def __init__(self, root):
        self.path = Path(root).expanduser().resolve(strict=True)
        if not self.path.is_dir():
            raise ValueError("Workspace root must be an existing directory")
        self.identity = self.path.stat().st_dev, self.path.stat().st_ino
        self.fd = None
        self.pin = None
        if os.name == "nt":
            self.pin = _windows_handle(self.path, directory=True)
        else:
            self.fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def parent(self, relative, *, create=False):
        parts = relative_parts(relative)
        if (self.path.stat().st_dev, self.path.stat().st_ino) != self.identity:
            raise ValueError("Workspace root changed")
        return Parent(self, parts, create=create)

    def open_read(self, relative):
        with self.parent(relative) as parent:
            stream = parent.open(parent.name)
            try:
                signature(stream)
                return stream
            except BaseException:
                stream.close()
                raise

    def stage(self, relative, *, overwrite=False):
        return StagedFile(self.parent(relative, create=True), overwrite=overwrite)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        if self.pin is not None:
            self.pin.Close()
            self.pin = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Parent:
    def __init__(self, root, parts, *, create):
        self.root, self.parts, self.name = root, parts, parts[-1]
        self.path = root.path
        self.fd = None
        self.pins = []
        try:
            if os.name == "nt":
                for component in parts[:-1]:
                    self.path = self.path / component
                    if create:
                        try:
                            self.path.mkdir()
                        except FileExistsError:
                            pass
                    self.pins.append(_windows_handle(self.path, directory=True))
            else:
                self.fd = os.dup(root.fd)
                for component in parts[:-1]:
                    if create:
                        try:
                            os.mkdir(component, mode=0o700, dir_fd=self.fd)
                        except FileExistsError:
                            pass
                    next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.fd)
                    os.close(self.fd)
                    self.fd = next_fd
                    self.path = self.path / component
        except BaseException:
            self.close()
            raise

    def open(self, name, *, create=False):
        if os.name == "nt":
            import msvcrt
            handle = _windows_handle(self.path / name, create=create)
            try:
                fd = msvcrt.open_osfhandle(handle.Detach(), os.O_RDWR if create else os.O_RDONLY)
            except BaseException:
                handle.Close()
                raise
        else:
            flags = os.O_NOFOLLOW | (os.O_RDWR | os.O_CREAT | os.O_EXCL if create else os.O_RDONLY | os.O_NONBLOCK)
            fd = os.open(name, flags, 0o600, dir_fd=self.fd)
        return os.fdopen(fd, "w+b" if create else "rb")

    def info(self, name):
        return os.stat(self.path / name, follow_symlinks=False) if os.name == "nt" else os.stat(name, dir_fd=self.fd, follow_symlinks=False)

    def unlink(self, name):
        if os.name == "nt":
            os.unlink(self.path / name)
        else:
            os.unlink(name, dir_fd=self.fd)

    def current(self):
        with self.root.parent("/".join(self.parts)) as other:
            here = self.path.stat() if os.name == "nt" else os.fstat(self.fd)
            there = other.path.stat() if os.name == "nt" else os.fstat(other.fd)
            if (here.st_dev, here.st_ino) != (there.st_dev, there.st_ino):
                raise ValueError("Workspace parent changed during transfer")

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        for pin in reversed(self.pins):
            pin.Close()
        self.pins.clear()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class StagedFile:
    def __init__(self, parent, *, overwrite=False):
        self.parent, self.overwrite = parent, overwrite
        self.temporary = ".swcli-upload-" + uuid.uuid4().hex + ".tmp"
        self.stream = None
        self.published = False
        try:
            try:
                target = parent.info(parent.name)
            except FileNotFoundError:
                pass
            else:
                if not overwrite:
                    raise FileExistsError("Workspace destination already exists")
                if not stat.S_ISREG(target.st_mode) or getattr(target, "st_file_attributes", 0) & 1024:
                    raise ValueError("Workspace destination must be a regular file")
            self.stream = parent.open(self.temporary, create=True)
            self.identity = signature(self.stream)[:2]
        except BaseException:
            parent.close()
            raise

    def publish(self):
        self.parent.current()
        self.stream.flush()
        os.fsync(self.stream.fileno())
        current = self.parent.info(self.temporary)
        if (current.st_dev, current.st_ino) != self.identity:
            raise ValueError("Workspace temporary file changed")
        source, target = self.temporary, self.parent.name
        if os.name == "nt":
            source, target = self.parent.path / source, self.parent.path / target
            kwargs = {}
        else:
            kwargs = {"src_dir_fd": self.parent.fd, "dst_dir_fd": self.parent.fd}
        if self.overwrite:
            os.replace(source, target, **kwargs)
        else:
            os.link(source, target, follow_symlinks=False, **kwargs)
            self.published = True
            self.parent.unlink(self.temporary)
        self.published = True

    def close(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None
            if not self.published:
                try:
                    current = self.parent.info(self.temporary)
                    if (current.st_dev, current.st_ino) == self.identity:
                        self.parent.unlink(self.temporary)
                except FileNotFoundError:
                    pass
                finally:
                    self.parent.close()
            else:
                self.parent.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
