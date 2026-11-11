"""Small hardware context for owned native tests, without user/machine names."""
import os
import platform
import sys
from pathlib import Path

import psutil


def host_identity() -> dict:
    memory = psutil.virtual_memory()
    record = {"platform": platform.platform(), "processor": platform.processor(),
              "logical_cpu_count": os.cpu_count(), "physical_cpu_count": psutil.cpu_count(logical=False),
              "processor_name": None, "memory_total_bytes": memory.total,
              "memory_available_bytes_at_start": memory.available}
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                record["processor_name"] = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    elif sys.platform == "linux":
        try:
            with Path("/proc/cpuinfo").open(encoding="utf-8", errors="replace") as stream:
                cpu = stream.read(256_000)
            for line in cpu.splitlines():
                name, separator, value = line.partition(":")
                if separator and name.strip() in {"model name", "Hardware"}:
                    record["processor_name"] = value.strip()
                    break
        except OSError:
            pass
    return record
