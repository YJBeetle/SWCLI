"""Portable COM-shaped file fixtures; real COM binding is verified on Windows."""
from contextlib import contextmanager
from types import ModuleType
from unittest import mock

from swcli.hosts.windows_save_as import save_as3


class Variant:
    def __init__(self, variant_type, value):
        self.varianttype = variant_type
        self.value = value


@contextmanager
def com_arguments():
    pythoncom = ModuleType("pythoncom")
    pythoncom.VT_DISPATCH, pythoncom.VT_BYREF, pythoncom.VT_I4 = 9, 0x4000, 3
    client = ModuleType("win32com.client")
    client.VARIANT = Variant
    dynamic = ModuleType("win32com.client.dynamic")
    dynamic.DumbDispatch = lambda extension: extension
    with mock.patch.dict("sys.modules", {
        "pythoncom": pythoncom, "win32com.client": client,
        "win32com.client.dynamic": dynamic,
    }):
        yield


def save_as_fixture(document, output, *, receipt, stage="save-as"):
    # Existing file/state fixture methods live on the fake document. Expose the
    # seven-argument method on its extension for the production adapter call.
    extension = document.Extension
    extension.SaveAs3 = document.SaveAs3
    extension._FlagAsMethod = mock.Mock()
    with com_arguments():
        return save_as3(document, output, receipt=receipt, stage=stage)
