"""Retain real Windows classical OCR failures across ASCII/Arabic worker paths."""
import argparse
import ctypes
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ocready.core.memory import stop_tree
from ocready.core.paths import runtime_root
from scripts.packaged_environment import runtime_test_environment
from scripts.provenance import source_record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("This probe requires native Windows.")
    root = Path(__file__).resolve().parents[1]
    runtime = runtime_root()
    results = []
    with tempfile.TemporaryDirectory(prefix="ocready-path-probe-") as temporary:
        work = Path(temporary)
        unicode_runtime = work / "محرك-العربية"
        shutil.copytree(runtime / "bin", unicode_runtime / "bin")
        shutil.copytree(runtime / "tessdata/fast", unicode_runtime / "tessdata/fast")
        for name, engine, arabic_temp in (("ascii", runtime, False), ("arabic-temp", runtime, True),
                                           ("arabic-runtime", unicode_runtime, False), ("arabic-both", unicode_runtime, True)):
            temp = work / name / ("مؤقت" if arabic_temp else "temp")
            env = runtime_test_environment(temp, isolated=False)
            env.update(OCREADY_RUNTIME=str(engine), PYTHONIOENCODING="utf-8")
            image = temp / ("لقطة.png" if arabic_temp else "input.png")
            shutil.copyfile(root / "assets/sample-bilingual.png", image)
            output = temp / "result.json"
            command = [sys.executable, "-m", "ocready", str(image), "--edition", "pocket", "--method",
                       "tesseract-fast", "--layout", "sparse", "--json", "--output", str(output)]
            try:
                child = subprocess.Popen(command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    stdout, stderr = child.communicate(timeout=150)
                    process = subprocess.CompletedProcess(command, child.returncode, stdout, stderr)
                finally:
                    if child.poll() is None:
                        stop_tree(child.pid)
                    child.wait()
                    child.stdout.close()
                    child.stderr.close()
                record = {"case": name, "exit_code": process.returncode,
                          "stdout": process.stdout[-16000:].decode("utf-8", errors="replace"),
                          "stderr": process.stderr[-16000:].decode("utf-8", errors="replace")}
                if output.is_file():
                    result = json.loads(output.read_text(encoding="utf-8"))
                    record["engine"] = result.get("engine")
                    record["bilingual_text_verified"] = "مرحبا بالعالم" in result.get("text", "") and "screenshots" in result.get("text", "")
            except subprocess.TimeoutExpired as exc:
                record = {"case": name, "error": str(exc), "timed_out": True,
                          "stdout": (exc.output or b"")[-16000:].decode("utf-8", errors="replace"),
                          "stderr": (exc.stderr or b"")[-16000:].decode("utf-8", errors="replace")}
            results.append(record)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps({"source": source_record(root), "platform": sys.platform,
                "windows_ansi_code_page": ctypes.windll.kernel32.GetACP(),
                "probe": "source-worker-paths-v1", "cases": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(record, ensure_ascii=True), flush=True)
    if not all(r.get("exit_code") == 0 and r.get("bilingual_text_verified") for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
