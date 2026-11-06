"""Select the same Python installation without allocating a Windows console."""

from pathlib import Path
import sys


def background_python():
    executable = Path(sys.executable)
    if sys.platform != "win32" or executable.name.lower() != "python.exe":
        return sys.executable
    windowed = executable.with_name("pythonw.exe")
    if not windowed.is_file():
        raise FileNotFoundError("Background startup requires pythonw.exe beside " + str(executable))
    return str(windowed)
