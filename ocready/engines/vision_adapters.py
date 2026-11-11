"""Explicit, offline runtime adapters; pack data never names importable modules."""
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from ocready.core.types import OCRError

if TYPE_CHECKING:
    from ocready.core.models import ModelPack


@dataclass(frozen=True)
class VisionRead:
    text: str
    backend: str
    note: str = ""


class VisionAdapter(Protocol):
    id: str
    name: str

    def validate_model(self, pack: "ModelPack") -> None: ...
    def command(self, pack: "ModelPack", image: Path, cuda: bool) -> list[str]: ...
    def probe_command(self, runner: str) -> list[str]: ...
    def probe_cuda(self, stdout: str, stderr: str) -> bool: ...
    def decode(self, stdout: str, image: Path, cuda: bool) -> VisionRead: ...
    def environment(self, runner: str) -> dict[str, str]: ...


def local_environment(runner: str) -> dict[str, str]:
    env = os.environ.copy()
    directory = str(Path(runner).expanduser().resolve().parent)
    if os.name == "nt":
        env["PATH"] = directory + os.pathsep + env.get("PATH", "")
    else:
        env["LD_LIBRARY_PATH"] = directory + os.pathsep + str(Path(directory).parent / "lib")
    return env


def clean_llama_output(output: str) -> str:
    output = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output).strip()
    for token in ("<|im_end|>", "<|endoftext|>", "<|eot_id|>"):
        output = output.removesuffix(token).rstrip()
    return output


class LlamaCppAdapter:
    id = "llama.cpp"
    name = "llama.cpp · GGUF models"

    def validate_model(self, pack: "ModelPack") -> None:
        if not pack.projector:
            raise OCRError("llama.cpp vision models require the matching GGUF vision projector.")
        for name, value in (("model", pack.model), ("vision projector", pack.projector)):
            with Path(value).expanduser().open("rb") as stream:
                if stream.read(4) != b"GGUF":
                    raise OCRError(f"The {name} is not a GGUF file.")

    def command(self, pack: "ModelPack", image: Path, cuda: bool) -> list[str]:
        runner = (pack.cuda_runner or pack.runner) if cuda else pack.runner
        args = [str(Path(runner).expanduser()), "-m", str(Path(pack.model).expanduser()),
                "--mmproj", str(Path(pack.projector).expanduser()), "--image", str(image.resolve()),
                "-p", pack.prompt, "-n", str(pack.tokens), "--temp", "0", "--seed", "1",
                "-c", "4096", "-b", "256", "-ub", "128", "-t", str(min(8, os.cpu_count() or 2)),
                "--image-max-tokens", "1024", "--no-warmup", "--log-colors", "off", "-ngl", "99" if cuda else "0"]
        if not cuda:
            args.append("--no-mmproj-offload")
        return args

    def probe_command(self, runner: str) -> list[str]:
        return [runner, "--list-devices"]

    def probe_cuda(self, stdout: str, stderr: str) -> bool:
        return bool(re.search(r"CUDA\d|CUDA\s*:", stdout + stderr, re.IGNORECASE))

    def decode(self, stdout: str, image: Path, cuda: bool) -> VisionRead:
        return VisionRead(clean_llama_output(stdout), "CUDA" if cuda else "CPU")

    environment = staticmethod(local_environment)


def protocol_json(output: str) -> dict:
    try:
        value = json.loads(output)
        if not isinstance(value, dict) or type(value.get("schema")) is not int or value["schema"] != 1:
            raise ValueError("expected schema 1")
        return value
    except (ValueError, TypeError) as exc:
        raise OCRError("The vision worker returned an incompatible JSON protocol response; expected schema 1.") from exc


class JsonCliAdapter:
    id = "json-cli-v1"
    name = "Local worker · OCReady JSON v1"

    def validate_model(self, pack: "ModelPack") -> None:
        # The worker owns its model format; admission still counts supplied assets.
        pass

    def command(self, pack: "ModelPack", image: Path, cuda: bool) -> list[str]:
        runner = (pack.cuda_runner or pack.runner) if cuda else pack.runner
        args = [str(Path(runner).expanduser()), "--ocready-vision-v1", "--image", str(image.resolve()),
                "--model", str(Path(pack.model).expanduser()), "--prompt", pack.prompt,
                "--max-output-tokens", str(pack.tokens), "--backend", "cuda" if cuda else "cpu",
                "--max-image-tokens", "1024"]
        if pack.projector:
            args += ["--projector", str(Path(pack.projector).expanduser())]
        return args

    def probe_command(self, runner: str) -> list[str]:
        return [runner, "--ocready-vision-capabilities"]

    def probe_cuda(self, stdout: str, stderr: str) -> bool:
        value = protocol_json(stdout)
        backends = value.get("backends")
        if not isinstance(backends, list) or not backends or any(not isinstance(v, str) or v not in {"cpu", "cuda"} for v in backends):
            raise OCRError("The vision worker must declare its supported CPU/CUDA backends.")
        return "cuda" in backends

    def decode(self, stdout: str, image: Path, cuda: bool) -> VisionRead:
        from PIL import Image
        value = protocol_json(stdout)
        text, backend, note = value.get("text"), value.get("backend"), value.get("note", "")
        width, height = value.get("width"), value.get("height")
        if (not isinstance(text, str) or len(text) > 100_000 or not isinstance(backend, str) or backend not in {"CPU", "CUDA"}
                or not isinstance(note, str) or len(note) > 2000 or type(width) is not int or type(height) is not int):
            raise OCRError("The vision worker returned malformed text, backend, note or image dimensions.")
        with Image.open(image) as picture:
            if (width, height) != picture.size:
                raise OCRError("The vision worker response belongs to a different image size.")
        if not cuda and backend != "CPU":
            raise OCRError("The vision worker used CUDA despite a CPU-only request.")
        if cuda and backend == "CPU":
            note = "The vision worker reported CPU fallback. " + note
        return VisionRead(text, backend, note.strip())

    environment = staticmethod(local_environment)


ADAPTERS: dict[str, VisionAdapter] = {adapter.id: adapter for adapter in (LlamaCppAdapter(), JsonCliAdapter())}


def get_adapter(identifier: str) -> VisionAdapter:
    if not isinstance(identifier, str) or identifier not in ADAPTERS:
        raise OCRError(f"Unsupported vision runtime adapter: {identifier}. Choose llama.cpp or an OCReady JSON v1 worker.")
    return ADAPTERS[identifier]
