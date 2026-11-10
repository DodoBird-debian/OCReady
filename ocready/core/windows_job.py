"""Windows worker Job Objects. Imported only on Windows."""
import ctypes
from ctypes import wintypes

import psutil


class BasicLimit(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]


class IOCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                    "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class ExtendedLimit(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", BasicLimit), ("IoInfo", IOCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


def kernel_api():
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateJobObjectW.argtypes, api.CreateJobObjectW.restype = [ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE
    api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    api.SetInformationJobObject.restype = wintypes.BOOL
    api.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    api.QueryInformationJobObject.restype = wintypes.BOOL
    api.AssignProcessToJobObject.argtypes, api.AssignProcessToJobObject.restype = [wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL
    api.OpenProcess.argtypes, api.OpenProcess.restype = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE
    api.OpenThread.argtypes, api.OpenThread.restype = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE
    api.ResumeThread.argtypes, api.ResumeThread.restype = [wintypes.HANDLE], wintypes.DWORD
    api.CloseHandle.argtypes, api.CloseHandle.restype = [wintypes.HANDLE], wintypes.BOOL
    return api


class WindowsJob:
    def __init__(self, limit: int):
        self.api = kernel_api()
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = ExtendedLimit()
        info.BasicLimitInformation.LimitFlags = 0x00000200 | 0x00002000  # JOB_MEMORY + KILL_ON_JOB_CLOSE
        info.JobMemoryLimit = limit
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            error = ctypes.get_last_error()
            self.close()
            raise ctypes.WinError(error)

    def assign(self, pid: int) -> None:
        process = self.api.OpenProcess(0x0100 | 0x0001 | 0x1000, False, pid)
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.api.AssignProcessToJobObject(self.handle, process):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.api.CloseHandle(process)

    def peak(self) -> int:
        info = ExtendedLimit()
        if self.handle and self.api.QueryInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info), None):
            return info.PeakJobMemoryUsed
        return 0

    def close(self) -> None:
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def resume_process(pid: int) -> None:
    api = kernel_api()
    resumed = False
    for thread in psutil.Process(pid).threads():
        handle = api.OpenThread(0x0002, False, thread.id)
        if not handle:
            continue
        try:
            resumed |= api.ResumeThread(handle) != 0xFFFFFFFF
        finally:
            api.CloseHandle(handle)
    if not resumed:
        raise OSError("Could not resume the suspended OCR worker.")
