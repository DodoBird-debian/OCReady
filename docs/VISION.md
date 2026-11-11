# Local vision models

Offline Tesseract is the default for Arabic and English. Everyday and Studio can also use local vision-language models through `llama-mtmd-cli`, subject to their RAM admission checks. Model weights and the matching visual encoder/projector are separate GGUF files. A text-only language model cannot read an image.

Open **Settings → Vision models** and select the CPU runner, model, and matching projector. Give it a name and a conservative total runner RAM estimate. Optionally select a separate CUDA-enabled runner; Auto also probes the CPU-runner path when it can support both backends. Choose an edition with enough RAM and select the saved model in the method list. Models run one at a time and unload when the subprocess exits. No source image is sent to an external service.

The app probes the selected CUDA runner's actual devices. Auto mode uses CUDA only when that runner reports a CUDA device; initialization failures retry once with the CPU runner, all GPU layers disabled, and the projector on CPU. Cancellation and RAM-budget failures never trigger an additional inference attempt.

Vision results are marked as AI transcription. They have no invented confidence or word coordinates. Use Fast or Precision OCR when you need to select individual words in the picture. Generative transcription can hallucinate, and model quality varies by language.

AI preview and inference use the same image limits: by default one million pixels and a 1600-pixel longest edge. These limits reduce preview buffers as well as encoder input. The working original is retained for viewing and cropping. If small characters disappear in the reduced preview, crop that area from the original before recognizing. Settings → Vision models exposes both limits, within the supported bounds of 0.25–2.56 million pixels and 512–1600 pixels per edge. Fast and Precision retain their edition's larger image limits.

## A tested CPU configuration

