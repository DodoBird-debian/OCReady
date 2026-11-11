"""Recognize explicit GPU backend failures without matching device/path mentions.

Keep this module dependency-free: standalone inference workers also include it.
"""
import re

_CUDA_FAILURE = re.compile(
    r"\b(?:CUDA|cuBLAS|cuDNN)(?:[ \t]+(?:runtime|driver))?[ \t]+(?:error|failure)\b"
    r"|\b(?:CUBLAS|CUDNN)_STATUS_(?!SUCCESS\b)[A-Z0-9_]+\b"
    r"|\bCUDA[ \t]+initiali[sz]ation[ \t]+(?:failed|failure|error)\b"
    r"|\b(?:failed|unable)[ \t]+to[ \t]+initiali[sz]e[ \t]+CUDA\b"
    r"|\bcuda(?:Malloc(?:Async)?|MemAlloc|SetDevice|GetDeviceCount)\b[^\n]{0,100}\b(?:failed|error)\b"
    r"|\bCUDA[ \t]+driver\b[^\n]{0,100}\b(?:insufficient|incompatible)\b"
    r"|\bno[ \t]+CUDA[- ]capable[ \t]+device\b"
    r"|\b(?:CUDA|GPU)[ \t]+(?:device[ \t]+)?(?:out[ \t]+of[ \t]+memory|memory[ \t]+allocation[ \t]+failed)\b"
    r"|\bout[ \t]+of[ \t]+(?:CUDA|GPU)[ \t]+memory\b"
    r"|\b(?:LoadLibrary|dlopen)\b[^\n]{0,120}\b(?:failed|error)\b[^\n]{0,160}(?:cuda|cudnn|cublas)",
    re.IGNORECASE,
)


def cuda_failure_detail(text: str) -> str:
    match = _CUDA_FAILURE.search(text)
    if match is None:
        return ""
    start = max(text.rfind("\n", 0, match.start()) + 1, match.start() - 80)
    end = text.find("\n", match.end())
    if end < 0:
        end = len(text)
    return text[start:min(end, match.end() + 200)].strip()[:320]


def is_cuda_backend_error(error: BaseException | str) -> bool:
    return bool(getattr(error, "cuda_failure", False) or cuda_failure_detail(str(error)))
