"""CI units only: one retained, identity-verified native process handle."""
from datetime import datetime,timezone
import ntpath

EXPECTED_CI_IMAGE=r'C:\Program Files\SOLIDWORKS\SLDWORKS.exe'


def require(value,message):
    if not value:raise RuntimeError(message)


def process_identity(handle):
    import ctypes
    from ctypes import wintypes
    import win32process
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    query=kernel.QueryFullProcessImageNameW;query.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)];query.restype=wintypes.BOOL
    image=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(len(image))
    if not query(int(handle),0,image,ctypes.byref(size)):raise ctypes.WinError(ctypes.get_last_error())
    created=win32process.GetProcessTimes(handle)['CreationTime']
    return dict(pid=win32process.GetProcessId(handle),image=image.value,creation_utc=created.astimezone(timezone.utc).isoformat(),creation_timestamp=created.timestamp())


def validate_identity(identity,pid,launched,observed,expected_image):
    require(identity['pid']==pid,'native retained handle PID differs')
    require(ntpath.normcase(ntpath.normpath(identity['image']))==ntpath.normcase(ntpath.normpath(expected_image)),'native full image differs from this CI installation')
    require(launched<=identity['creation_timestamp']<=observed,'native creation time is outside this run startup window')


def capture(pid,launched,expected_image=EXPECTED_CI_IMAGE,*,terminate_right=True):
    import win32api
    import win32con
    # QUERY_LIMITED_INFORMATION + TERMINATE + SYNCHRONIZE, only this proven PID.
    handle=win32api.OpenProcess(win32con.SYNCHRONIZE|0x1000|(win32con.PROCESS_TERMINATE if terminate_right else 0),False,pid)
    try:
        identity=process_identity(handle);validate_identity(identity,pid,launched,datetime.now(timezone.utc).timestamp(),expected_image)
        return handle,identity
    except BaseException:handle.Close();raise


def exited(handle):
    import win32event
    return win32event.WaitForSingleObject(handle,0)==win32event.WAIT_OBJECT_0


def terminate(handle,identity):
    import win32api
    # Recheck the same retained handle, never reopen or search for a substitute PID.
    require(process_identity(handle)==identity,'native retained handle identity changed')
    win32api.TerminateProcess(handle,1)
