import os

import psutil


def tree_rss(pid: int | None = None) -> int:
    try:
        root = psutil.Process(pid or os.getpid())
        processes = [root, *root.children(recursive=True)]
    except psutil.Error:
        return 0
    total = 0
    for process in processes:
        try:
            total += process.memory_info().rss
        except psutil.Error:
            continue
    return total


def stop_tree(pid: int) -> None:
    try:
        root = psutil.Process(pid)
        processes = [*root.children(recursive=True), root]
    except psutil.Error:
        return
    for process in processes:
        try:
            process.terminate()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(processes, timeout=0.8)
    for process in alive:
        try:
            process.kill()
        except psutil.Error:
            pass
