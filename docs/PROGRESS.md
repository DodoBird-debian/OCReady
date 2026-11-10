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

## Iteration 2 — native copy-and-paste workspace

- Built the styled native Qt application with a resizable image/text split, readable empty states, bilingual example, editing, text export, shortcuts, and live RAM display.
- Added zoom/pan, source-word boxes, click/rectangle selection, source-to-editor and editor-to-source highlighting, and selection-only copying.
- Source linking is invalidated after manual edits or image transformations; outdated recognition job IDs are rejected.
- Added clipboard images, image drag-and-drop, reversible inversion/grayscale/contrast/threshold, rotation, mirroring, cropping, and original/processed views.
- Added asynchronous Spectacle region capture and Windows Snipping Tool clipboard ingestion. Checked Spectacle's installed command-line options; interactive capture and Windows round-trip still require desktop validation.
- Added settings persistence without storing images or OCR text, safe close/cancellation, actionable inline errors, and diagnostics.
- Inspected the native rendered workspace with real bilingual OCR and highlighted Arabic words; screenshot in `docs/images/workspace.png`.
- Observed about 120 MB application RSS after the small GUI sample (OCR completed). This does not certify the worst case or include a concurrent VLM.
- Validation: 21 passing tests including real Arabic source clicks/copying, editor linking, edit invalidation, stale result rejection, native clipboard import, background OCR completion, and reversible cleanup; Ruff passed.
- Remaining: real local VLM and CUDA testing, binary compilation, Windows/KDE interactive validation, large-image memory benchmarks, and platform hard-limit policies.

## Iteration 3 — local vision inference and edition-aware delivery

- Added local GGUF model manifests, CPU runner / projector validation, conservative memory admission, multiple saved model configurations, and an in-app model setup dialog.
- Added real llama.cpp multimodal inference with bounded tokens/context/image tokens, explicit CPU flags, actual CUDA device probing, and one CPU retry for GPU initialization failures.
- Vision transcription carries no fabricated confidence or source-word boxes. The basic UI clearly identifies AI output; classical source-linked OCR stays available.
- Ran GLM-OCR Q8 on the real bilingual image: 23.8 seconds, 1.86 GB whole-process-tree peak RSS on CPU. English and the long Arabic line were correct; one Arabic word was misread. This is documented in VISION.md.
- Tested real CUDA discovery with a GTX 1660 Ti. The current prebuilt runner discovered CUDA, but failed with an unsupported PTX toolchain against driver 550; OCReady automatically completed the same job on CPU. This verifies a real fallback path, not successful GPU inference.
- Added edition build manifests, safe embedded-runtime extraction, onefile build tooling, cross-platform source CI, binary build workflows, and packaged real-OCR smoke checks. Compilation and CI results are tracked in the next iteration.
- Added GPL source license and pinned GitHub Actions revisions.
- Validation: 32 passing tests, including manifest validation, missing/incorrect projector checks, relative paths, CPU flags, simulated CUDA retry, and no retry after cancellation or budget failure; Ruff passed.
- Remaining: successful CUDA inference with compatible runtime/driver, compiled artifact verification, Windows desktop validation, broader memory/accuracy workloads, and hard containment.

## Iteration 4 — compiled Linux verification and resource evidence

- Compiled a 64.2 MB Linux Pocket onefile executable with Qt, the OCR runtime, and Arabic/English data embedded; ran it from a separate temporary directory without development runtime overrides.
- Verified real packaged headless OCR and an actual compiled native-GUI recognition path: 31 linked words, correct sample Arabic, and approximately 141 MB idle GUI RSS after the small case.
- Added an external 10 ms RSS observer, cap-sized bilingual tiled images, dark/inverted images, and four-document GUI repetition workloads.
- All 12 source scenarios passed their budgets. Maximum observed classical GUI peaks: Pocket 272.2 MB, Everyday 508.2 MB, Studio 853.5 MB. Raw reports are checked in without recognized document text.
- The compiled Pocket cap-sized GUI case reached 347.3 MB including the onefile launcher. It passed narrowly, exposing an important release risk: the internal monitor currently omits its parent launcher, and the 3 MP Pocket cap leaves insufficient margin. Next iteration prioritizes this verified gap.
- Both Linux and Windows source CI jobs passed all 32 tests. Six edition/platform binary builds were dispatched; the Windows Studio build and real packaged OCR smoke test have passed, with the other jobs still running at this record.
- Documented input limits, observed peaks, onefile startup overhead, sampling limitations, and remaining hard-containment requirements in MEMORY.md.
- Validation: Ruff and 32 tests passed; real Linux compiled CLI and GUI smoke tests passed; benchmark exit codes passed. A real CUDA PTX failure again completed through CPU fallback; successful GPU inference still needs a compatible runner/driver.
