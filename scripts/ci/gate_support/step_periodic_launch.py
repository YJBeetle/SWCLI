"""Verify the direct, isolated Python worker before importing the native driver."""
import os
from pathlib import Path
import sys


def worker_python():
    # Matches the Windows multiprocessing spawn strategy validated by 34baf8e.
    env = os.environ.copy()
    env.pop('__PYVENV_LAUNCHER__', None)
    executable = sys.executable
    if sys.platform == 'win32':
        executable = sys._base_executable
        if os.path.normcase(executable) != os.path.normcase(sys.executable):
            env['__PYVENV_LAUNCHER__'] = sys.executable
    if not os.path.isabs(executable) or not Path(executable).is_file():
        raise RuntimeError('absolute worker Python executable unavailable')
    return executable, env


def windows_process_image():
    import ctypes
    from ctypes import wintypes
    get_name = ctypes.WinDLL('kernel32', use_last_error=True).GetModuleFileNameW
    get_name.argtypes = (wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD)
    get_name.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_name(None, buffer, len(buffer))
    if not 0 < length < len(buffer):
        raise OSError('Windows failed to report the worker process image')
    return buffer.value


def verify_worker_identity(expected, stream):
    parent = os.getppid()
    spawned = os.getpid()
    claimed = expected.get('parent_pid')
    if type(claimed) is not int or claimed <= 0 or claimed != parent:
        raise RuntimeError(f'worker parent differs: actual {parent}, expected {claimed}')
    if not sys.flags.isolated or not os.path.samefile(sys.prefix, expected['parent_prefix']):
        raise RuntimeError('worker did not retain the supervisor Python environment in isolated mode')
    if stream is None or stream.readline(32) != f'{spawned}\n'.encode('ascii'):
        raise RuntimeError('supervisor launch pipe did not identify this worker PID')
    image = windows_process_image() if sys.platform == 'win32' else None
    if image is not None and not os.path.samefile(image, sys._base_executable):
        raise RuntimeError('worker image is not its base Python executable')
    receipt = dict(parent_pid=parent, worker_pid=spawned, spawned_pid=spawned,
                   prefix=sys.prefix, isolated=True, executable=sys.executable,
                   base_executable=sys._base_executable, process_image=image)
    verify_worker_receipt(receipt, expected, spawned)
    return receipt


def verify_worker_receipt(receipt, expected, spawned_pid):
    for field, value in (('parent_pid', expected['parent_pid']),
                         ('worker_pid', spawned_pid), ('spawned_pid', spawned_pid)):
        if type(receipt[field]) is not int or receipt[field] != value:
            raise RuntimeError(f'worker supervision receipt has mismatched {field}')
    if receipt['isolated'] is not True or not os.path.samefile(receipt['prefix'], expected['parent_prefix']):
        raise RuntimeError('worker supervision receipt has mismatched Python environment')
    image = receipt['process_image'] if sys.platform == 'win32' else receipt['executable']
    if not image or not os.path.samefile(image, expected['launch_executable']):
        raise RuntimeError('worker supervision receipt does not match the launched process image')
