"""OS worker allocation limits complement the app's whole-tree RSS guard.

Linux workers enter their own systemd scope before exec. Windows workers are
assigned to a Job Object before their initial thread runs. These OS counters
are not identical to RSS, so the existing RSS monitor remains authoritative
for the selected application's observed working-set budget.
"""
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from ocready.core.paths import runtime_root
from ocready.core.types import BudgetExceeded

RESERVE = 16_000_000


def _control_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        env.pop(key, None)
    return env


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", "--no-ask-password", *args],
                          stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=2, env=_control_env())


@dataclass
class WorkerLimit:
    mode: str = "rss-monitor"
    limit_bytes: int = 0
    peak_bytes: int = 0
    detail: str = "No OS worker allocation limit is available. Whole-tree RSS monitoring remains active."
    unit: str = ""
    group: Path | None = None
    windows_job: object | None = None
    oom: bool = False

    def sample(self) -> None:
        if self.group:
            try:
                self.peak_bytes = max(self.peak_bytes, int((self.group / "memory.peak").read_text()))
                events = dict(line.split() for line in (self.group / "memory.events").read_text().splitlines())
                self.oom |= int(events.get("oom_kill", 0)) > 0
            except (OSError, ValueError):
                pass
        if self.windows_job:
            self.peak_bytes = max(self.peak_bytes, self.windows_job.peak())

    def completed(self) -> None:
        self.sample()
        if self.unit:
            try:
                result = _systemctl("show", self.unit, "--property=Result", "--value")
                self.oom |= result.stdout.strip() == "oom-kill"
            except (OSError, subprocess.SubprocessError):
                pass

    def close(self) -> None:
        if self.windows_job:
            self.windows_job.close()
            self.windows_job = None
        if self.unit:
            try:
                _systemctl("stop", self.unit)
                _systemctl("reset-failed", self.unit)
            except (OSError, subprocess.SubprocessError):
                pass
            self.unit = ""


def linux_gate() -> Path | None:
    gate = runtime_root() / "bin" / "ocready-exec-gate"
    session = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    bus_exists = bool(runtime and (Path(runtime) / "bus").is_socket())
    if gate.is_file() and os.access(gate, os.X_OK) and shutil.which("busctl") and shutil.which("systemctl") and (session or bus_exists):
        return gate
    return None


def _linux_limit(pid: int, allowance: int) -> WorkerLimit:
    unit = "ocready-worker-" + uuid.uuid4().hex + ".scope"
    guard = WorkerLimit(unit=unit)
    command = ["busctl", "--user", "--timeout=2", "--quiet", "call", "org.freedesktop.systemd1",
               "/org/freedesktop/systemd1", "org.freedesktop.systemd1.Manager", "StartTransientUnit",
               "ssa(sv)a(sa(sv))", unit, "fail", "5",
               "Description", "s", "OCReady OCR worker", "PIDs", "au", "1", str(pid),
               "MemoryMax", "t", str(allowance), "MemorySwapMax", "t", "0",
               "CollectMode", "s", "inactive", "0"]
    try:
        reply = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                               timeout=3, env=_control_env())
        if reply.returncode:
            guard.detail = "User cgroup scope unavailable: " + reply.stderr.decode("utf-8", errors="replace").strip()[:300]
            return guard
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            result = _systemctl("show", unit, "--property=ControlGroup", "--value")
            relative = result.stdout.strip()
            if relative:
                group = (Path("/sys/fs/cgroup") / relative.lstrip("/")).resolve()
                if not group.is_relative_to(Path("/sys/fs/cgroup")):
                    break
                if str(pid) in (group / "cgroup.procs").read_text().splitlines():
                    limit = int((group / "memory.max").read_text())
                    if limit == allowance:
                        try:
                            (group / "memory.oom.group").write_text("1")
                        except OSError:
                            pass
                        guard.mode, guard.limit_bytes, guard.group = "cgroup-v2", allowance, group
                        guard.detail = "Worker cgroup memory.max + zero swap; whole-tree RSS monitoring also active."
                        return guard
            time.sleep(.01)
    except (OSError, ValueError, subprocess.SubprocessError):
        guard.detail = "User cgroup scope could not be established; RSS monitoring is active."
    return guard


def start_worker(command: list[str], *, budget: int, resident: int, stdout, stderr,
                 env: dict[str, str] | None, cwd: Path | None) -> tuple[subprocess.Popen, WorkerLimit]:
    page_size = os.sysconf("SC_PAGE_SIZE") if os.name == "posix" else 4096
    allowance = (budget - resident - RESERVE) // page_size * page_size
    if allowance < 16_000_000:
        raise BudgetExceeded("There is too little memory headroom to start OCR. Try a smaller crop or a larger edition.")
    guard = WorkerLimit()
    gate = linux_gate() if os.name == "posix" else None
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW | 0x00000004  # CREATE_SUSPENDED
    child = subprocess.Popen([str(gate), *command] if gate else command,
                             stdin=subprocess.PIPE if gate else subprocess.DEVNULL,
                             stdout=stdout, stderr=stderr, env=env, cwd=cwd,
                             creationflags=creationflags)
    try:
        if gate:
            guard = _linux_limit(child.pid, allowance)
            child.stdin.write(b"x")
            child.stdin.close()
        elif os.name == "nt":
            from ocready.core.windows_job import WindowsJob, resume_process
            try:
                job = WindowsJob(allowance)
                try:
                    job.assign(child.pid)
                except OSError:
                    job.close()
                    raise
                guard = WorkerLimit(mode="windows-job", limit_bytes=allowance,
                                    detail="Worker Job Object committed-memory limit; whole-tree RSS monitoring also active.",
                                    windows_job=job)
            except OSError:
                guard.detail = "A Windows Job Object was unavailable; RSS monitoring is active."
            resume_process(child.pid)
        return child, guard
    except BaseException:
        guard.close()
        child.kill()
        child.wait()
        if child.stdin:
            child.stdin.close()
        raise
