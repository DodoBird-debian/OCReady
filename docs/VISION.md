# Local vision models

Offline Tesseract is the default for Arabic and English. Studio can also use a local vision-language model through `llama-mtmd-cli`. Model weights and the matching visual encoder/projector are separate GGUF files. A text-only language model cannot read an image.

Open **Settings → Vision models** and select the CPU runner, model, and matching projector. Give it a name and a conservative total runner RAM estimate. Optionally select a CUDA-enabled runner. Select Studio and choose the saved model in the method list. Models run one at a time and unload when the subprocess exits. No source image is sent to an external service.

The app probes the selected CUDA runner's actual devices. Auto mode uses CUDA only when that runner reports a CUDA device; initialization failures retry once with the CPU runner, all GPU layers disabled, and the projector on CPU. Cancellation and RAM-budget failures never trigger an additional inference attempt.

Vision results are marked as AI transcription. They have no invented confidence or word coordinates. Use Fast or Precision OCR when you need to select individual words in the picture. Generative transcription can hallucinate, and model quality varies by language.

## A tested CPU configuration

- Runner: llama.cpp `b12255`, `llama-mtmd-cli`, Linux x86_64 CPU release.
- Model: [ggml-org/GLM-OCR-GGUF](https://huggingface.co/ggml-org/GLM-OCR-GGUF), revision `65a42de1148dbed2297e922b5dbc7d9b70c36578`.
- Model file: `GLM-OCR-Q8_0.gguf`, SHA256 `45bc244a6446aff850521dc41f18bc8d7105ad5f0c2c8c28af04e7cc4f4d50b1`.
- Projector: `mmproj-GLM-OCR-Q8_0.gguf`, SHA256 `9c4b58e33e316ed142eb5dcb41abec3844d3e6e5dc361ffb782c3fa9d175141f`.
- Prompt: `Text Recognition:` (the dedicated OCR task prompt).
- CPU working set observed on the 1100×720 bilingual example: approximately 1.86 GB process-tree RSS; 23.8 seconds on this development machine.
- The real model read the English paragraphs and the longer Arabic line, but misread `مرحبا` as `مريح`. Tesseract read the sample correctly. This model is an optional alternative, not a demonstrated Arabic accuracy improvement.

This single-image measurement does not certify a universal 4 GB ceiling. The app separately checks estimated CPU footprint, input limits, and sampled runtime RSS. CUDA VRAM is separate from host RAM.

## Headless use

```sh
python -m ocready image.png --json --edition studio --method vision \
  --model-pack /absolute/path/pack.json --backend auto
```

A manifest uses these fields (paths may be relative to the manifest):

```json
{
  "id": "glm-ocr",
  "name": "GLM-OCR Q8",
  "runner": "./llama-mtmd-cli",
  "model": "./GLM-OCR-Q8_0.gguf",
  "projector": "./mmproj-GLM-OCR-Q8_0.gguf",
  "cuda_runner": "",
  "memory_mb": 2800,
  "tokens": 512,
  "prompt": "Text Recognition:"
}
```

The memory estimate covers the complete runner, including both weight files, image encoder, cache, and working buffers. The app adds its current resident memory and another reserve. Estimates below raw weight sizes are raised to a minimum lower bound. Download size is never treated as a measured inference footprint.
