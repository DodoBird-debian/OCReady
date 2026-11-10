# OCReady

A local-first desktop workspace for turning Arabic and English screenshots into text you can select, edit, and copy.

**Under construction.** See [the modular implementation plan](docs/PLAN.md) and [iteration log](docs/PROGRESS.md). Memory tiers are engineering budgets until benchmarked; no vision model is claimed to fit a tier based on parameter count alone.

The application uses a native Qt split view, offline Tesseract OCR, optional local vision-language models, reversible image cleanup, source-word highlighting, and KDE / Windows screenshot integration. Linux and Windows builds target one-file executables using Nuitka (compiled application and embedded runtime, extracted on launch).

![Native bilingual OCR workspace](docs/images/workspace.png)

## Development

```sh
uv sync --extra dev
uv run python scripts/prepare_runtime.py
uv run python -m ocready
uv run pytest
```

The same commands work with a normal virtual environment: install `.[dev]`, then use `python` directly. Debian runtime preparation extracts packages without requiring root. Windows preparation uses an existing Tesseract installation.

```sh
python -m ocready assets/sample-bilingual.png --json --layout sparse
python -m ocready --diagnostics
```

Open/paste/capture an image, choose **Recognize text**, and copy. Click or drag over the picture to select located words. Selecting editor text highlights its source; manual edits invalidate source linking until the next recognition. Image cleanup is reversible. Use F1 for shortcuts.

Studio supports local vision-language models through llama.cpp. Configure one or more packs under **Settings → Vision models**; see [setup and measured results](docs/VISION.md). CPU inference and a real CUDA-failure-to-CPU fallback have been exercised. Vision output has no invented source boxes or confidence.

## Compiling a single executable

```sh
uv run python scripts/prepare_runtime.py --best
uv run python scripts/build.py --edition pocket
uv run python scripts/smoke_binary.py dist/pocket
```

Use `everyday` or `studio` for the other editions. A onefile build embeds Qt, the OCR executable, its runtime libraries, and Arabic/English model data, then extracts a private payload at startup. Optional vision packs are local external files in the current build tooling. GitHub Actions builds Linux and Windows separately; these are prerelease artifacts until their platform and resource gates pass.

No document content is uploaded. Vision inference is a local subprocess. Model installation is explicit.

## Editions

| Edition | Whole application + child-process RAM budget | Default methods |
| --- | --- | --- |
| Pocket | below 350,000,000 bytes | Tesseract fast, sparse text, automatic preprocessing |
| Everyday | below 1,000,000,000 bytes | Pocket methods, best language data, sequential comparison |
| Studio | below 4,000,000,000 bytes | Everyday methods, optional local GGUF vision inference |

Budgets use decimal MB/GB. GPU VRAM is separate and must also be reported. Small-tier vision models require a measured complete inference footprint before admission. Arabic accuracy and Windows behavior are separate validation gates.

See [measured memory workloads and limitations](docs/MEMORY.md). Linux source benchmarks and a compiled Pocket executable have been exercised; the compiled cap-sized GUI case is currently close to the Pocket ceiling and is being improved.

## License

GPL-3.0-or-later. Qt/PySide and bundled OCR components retain their own notices. See [third-party notices](docs/THIRD_PARTY.md).