- Runner: llama.cpp `b12255`, `llama-mtmd-cli`, Linux x86_64 CPU release.
- Model: [ggml-org/GLM-OCR-GGUF](https://huggingface.co/ggml-org/GLM-OCR-GGUF), revision `65a42de1148dbed2297e922b5dbc7d9b70c36578`.
- Model file: `GLM-OCR-Q8_0.gguf`, SHA256 `45bc244a6446aff850521dc41f18bc8d7105ad5f0c2c8c28af04e7cc4f4d50b1`.
- Projector: `mmproj-GLM-OCR-Q8_0.gguf`, SHA256 `9c4b58e33e316ed142eb5dcb41abec3844d3e6e5dc361ffb782c3fa9d175141f`.
- Prompt: `Text Recognition:` (the dedicated OCR task prompt).
- CPU working set observed on the 1100×720 bilingual example: approximately 1.86 GB process-tree RSS; 23.8 seconds on this development machine.
- The real model read the English paragraphs and the longer Arabic line, but misread `مرحبا` as `مريح`. Tesseract read the sample correctly. This model is an optional alternative, not a demonstrated Arabic accuracy improvement.

The initially downloaded CUDA 12.8 runner discovered the GTX 1660 Ti but failed against driver 550 with an unsupported PTX toolchain; automatic CPU fallback completed successfully. A runner built locally with CUDA 12.4 and native SM 7.5 kernels then completed real GLM-OCR inference in **6.9 seconds**, with **1.24 GB host process-tree RSS**. It produced the same one-word Arabic error. This verifies actual CUDA inference as well as a real fallback scenario, on Linux.

These single-image measurements do not certify a universal 4 GB ceiling. The app separately checks estimated CPU footprint, input limits, and sampled runtime RSS. CUDA VRAM is separate from host RAM.

## A smaller English-only alternative

The [SmolVLM-256M model card](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct) declares English support. The Q8 GGUF plus projector total about 279 MB on disk, and the real CPU run used about 491 MB including the small headless application. It read the sample's three English paragraphs and omitted the Arabic. OCReady therefore requires an English-only language setting for this pack; it is not an Arabic OCR replacement.

Four Everyday source workloads passed with this pack, including an 8 MP tiled-image case and repeated native GUI runs. The largest observed GUI process-tree RSS was **847.5 MB**. See [the raw report](benchmarks/linux-everyday-smolvlm.json).

With the shared one-million-pixel preview/input limit, the Q4 model passed the same four source workloads. Its repeated 8 MP GUI peak was **735.0 MB**. See [the Q4 bounded-input report](benchmarks/linux-everyday-smolvlm-q4-bounded.json). This measures memory and successful inference, not transcription accuracy on the tiled stress image.

A Q4 variant was tested in an **entirely embedded, vision-only executable** built from clean source `e9cdf23`: a 269.7 MB Linux binary containing the runner, model and projector. It passed small-image CLI and native GUI transcription checks. All four packaged memory workloads also passed: 780.9 MB sample, 777.2 MB inverted image, 826.7 MB cap-sized headless input, and **921.2 MB for the full 8 MP GUI workflow**, including the onefile launcher. See [the binary-identified report](benchmarks/linux-everyday-smolvlm-q4-onefile.json). This validates the tested Linux single-method packaging and memory workload. It does not establish Arabic accuracy, Windows VLM behavior, or a universal allocation ceiling.

The later clean `2ba93c6` build releases unused launcher payload residency after extraction. Its 270.0 MB embedded executable passed the same packaged workloads with a **651.6 MB** maximum GUI peak, still counting its launcher and OCR children. [Updated binary-identified report](benchmarks/linux-everyday-smolvlm-q4-onefile-trimmed.json). This adds headroom for future engine combinations; each combination still needs its own admission and packaged tests.

## Preparing reproducible CPU presets

Developer preparation can provision checksum-locked official GGUF files, matching projectors, a Linux/Windows x86_64 CPU runner and retained model cards/notices:

```sh
uv run python -m scripts.prepare_vision --preset smol
# Studio can include both choices:
uv run python -m scripts.prepare_vision --preset smol --preset glm
```

The manifests are `models/vision/smol/pack.json` and `models/vision/glm/pack.json`. Repeat `--model-pack` when building to embed both. These downloads occur during explicit preparation, never at app startup. Every asset has a pinned revision, byte size and SHA256 in `assets/vision-lock.json`; archive extraction rejects escaping paths and links. Generated manifests use relative paths and include the upstream cards.

Both presets expose English. SmolVLM declares English only. GLM-OCR's upstream card lists eight languages but does not list Arabic; Arabic text occasionally read in experiments does not establish supported Arabic transcription. Use the bilingual classical or neural methods for Arabic. These presets supply CPU inference; `--cuda-runner` can add a separately provisioned compatible runner. A preset's disk size and memory estimate are not packaged resource certification.

## Building a compatible CUDA runner

For a Linux driver that cannot run newer upstream PTX, an optional developer tool builds pinned llama.cpp with native kernels and NVIDIA's checksum-verified CUDA 12.4 redistributables:

```sh
uv sync --extra dev --extra cuda-build
uv run python scripts/build_vision_runner.py --architecture 75 --jobs 3 \
  --host-cxx /path/to/a/compatible/g++-12
```

The tool installs nothing system-wide and does not change the GPU driver. It keeps the toolchain and build under `runtime/`. On Debian 13 it applies the upstream-documented glibc math-declaration compatibility correction only to its own extracted SDK. The selected architecture must match the target GPU; `75` is the tested GTX 1660 Ti. Use the resulting `runtime/llama-cuda-native/bin/llama-mtmd-cli` as the CUDA runner. Retained upstream notices accompany its libraries.

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
  "max_pixels": 1000000,
  "max_edge": 1600,
  "tokens": 512,
  "prompt": "Text Recognition:",
  "languages": "eng"
}
```

The memory estimate covers the complete runner, including both weight files, image encoder, cache, and working buffers. The app adds its current resident memory and an application reserve: 16 MB plus 24 bytes per bounded input pixel (six 4-byte pixel buffers). Estimates below raw weight sizes are raised to a minimum lower bound. This reserve is an admission heuristic, not an allocation proof; runtime worker limits and process-tree monitoring remain active. Download size is never treated as a measured inference footprint.
