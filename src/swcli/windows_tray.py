"""Optional Windows notification icon. All host actions use the daemon protocol.

The UI owns no COM object or SW process. Destroying its window only removes the
icon. Windows imports stay inside the backend so Wine/off and POSIX clients do
not acquire GUI dependencies.
"""

import ctypes
import json
from importlib.resources import as_file, files
import os
import queue
import sys
import threading
import uuid

MODES = ("auto", "on", "off")


def validate_mode(mode):
    if mode not in MODES:
        raise ValueError("tray must be auto, on or off")
    return mode


def is_wine():
    if sys.platform != "win32":
        return False
    try:
        return getattr(ctypes.WinDLL("ntdll"), "wine_get_version", None) is not None
    except (AttributeError, OSError):
        return False


def tray_enabled(mode, host_platform="windows"):
    validate_mode(mode)
    if mode == "off":
        return False
    if mode == "on":
        if sys.platform != "win32":
            raise RuntimeError("the tray requires a Windows execution runtime")
        return True
    return sys.platform == "win32" and not host_platform.endswith("-wine") and not is_wine()


def diagnostic(error):
    print(json.dumps({"event": "tray.unavailable", "code": type(error).__name__,
                      "message": str(error)}, ensure_ascii=True), file=sys.stderr, flush=True)


def status_text(response, endpoint):
    if not response.get("success"):
        error = response.get("error") or {}
        return "状态查询失败\n" + str(error.get("message", error.get("code", "unknown")))
    state = response.get("result") or {}
    def yes_no(value):
        return {True: "是", False: "否", None: "未知"}.get(value, "未知")
    names = {"ready": "就绪", "starting": "启动中", "degraded": "连接异常",
             "stopped": "已停止", "unknown": "未知"}
    owned = state.get("daemon_sw_owned")
    owner = "daemon 专属" if owned is True else "附加的用户宿主" if owned is False else "未知"
    return "\n".join(("Endpoint: " + endpoint, "Daemon PID: " + str(os.getpid()),
                       "Daemon: " + names.get(state.get("daemon_state"), "未知"),
                       "SOLIDWORKS PID: " + str(state.get("daemon_sw_pid") or "未知"),
                       "宿主归属: " + owner,
                       "SW 窗口可见: " + yes_no(state.get("daemon_sw_visible")),
                       "用户 SW 正在运行: " + yes_no(state.get("user_sw_running"))))


class TrayController:
    def __init__(self, endpoint, *, view_factory=None, manager_factory=None):
        from .daemon_manager import DaemonManager
        self.endpoint = endpoint
        self._manager = (manager_factory or DaemonManager)(endpoint=endpoint)
        self._view_factory = view_factory or Win32TrayView
        self._view = None
        self._created = threading.Event()
        self._closed = threading.Event()
        self._ready = threading.Event()
        self._busy = threading.Lock()
        self._startup_error = None
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, name="swcli-tray", daemon=True)
        self._thread.start()
        if not self._created.wait(5):
            self.close()
            raise RuntimeError("notification icon did not initialize within five seconds")
        if self._startup_error is not None:
            raise self._startup_error
        return self

    def _run(self):
        try:
            self._view = self._view_factory(self)
            self._view.run(self._created, self._closed)
        except Exception as exc:
            self._startup_error = exc
            if self._created.is_set():
                diagnostic(exc)
        finally:
            self._closed.set()
            self._created.set()

    def ready(self):
        self._ready.set()
        if self._view is not None:
            self._view.post("ready", None)

    def close(self):
        # This never calls manager.stop(), closes documents or terminates SW.
        self._closed.set()
        if self._view is not None:
            self._view.close()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)

    def request(self, action):
        if action not in ("status", "stop"):
            raise ValueError("unknown tray action")
        if not self._ready.is_set() or self._closed.is_set() or not self._busy.acquire(False):
            return False
        def perform():
            try:
                # Exactly one normal protocol request. Refusal/timeout is not retried.
                result = self._manager.status() if action == "status" else self._manager.stop()
            except Exception as exc:
                result = {"success": False, "error": {"code": type(exc).__name__, "message": str(exc)},
                          "outcome_unknown": action == "stop"}
            finally:
                self._busy.release()
            if not self._closed.is_set():
                self._view.post(action, result)
        try:
            threading.Thread(target=perform, name="swcli-tray-request", daemon=True).start()
        except BaseException:
            self._busy.release()
            raise
        return True


