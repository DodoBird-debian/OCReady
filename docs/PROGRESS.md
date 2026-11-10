# Implementation record

## Iteration 0 — architecture and delivery contract

- Created the empty repository and a modular plan with more than 1,000 lines.
- Chose native Qt for Arabic shaping, bidirectional editing, accessibility, and clipboard images.
- Chose Tesseract fast/best for offline OCR, plus an isolated llama.cpp adapter for optional vision-language inference.
- Defined decimal memory budgets over the application and its child processes.
- Chose Nuitka onefile distribution for Linux and Windows, with explicitly bundled runtime data.
- Established that model-size estimates do not certify runtime memory or Arabic accuracy.

The plan describes both the implementation sequence and release gates. Pending items are not claims of completed functionality.

## Iteration 1 — real offline OCR core

- Implemented edition manifests, bounded image decoding, immutable preprocessing recipes, logical-order TSV parsing, and source word ranges.
- Added Tesseract fast/best adapters, sequential layout comparison, process-tree RSS sampling, cancellation, timeout, and subprocess cleanup.
- Added a headless CLI with JSON/text output, diagnostics, language selection, preprocessing switches, and explicit error exit codes.
- Prepared a relocatable Linux OCR runtime without administrator access; pinned Arabic/English fast/best assets by upstream commit and SHA256.
- Rendered a real shaped bilingual fixture with Qt; the engine extracted `مرحبا بالعالم`, `اللغة العربية واللغة الإنجليزية`, and the English paragraphs correctly.
- Observed 31 located words and 75.7 MB process-tree peak RSS for the small bilingual headless case. This is not a GUI, large-image, or universal memory certification.
- Validation: 14 core tests including real English/bilingual OCR, cancellation, timeout, bounded transforms, image safety, Unicode offsets, and shell-safe arguments; Ruff lint.
- Found and corrected a real packaging issue: Tesseract's named `tsv` config was absent from the minimal language-data payload. The adapter now enables TSV directly with `tessedit_create_tsv=1`.
- Remaining: native workspace, capture integration, real VLM inference, binary compilation, Windows validation, and broad memory benchmarks.
