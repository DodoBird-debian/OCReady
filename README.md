# OCReady

A local-first desktop workspace for turning Arabic and English screenshots into text you can select, edit, and copy.

**Under construction.** See [the modular implementation plan](docs/PLAN.md) and [iteration log](docs/PROGRESS.md). Memory tiers are engineering budgets until benchmarked; no vision model is claimed to fit a tier based on parameter count alone.

The application uses a native Qt split view, offline Tesseract OCR, optional local vision-language models, reversible image cleanup, source-word highlighting, and KDE / Windows screenshot integration. Linux and Windows builds target one-file executables using Nuitka (compiled application and embedded runtime, extracted on launch).

## Development

```sh
uv sync --extra dev
uv run python scripts/prepare_runtime.py
uv run python -m ocready
uv run pytest
```

No document content is uploaded. Vision inference is a local subprocess. Model installation is explicit.

## Editions

| Edition | Whole application + child-process RAM budget | Default methods |
| --- | --- | --- |
| Pocket | below 350,000,000 bytes | Tesseract fast, sparse text, automatic preprocessing |
| Everyday | below 1,000,000,000 bytes | Pocket methods, best language data, sequential comparison |
| Studio | below 4,000,000,000 bytes | Everyday methods, optional local GGUF vision inference |

Budgets use decimal MB/GB. GPU VRAM is separate and must also be reported. Small-tier vision models require a measured complete inference footprint before admission. Arabic accuracy and Windows behavior are separate validation gates.

## License

GPL-3.0-or-later. Qt/PySide and bundled OCR components retain their own notices. See [third-party notices](docs/THIRD_PARTY.md).