def start_tray(mode, *, endpoint, host_platform="windows"):
    if not tray_enabled(mode, host_platform):
        return None
    try:
        return TrayController(endpoint).start()
    except Exception as exc:
        if mode == "on":
            raise RuntimeError("requested Windows tray is unavailable: " + str(exc)) from exc
        diagnostic(exc)
        return None


class Win32TrayView:
    """One window/message pump on its own thread; native calls stay on that thread."""
    CALLBACK = 0x8001
    UPDATE = 0x8002
    STATUS, STOP, HIDE = 1001, 1002, 1003

    def __init__(self, controller):
        self.controller = controller
        self.hwnd = None
        self._messages = queue.Queue()
        self._icon_added = False
        self._tip = "SWCLI · 启动中"

    def post(self, action, value):
        self._messages.put((action, value))
        if self.hwnd is not None:
            try:
                self.gui.PostMessage(self.hwnd, self.UPDATE, 0, 0)
            except Exception:
                if not self.controller._closed.is_set():
                    raise

    def close(self):
        if self.hwnd is not None:
            try:
                self.gui.PostMessage(self.hwnd, 0x10, 0, 0)  # WM_CLOSE
            except Exception:
                if not self.controller._closed.is_set():
                    raise

    def _icon(self, operation):
        flags = self.gui.NIF_ICON | self.gui.NIF_MESSAGE | self.gui.NIF_TIP | 0x80  # NIF_SHOWTIP
        value = self.gui.Shell_NotifyIcon(operation, (self.hwnd, 1, flags, self.CALLBACK, self.icon, self._tip))
        if value is False:
            raise OSError("Windows notification area rejected the icon")
        if operation == self.gui.NIM_ADD:
            self._icon_added = True
            # NOTIFYICONDATA's timeout/version union is tuple item 7.
            self.gui.Shell_NotifyIcon(4, (self.hwnd, 1, 0, 0, 0, "", "", 4))

    def _menu(self):
        g, c = self.gui, self.con
        menu = g.CreatePopupMenu()
        try:
            g.AppendMenu(menu, c.MF_STRING | c.MF_GRAYED, 0, self._tip)
            g.AppendMenu(menu, c.MF_SEPARATOR, 0, "")
            disabled = c.MF_GRAYED if not self.controller._ready.is_set() or self.controller._busy.locked() else 0
            g.AppendMenu(menu, c.MF_STRING | disabled, self.STATUS, "查看状态")
            g.AppendMenu(menu, c.MF_STRING | disabled, self.STOP, "停止 daemon…")
            g.AppendMenu(menu, c.MF_SEPARATOR, 0, "")
            g.AppendMenu(menu, c.MF_STRING, self.HIDE, "隐藏图标（保持运行）")
            x, y = g.GetCursorPos()
            g.SetForegroundWindow(self.hwnd)
            selected = g.TrackPopupMenu(menu, c.TPM_LEFTALIGN | c.TPM_RIGHTBUTTON | c.TPM_RETURNCMD,
                                       x, y, 0, self.hwnd, None)
            if selected == self.STATUS:
                self.controller.request("status")
            elif selected == self.STOP:
                answer = g.MessageBox(self.hwnd,
                    "停止将影响连接到此 daemon 的所有客户端。\n专属 SW 中有打开的文档时会拒绝停止；附加的用户 SW 会保留。\n\n现在停止 daemon？",
                    "SWCLI", c.MB_YESNO | c.MB_ICONWARNING | c.MB_DEFBUTTON2)
                if answer == c.IDYES:
                    self.controller.request("stop")
            elif selected == self.HIDE:
                g.DestroyWindow(self.hwnd)
        finally:
            g.DestroyMenu(menu)
            if self.hwnd is not None:
                g.PostMessage(self.hwnd, c.WM_NULL, 0, 0)

    def _update(self, *_):
        while True:
            try:
                action, value = self._messages.get_nowait()
            except queue.Empty:
                return 0
            if action == "ready":
                self._tip = "SWCLI · 正在运行 · " + self.controller.endpoint
                self._icon(self.gui.NIM_MODIFY)
            elif action == "status":
                self.gui.MessageBox(self.hwnd, status_text(value, self.controller.endpoint), "SWCLI 状态", self.con.MB_OK)
            elif action == "stop" and not value.get("success"):
                error = value.get("error") or {}
                message = str(error.get("code", "ShutdownFailed")) + ": " + str(error.get("message", "停止未完成"))
                if value.get("outcome_unknown"):
                    message += "\n结果未知；请先查询状态，不要重复停止。"
                self.gui.MessageBox(self.hwnd, message, "SWCLI 停止结果", self.con.MB_OK | self.con.MB_ICONWARNING)

    def _notify(self, hwnd, message, wparam, lparam):
        event = lparam & 0xffff
        if event in (self.con.WM_RBUTTONUP, self.con.WM_CONTEXTMENU):
            self._menu()
        elif event in (self.con.WM_LBUTTONUP, 0x400, 0x401):  # NIN_SELECT / NIN_KEYSELECT
            self.controller.request("status")
        return 0

    def _destroy(self, *_):
        self.controller._closed.set()
        if self._icon_added:
            try:
                self.gui.Shell_NotifyIcon(self.gui.NIM_DELETE, (self.hwnd, 1))
            except Exception as exc:
                diagnostic(exc)
            finally:
                self._icon_added = False
        self.hwnd = None
        self.gui.PostQuitMessage(0)
        return 0

    def run(self, created, closed):
        import win32api
        import win32con
        import win32gui
        self.gui, self.con = win32gui, win32con
        instance = win32api.GetModuleHandle(None)
        name = "SWCLI-Tray-" + uuid.uuid4().hex
        taskbar_created = win32gui.RegisterWindowMessage("TaskbarCreated")
        window_class = win32gui.WNDCLASS()
        window_class.hInstance = instance
        window_class.lpszClassName = name
        window_class.lpfnWndProc = {
            win32con.WM_DESTROY: self._destroy,
            win32con.WM_CLOSE: lambda hwnd, *_: win32gui.DestroyWindow(hwnd) or 0,
            self.CALLBACK: self._notify,
            self.UPDATE: self._update,
            taskbar_created: lambda *_: self._icon(win32gui.NIM_ADD) or 0,
        }
        win32gui.RegisterClass(window_class)
        try:
            self.hwnd = win32gui.CreateWindow(name, "SWCLI", 0, 0, 0, 0, 0, 0, 0, instance, None)
            icon_resource = files("swcli").joinpath("assets").joinpath("swcli.ico")
            with as_file(icon_resource) as icon_path:
                self.icon = win32gui.LoadImage(None, str(icon_path), win32con.IMAGE_ICON,
                    win32api.GetSystemMetrics(win32con.SM_CXSMICON),
                    win32api.GetSystemMetrics(win32con.SM_CYSMICON), win32con.LR_LOADFROMFILE)
            if closed.is_set():
                return
            self._icon(win32gui.NIM_ADD)
            created.set()
            win32gui.PumpMessages()
        finally:
            if self.hwnd is not None:
                win32gui.DestroyWindow(self.hwnd)
            if getattr(self, "icon", None) is not None:
                win32gui.DestroyIcon(self.icon)
                self.icon = None
            win32gui.UnregisterClass(name, instance)
