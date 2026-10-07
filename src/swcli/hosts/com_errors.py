"""Portable HRESULT classification shared by lifecycle and live-object guards."""

from typing import Optional

TRANSIENT_COM_HRESULTS = {
    0x80010001,  # RPC_E_CALL_REJECTED
    0x8001010A,  # RPC_E_SERVERCALL_RETRYLATER
    0x8001010B,  # RPC_E_SERVERCALL_REJECTED
}
DISCONNECTED_COM_HRESULTS = {
    0x800401FD,  # CO_E_OBJNOTCONNECTED
    0x80010108,  # RPC_E_DISCONNECTED
    0x800706BA,  # HRESULT_FROM_WIN32(RPC_S_SERVER_UNAVAILABLE)
}


def com_hresult(exc: BaseException) -> Optional[int]:
    """Normalize signed pywin32 and compatible exception HRESULTs."""
    value = getattr(exc, "hresult", None)
    if not isinstance(value, int) and exc.args and isinstance(exc.args[0], int):
        value = exc.args[0]
    if not isinstance(value, int):
        return None
    return value & 0xFFFFFFFF
