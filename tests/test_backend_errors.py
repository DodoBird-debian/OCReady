import pytest

from ocready.core.backend_errors import cuda_failure_detail, is_cuda_backend_error


@pytest.mark.parametrize("message", [
    "CUDA error: the provided PTX was compiled with an unsupported toolchain.",
    "CUDA initialization failed", "Failed to initialize CUDA", "cuBLAS error: allocation failed",
    "CUBLAS_STATUS_ALLOC_FAILED", "CUDNN_STATUS_NOT_INITIALIZED", "cudaMalloc failed: out of memory",
    "CUDA driver version is insufficient for CUDA runtime version", "no CUDA-capable device is detected",
    "GPU out of memory", "out of GPU memory", "LoadLibrary failed with error 126 loading onnxruntime_providers_cuda.dll",
])
def test_explicit_backend_failures_remain_eligible_for_cpu_recovery(message):
    assert is_cuda_backend_error(message)
    assert cuda_failure_detail(message)


@pytest.mark.parametrize("message", [
    "CUDA0: GPU detected\nerror loading model: invalid GGUF tensor dimensions",
    "Could not read /models/cuda/document.gguf", "CUBLAS_STATUS_SUCCESS\nInvalid input dimensions",
    "Out of memory while allocating CPU model tensors", "CUDA model file does not exist",
    "The CUDA helper returned an invalid JSON response", "Image dimensions are invalid",
    "Runner path: /models/cuda\nerror loading model: invalid tensor dimensions",
])
def test_device_paths_and_model_errors_do_not_trigger_gpu_retries(message):
    assert not is_cuda_backend_error(message)
