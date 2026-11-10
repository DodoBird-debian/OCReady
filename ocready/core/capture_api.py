"""Small Windows capture primitives, isolated from document/UI state."""
import ctypes
import os
from functools import lru_cache

import psutil


@lru_cache(maxsize=1)
def _user32():
    api = ctypes.WinDLL("user32", use_last_error=True)
    api.GetClipboardSequenceNumber.argtypes = []
    api.GetClipboardSequenceNumber.restype = ctypes.c_uint32
    api.GetForegroundWindow.argtypes = []
    api.GetForegroundWindow.restype = ctypes.c_void_p
    api.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    api.GetWindowThreadProcessId.restype = ctypes.c_uint32
    return api


def clipboard_sequence() -> int:
    return int(_user32().GetClipboardSequenceNumber()) if os.name == "nt" else 0


def capture_host_visible() -> bool | None:
    """Best-effort cancellation detection; unknown hosts keep the timeout path."""
    if os.name != "nt":
        return None
    api = _user32()
    window = api.GetForegroundWindow()
    if not window:
        return None
    pid = ctypes.c_uint32()
    api.GetWindowThreadProcessId(window, ctypes.byref(pid))
    if not pid.value:
        return None
    try:
        name = psutil.Process(pid.value).name().casefold()
    except psutil.Error:
        return None
    return name in {"snippingtool.exe", "screenclippinghost.exe", "screenclipping.exe"}
