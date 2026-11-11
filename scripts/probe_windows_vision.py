"""Observe native worker exit handles inside an owned Windows onefile run."""
import argparse
import ctypes
import json
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path

import psutil

from ocready.core.memory import stop_tree
from scripts.packaged_environment import runtime_test_environment
from scripts.provenance import file_sha256, source_record

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--checksum", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This probe requires native Windows.")
    from ctypes import wintypes as W
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes, kernel.OpenProcess.restype = [W.DWORD, W.BOOL, W.DWORD], W.HANDLE
    kernel.GetExitCodeProcess.argtypes, kernel.GetExitCodeProcess.restype = [W.HANDLE, ctypes.POINTER(W.DWORD)], W.BOOL
    kernel.WaitForSingleObject.argtypes, kernel.WaitForSingleObject.restype = [W.HANDLE, W.DWORD], W.DWORD
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [W.HANDLE], W.BOOL
    binary = args.binary.resolve()
    digest = file_sha256(binary)
    if digest != args.checksum.read_text(encoding="utf-8").split()[0]:
        raise ValueError("The probe binary differs from its public checksum.")
    report = {"source": source_record(ROOT), "binary_sha256": digest, "platform": platform.platform(),
              "processor": platform.processor(), "processor_identifier": os.environ.get("PROCESSOR_IDENTIFIER", ""),
              "cpu_count": os.cpu_count(), "scope": "Reference public Studio onefile; owned-process exit diagnostics, not a RAM certification", "cases": []}
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            report["processor_name"] = winreg.QueryValueEx(key, "ProcessorNameString")[0]
    except OSError:
        report["processor_name"] = None
    with tempfile.TemporaryDirectory(prefix="ocready-native-probe-", ignore_cleanup_errors=True) as temporary:
        for name, backend, unicode in (("ascii-auto", "auto", False), ("arabic-auto", "auto", True),
                                       ("ascii-cpu", "cpu", False), ("arabic-cpu", "cpu", True)):
            work = Path(temporary) / name
            env = runtime_test_environment(work / ("مؤقت" if unicode else "temp"))
            output = work / "result.json"
            command = [str(binary), str(ROOT / "assets/sample-bilingual.png"), "--json", "--output", str(output),
                       "--method", "vision", "--pack-id", "smolvlm-256m-q4", "--backend", backend]
            started = time.monotonic()
            handles = {}
            peaks = {}
            record = {"case": name, "backend": backend, "native_workers": [], "timed_out": False}
            with tempfile.TemporaryFile() as log:
                child = subprocess.Popen(command, cwd=work, env=env, stdout=log, stderr=log)
                try:
                    while child.poll() is None:
                        if time.monotonic() - started > 800:
                            record["timed_out"] = True
                            break
                        try:
                            descendants = psutil.Process(child.pid).children(recursive=True)
                        except psutil.Error:
                            descendants = []
                        for process in descendants:
                            try:
                                if process.name().lower() != "llama-mtmd-cli.exe":
                                    continue
                                if process.pid not in handles:
                                    # Query/synchronize only; no process outside this
                                    # launched root's own descendant tree is opened.
                                    created = process.create_time()
                                    handle = kernel.OpenProcess(0x1000 | 0x100000, False, process.pid)
                                    if handle:
                                        try:
                                            if not process.is_running() or psutil.Process(process.pid).create_time() != created:
                                                continue
                                            handles[process.pid] = handle
                                            peaks[process.pid] = {"pid": process.pid, "created": created, "command": [], "peak_rss": 0, "peak_private": 0}
                                            peaks[process.pid]["command"] = process.cmdline()
                                        finally:
                                            if handles.get(process.pid) != handle:
                                                kernel.CloseHandle(handle)
                                if process.pid in peaks:
                                    memory = process.memory_info()
                                    peaks[process.pid]["peak_rss"] = max(peaks[process.pid]["peak_rss"], memory.rss)
                                    peaks[process.pid]["peak_private"] = max(peaks[process.pid]["peak_private"], getattr(memory, "private", 0))
                            except psutil.Error:
                                continue
                        time.sleep(.02)
                finally:
                    if child.poll() is None:
                        stop_tree(child.pid)
                    child.wait()
                    for pid, handle in handles.items():
                        try:
                            # An unsignaled handle still names this original own
                            # child, so its PID cannot have been reused yet.
                            if kernel.WaitForSingleObject(handle, 0) == 258:
                                stop_tree(pid)
                            code = W.DWORD()
                            if kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                                peaks[pid].update(exit_code=code.value, exit_hex=f"0x{code.value:08X}")
                            record["native_workers"].append(peaks[pid])
                        finally:
                            kernel.CloseHandle(handle)
                log.seek(0, 2)
                log.seek(max(0, log.tell() - 16000))
                record.update(exit_code=child.returncode, elapsed_seconds=round(time.monotonic() - started, 3),
                              log_tail=log.read(16000).decode("utf-8", errors="replace"))
            if output.is_file():
                result = json.loads(output.read_text(encoding="utf-8"))
                record.update(engine=result.get("engine"), backend_used=result.get("backend"),
                              english_sample_verified="screenshots" in result.get("text", ""))
            report["cases"].append(record)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(record, ensure_ascii=True), flush=True)
    if not all(row["exit_code"] == 0 and row.get("english_sample_verified")
               and any("-m" in worker["command"] and worker.get("exit_code") == 0 for worker in row["native_workers"])
               for row in report["cases"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
