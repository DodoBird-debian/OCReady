# OCReady

A local-first desktop workspace for turning Arabic and English screenshots into text you can select, edit, and copy.

**Under construction.** See [the modular implementation plan](docs/PLAN.md) and [iteration log](docs/PROGRESS.md). Memory tiers are engineering budgets until benchmarked; no vision model is claimed to fit a tier based on parameter count alone.

[Download experimental Linux and Windows prereleases](https://github.com/DodoBird-debian/OCReady/releases). They include all three editions, checksums, build manifests, and measured resource reports. Development continues beyond each tagged snapshot.

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

Switching between the original and processed picture keeps your linked selection, including through crop and rotation. Neural OCR selections cover whole detected lines; Fast and Precision support individual words.

Enable **Compare layouts** to retain two OCR reads. The **Compare reads** selector lets you inspect and choose either result, including its own source boxes, without repeating inference. A higher OCR confidence can still omit text; verify the reading against the picture.

Use **Ctrl+C** with the picture focused to copy its selected words. The text pane keeps native selection copying. Automatic paragraph direction also follows Arabic and English as you edit or paste; Undo restores the text in one step.

Everyday admits smaller local vision-language packs; Studio admits larger ones. Configure one or more packs under **Settings → Vision models**; see [setup and measured results](docs/VISION.md). Real CPU inference, CUDA inference, and a GPU-failure-to-CPU fallback have been exercised on Linux. Vision output has no invented source boxes or confidence. The tiny SmolVLM choice supports English; Studio's experimental Qwen3-VL preset has been evaluated on Arabic + English, with known digit/diacritic errors.

The [LLM runtime layer is modular](docs/VISION-ADAPTERS.md): swap local models, projectors, prompts and CPU/CUDA runners through packs. Existing packs default to llama.cpp; other offline runtimes can implement the versioned JSON-worker adapter. Admission, cancellation, containment and fallback remain shared across adapters.

An additional [local neural OCR method](docs/NEURAL.md) uses PP-OCRv5 detection and Arabic/English recognition in a separate compiled worker. Its real detected lines can be selected and copied from the picture. [Download Everyday with all four methods for Linux or Windows](https://github.com/DodoBird-debian/OCReady/releases/tag/v0.1.0-everyday-multimodal-json-preview.8), or choose the [smaller neural-only preview](https://github.com/DodoBird-debian/OCReady/releases/tag/neural-preview.1). Workers and models are embedded. The latest four-method release passed all sixteen resource scenarios on each platform, peaking at 659 MB on Linux and 562 MB on Windows; see [release evidence](docs/benchmarks/everyday-json-release.json). It uses the alternate JSON vision interface with the compact English model. The [earlier native-interface composition](https://github.com/DodoBird-debian/OCReady/releases/tag/v0.1.0-everyday-multimodal-preview.3) remains available. Configure external packs under **Settings → Neural OCR**, or embed them with `--neural-pack`.

Fresh default Everyday/Studio GUI sessions prefer Precision for bilingual text; curated model-rich variants prefer their bundled bilingual neural engine. Your method choice is remembered separately for each edition, along with the last available edition, layout, language, and compute backend. An explicit `--edition` overrides the saved GUI edition; headless defaults remain the build's default.

## Compiling a single executable

```sh
uv run python scripts/prepare_runtime.py --best
uv run python scripts/build.py --edition pocket
uv run python scripts/smoke_binary.py dist/pocket
```

Use `everyday` or `studio` for the other editions. A onefile build embeds Qt, the selected OCR runtimes and model data, then extracts a private payload at startup. Vision packs can be external or embedded. For a single-method build with all vision assets inside the executable:

```sh
uv run python scripts/build.py --edition everyday --methods vision \
  --model-pack /absolute/path/to/pack.json
```

Repeat `--model-pack` to embed multiple compatible models, or use `--methods fast,best,vision` for a combined build. Installed models run sequentially. A 270.0 MB Linux vision-only executable with an English-only small model passed real CLI/GUI inference and its full 8 MP GUI memory workload at 652 MB after releasing dormant launcher residency. GitHub Actions builds the default Linux and Windows editions separately; artifacts remain prereleases until their platform and resource gates pass.

Build manifests record the source revision, source-content digest, dirty state, dependency versions, and included asset hashes. Keep sources unchanged during compilation; the build rejects a changed source tree before producing distribution metadata. Benchmark reports identify the measured executable by SHA256.

Tag builds can publish verified experimental prereleases after all six packaged checks pass. See [release evidence and preparation](docs/RELEASING.md).

No document content is uploaded. Vision inference is a local subprocess. Model installation is explicit.

## Editions

| Edition | Whole application + child-process RAM budget | Default methods |
| --- | --- | --- |
| Pocket | below 350,000,000 bytes | Tesseract fast, sparse text, reversible image cleanup |
| Everyday | below 1,000,000,000 bytes | Pocket methods, best language data, comparison, admissible small vision packs |
| Studio | below 4,000,000,000 bytes | Everyday methods, optional local GGUF vision inference |

Budgets use decimal MB/GB. GPU VRAM is separate and must also be reported. Small-tier vision models require a measured complete inference footprint before admission. Arabic accuracy and Windows behavior are separate validation gates.

See [measured memory workloads and limitations](docs/MEMORY.md). Branded Pocket executables at `8fa1f03` passed all four packaged workloads on both CI platforms, peaking at 228 MB on Linux and 175 MB on Windows, including their launchers. Studio's two-LLM composition also passed twenty scenarios per platform at clean `25c7477`, with 3.255 GB Linux and 3.138 GB Windows maxima. A subsequent Studio release attempt exposed a diagnostic deadline mismatch; corrected verification remains required before publication. These measurements are not universal hard-memory certifications.

The [accuracy corpus and evaluator](docs/ACCURACY.md) track character/word errors across Arabic and English styles, including difficult cases. Passing resource tests is separate from transcription accuracy.

## License

GPL-3.0-or-later. Qt/PySide and bundled OCR components retain their own notices. See [third-party notices](docs/THIRD_PARTY.md).
