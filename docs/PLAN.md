# OCReady — modular engineering and execution plan

Plan date: 2026-11-10 (Asia/Baghdad).
This document is an implementation contract, not a claim that every described capability already exists.
Each module has a bounded responsibility, implementation tasks, verification cases, and a release gate.
The execution log in PROGRESS.md is authoritative for which parts have actually been built and tested.

## Product outcome

OCReady turns a screenshot or local image into Arabic and English text that can be selected, edited, and copied.
The main workspace has an image pane and a text pane with linked highlighting where word geometry is available.
The application must remain useful without internet connectivity after installation.
Classical OCR is mandatory; optional vision-language methods extend difficult-image transcription.
Three editions target less than 350 MB, 1 GB, and 4 GB of total host RAM respectively.
Units in this plan are decimal: 1 MB = 1,000,000 bytes and 1 GB = 1,000,000,000 bytes.
Model weights, visual encoder weights, KV cache, activations, image buffers, UI, and runner overhead all count.
CUDA is optional and must fall back to CPU when the configured model remains admissible on CPU.
A CPU fallback that would exceed the edition budget must be rejected with a clear explanation.
A 350 MB downloadable model is not automatically a model that can infer inside 350 MB of application RAM.
Pocket will ship classical OCR first; no unmeasured tiny vision model will be advertised as compliant.
A user can install one method or multiple methods, but only one heavy inference job is resident at a time.
Linux and Windows deliverables are compiled onefile executables; extraction at startup is permitted and documented.
The onefile application includes Qt and classical OCR data and does not require a separate Python installation.
Optional GGUF models may be external packs or deliberately embedded build assets.
Arabic shaping and mixed-direction editing are release requirements, not cosmetic enhancements.

## Architectural decisions

ADR-001: Use Python with PySide6 Essentials and Qt Widgets for a native shaped-text interface.
ADR-002: Compile the application with Nuitka and bundle the redistributable runtime in onefile mode.
ADR-003: Keep recognition in subprocesses so cancellation and worker memory can be managed independently.
ADR-004: Use Tesseract with fast and best language sets as the initial non-generative engine family.
ADR-005: Use a llama.cpp adapter with explicit model and projector configuration for optional local VLMs.
ADR-006: Keep images out of settings and keep document content out of logs by default.
ADR-007: Record located OCR separately from generative transcription because only located OCR provides source geometry.
ADR-008: Use serial comparison rather than simultaneous model loading to preserve the memory contract.
ADR-009: Keep source pixels immutable; derive a bounded transformed OCR input and store its provenance.
ADR-010: Treat memory certification, CUDA testing, Windows interaction, and Arabic accuracy as separate gates.

## Dependency graph and implementation sequence

Iteration 0: Product contract → edition policy → domain schema → public repository and this plan.
Iteration 1: Image intake → preprocessing → Tesseract runtime → parser → headless CLI → real OCR verification.
Iteration 2: Visual design → split workspace → clipboard → canvas → linked highlighting → native UI verification.
Iteration 3: KDE and Windows capture → cancellation → stale-job handling → settings → workflow verification.
Iteration 4: Model registry → local vision runner → CUDA policy → model admission → honest capability reporting.
Iteration 5: Runtime preparation → onefile builds → Linux and Windows CI → artifact smoke tests.
Iteration 6: Accuracy corpus → whole-process benchmarks → resource fixes → release-readiness review.
Later cycles: Recheck the full product, correct observed shortcomings, validate, commit, and push.
Every iteration must leave reviewable source and update PROGRESS.md with evidence and remaining gaps.
Every implementation iteration must end with a git commit and a push to the public GitHub repository OCReady.

## Acceptance and evidence policy

A code path without an exercised test or runtime observation is implemented but unverified.
A mocked runner test proves adapter behavior; it does not prove an actual VLM can perform Arabic OCR.
A successful Linux build does not prove Windows behavior, and vice versa.
A successful small-image benchmark does not prove the bound for arbitrary input sizes.
Input limits and admission checks must be part of each memory-tier claim.
Memory sampling is a guardrail and must not be described as an OS-enforced hard ceiling.
A build can be distributed as a prerelease while clearly listing unverified requirements.
A method that produces no word coordinates cannot pretend to support precise source-word highlighting.
A clean screenshot with Arabic text must be inspected visually and recognized, not merely stored in a fixture folder.
No network request may transmit user document content in the default local workflow.
The goal stays active for continued improvements at the user's request.

## Detailed module contracts

### M01 — Product contract
- Responsibility: Define the copy-and-paste workflow and verifiable release criteria.
- Primary implementation location: `docs/PLAN.md`.
- Input contract: accept only validated values at the boundary of product contract.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep product contract independent of unrelated UI and inference implementations.
- M01.T1: Make capture to copy the primary path.
- M01.T2: Keep first run useful without a network.
- M01.T3: Prioritize Arabic and English equally.
- M01.T4: Make advanced methods optional.
- M01.T5: Keep methods replaceable behind contracts.
- M01.T6: Label experimental capabilities honestly.
- State rule: do not publish partial product contract changes as a successful completed operation.
- Resource rule: include allocations and child processes used by product contract in the selected edition budget.
- Failure rule: preserve the current document when product contract cannot complete safely.
- Cancellation rule: dispose transient work owned by product contract before signaling a terminal state.
- M01.V1: Extract a screenshot in three actions.
- M01.V2: Start offline with bundled languages.
- M01.V3: Identify the current engine in the result.
- M01.V4: Find every requirement in the traceability table.
- Principal risk: Scope growth must not make basic capture slower.
- Evidence gate: record concrete validation of product contract in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit product contract for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the product contract changes in a coherent tested git iteration and push it.

### M02 — Edition policy
- Responsibility: Represent Pocket, Everyday, and Studio as immutable capability manifests.
- Primary implementation location: `ocready/core/editions.py`.
- Input contract: accept only validated values at the boundary of edition policy.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep edition policy independent of unrelated UI and inference implementations.
- M02.T1: Use 350000000 bytes for Pocket.
- M02.T2: Use 1000000000 bytes for Everyday.
- M02.T3: Use 4000000000 bytes for Studio.
- M02.T4: Reserve memory for the native interface.
- M02.T5: Admit only a compatible method subset.
- M02.T6: Keep all three editions selectable during development.
- State rule: do not publish partial edition policy changes as a successful completed operation.
- Resource rule: include allocations and child processes used by edition policy in the selected edition budget.
- Failure rule: preserve the current document when edition policy cannot complete safely.
- Cancellation rule: dispose transient work owned by edition policy before signaling a terminal state.
- M02.V1: Reject an unknown edition.
- M02.V2: Reject a method outside a tier.
- M02.V3: Use decimal units consistently.
- M02.V4: Never confuse model size with memory.
- Principal risk: Nominal parameter count cannot certify an inference footprint.
- Evidence gate: record concrete validation of edition policy in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit edition policy for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the edition policy changes in a coherent tested git iteration and push it.

### M03 — Domain schema
- Responsibility: Keep engine-neutral inputs, words, geometry, and results.
- Primary implementation location: `ocready/core/types.py`.
- Input contract: accept only validated values at the boundary of domain schema.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep domain schema independent of unrelated UI and inference implementations.
- M03.T1: Define stable engine identifiers.
- M03.T2: Use source pixel coordinates for words.
- M03.T3: Carry language and confidence metadata.
- M03.T4: Track generated text separately from located words.
- M03.T5: Record preprocessing provenance.
- M03.T6: Keep result objects serializable.
- State rule: do not publish partial domain schema changes as a successful completed operation.
- Resource rule: include allocations and child processes used by domain schema in the selected edition budget.
- Failure rule: preserve the current document when domain schema cannot complete safely.
- Cancellation rule: dispose transient work owned by domain schema before signaling a terminal state.
- M03.V1: Round-trip multilingual text.
- M03.V2: Reject negative bounding boxes.
- M03.V3: Preserve document identity.
- M03.V4: Represent missing confidence explicitly.
- Principal risk: Vision output may not include reliable word coordinates.
- Evidence gate: record concrete validation of domain schema in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit domain schema for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the domain schema changes in a coherent tested git iteration and push it.

### M04 — Image intake
- Responsibility: Read image files without unbounded decoder allocations.
- Primary implementation location: `ocready/core/images.py`.
- Input contract: accept only validated values at the boundary of image intake.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep image intake independent of unrelated UI and inference implementations.
- M04.T1: Support PNG and JPEG first.
- M04.T2: Support BMP TIFF and WebP where Pillow decodes them.
- M04.T3: Apply EXIF orientation before display.
- M04.T4: Flatten alpha against white.
- M04.T5: Check dimensions before decoding.
- M04.T6: Limit decompressed pixels by edition.
- State rule: do not publish partial image intake changes as a successful completed operation.
- Resource rule: include allocations and child processes used by image intake in the selected edition budget.
- Failure rule: preserve the current document when image intake cannot complete safely.
- Cancellation rule: dispose transient work owned by image intake before signaling a terminal state.
- M04.V1: Load transparent PNG correctly.
- M04.V2: Reject a decompression bomb.
- M04.V3: Explain a corrupt file.
- M04.V4: Keep filenames with Arabic characters.
- Principal risk: Tiny compressed files can decode into enormous images.
- Evidence gate: record concrete validation of image intake in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit image intake for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the image intake changes in a coherent tested git iteration and push it.

### M05 — Clipboard images
- Responsibility: Make pasting screenshots a first-class document source.
- Primary implementation location: `ocready/ui/window.py`.
- Input contract: accept only validated values at the boundary of clipboard images.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep clipboard images independent of unrelated UI and inference implementations.
- M05.T1: Accept Qt clipboard image data.
- M05.T2: Accept a local image file URL.
- M05.T3: Keep normal editor paste behavior.
- M05.T4: Offer an explicit Paste image button.
- M05.T5: Normalize device pixel ratio.
- M05.T6: Do not poll document contents continuously.
- State rule: do not publish partial clipboard images changes as a successful completed operation.
- Resource rule: include allocations and child processes used by clipboard images in the selected edition budget.
- Failure rule: preserve the current document when clipboard images cannot complete safely.
- Cancellation rule: dispose transient work owned by clipboard images before signaling a terminal state.
- M05.V1: Paste a Windows screenshot.
- M05.V2: Paste a KDE screenshot.
- M05.V3: Avoid replacing the document with text paste.
- M05.V4: Show a helpful empty clipboard message.
- Principal risk: Clipboard ownership and MIME behavior differ across platforms.
- Evidence gate: record concrete validation of clipboard images in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit clipboard images for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the clipboard images changes in a coherent tested git iteration and push it.

### M06 — KDE capture
- Responsibility: Invoke Spectacle without a shell and import its output.
- Primary implementation location: `ocready/core/capture.py`.
- Input contract: accept only validated values at the boundary of kde capture.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep kde capture independent of unrelated UI and inference implementations.
- M06.T1: Discover spectacle with PATH lookup.
- M06.T2: Use rectangular capture in background mode.
- M06.T3: Write to a private temporary path.
- M06.T4: Hide the main window before capture.
- M06.T5: Restore it after completion or cancellation.
- M06.T6: Bound capture lifetime and clean temporary files.
- State rule: do not publish partial kde capture changes as a successful completed operation.
- Resource rule: include allocations and child processes used by kde capture in the selected edition budget.
- Failure rule: preserve the current document when kde capture cannot complete safely.
- Cancellation rule: dispose transient work owned by kde capture before signaling a terminal state.
- M06.V1: Cancel capture without losing work.
- M06.V2: Handle missing Spectacle.
- M06.V3: Capture on Wayland where supported by Spectacle.
- M06.V4: Avoid including the app in the snip.
- Principal risk: Spectacle options and compositor permissions vary by installation.
- Evidence gate: record concrete validation of kde capture in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit kde capture for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the kde capture changes in a coherent tested git iteration and push it.

### M07 — Windows capture
- Responsibility: Launch the Windows snipping experience and ingest clipboard changes.
- Primary implementation location: `ocready/core/capture.py`.
- Input contract: accept only validated values at the boundary of windows capture.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep windows capture independent of unrelated UI and inference implementations.
- M07.T1: Use a supported screen clipping URI.
- M07.T2: Avoid redirect callbacks requiring MSIX identity.
- M07.T3: Wait for a new image clipboard generation.
- M07.T4: Ignore an unchanged old screenshot.
- M07.T5: Restore the app after a captured image.
- M07.T6: Offer manual paste if activation fails.
- State rule: do not publish partial windows capture changes as a successful completed operation.
- Resource rule: include allocations and child processes used by windows capture in the selected edition budget.
- Failure rule: preserve the current document when windows capture cannot complete safely.
- Cancellation rule: dispose transient work owned by windows capture before signaling a terminal state.
- M07.V1: Reject a stale clipboard image.
- M07.V2: Cancel a timed-out snip.
- M07.V3: Launch on Windows 11.
- M07.V4: Keep the current document on failure.
- Principal risk: Unpackaged Win32 apps cannot use packaged redirect URI semantics.
- Evidence gate: record concrete validation of windows capture in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit windows capture for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the windows capture changes in a coherent tested git iteration and push it.

### M08 — Document lifecycle
- Responsibility: Ensure the image and text panes always refer to the same document.
- Primary implementation location: `ocready/ui/window.py`.
- Input contract: accept only validated values at the boundary of document lifecycle.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep document lifecycle independent of unrelated UI and inference implementations.
- M08.T1: Assign monotonically increasing job IDs.
- M08.T2: Invalidate results when source changes.
- M08.T3: Ask before replacing edited text when needed.
- M08.T4: Reset word overlays after transformations.
- M08.T5: Keep only one full document in Pocket.
- M08.T6: Release previous image buffers promptly.
- State rule: do not publish partial document lifecycle changes as a successful completed operation.
- Resource rule: include allocations and child processes used by document lifecycle in the selected edition budget.
- Failure rule: preserve the current document when document lifecycle cannot complete safely.
- Cancellation rule: dispose transient work owned by document lifecycle before signaling a terminal state.
- M08.V1: Drop a second image during recognition.
- M08.V2: Discard an obsolete worker result.
- M08.V3: Keep manual edits until explicit replacement.
- M08.V4: Open repeated images without growth.
- Principal risk: Late asynchronous results can attach to the wrong source.
- Evidence gate: record concrete validation of document lifecycle in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit document lifecycle for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the document lifecycle changes in a coherent tested git iteration and push it.

### M09 — Preprocessing pipeline
- Responsibility: Provide reversible bounded image transformations.
- Primary implementation location: `ocready/core/preprocess.py`.
- Input contract: accept only validated values at the boundary of preprocessing pipeline.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep preprocessing pipeline independent of unrelated UI and inference implementations.
- M09.T1: Keep an untouched source image.
- M09.T2: Compose transforms into one pipeline.
- M09.T3: Preview processed versus original.
- M09.T4: Store a compact transform description.
- M09.T5: Apply the identical pipeline to all comparisons.
- M09.T6: Clear OCR geometry when pixel geometry changes.
- State rule: do not publish partial preprocessing pipeline changes as a successful completed operation.
- Resource rule: include allocations and child processes used by preprocessing pipeline in the selected edition budget.
- Failure rule: preserve the current document when preprocessing pipeline cannot complete safely.
- Cancellation rule: dispose transient work owned by preprocessing pipeline before signaling a terminal state.
- M09.V1: Reset exactly to the source.
- M09.V2: Match preview with OCR input.
- M09.V3: Keep output below a tier pixel cap.
- M09.V4: Report every active transformation.
- Principal risk: Unnecessary image copies consume the smallest memory budget.
- Evidence gate: record concrete validation of preprocessing pipeline in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit preprocessing pipeline for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the preprocessing pipeline changes in a coherent tested git iteration and push it.

### M10 — Color cleanup
- Responsibility: Improve difficult light and dark screenshots.
- Primary implementation location: `ocready/core/preprocess.py`.
- Input contract: accept only validated values at the boundary of color cleanup.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep color cleanup independent of unrelated UI and inference implementations.
- M10.T1: Invert RGB while preserving legibility.
- M10.T2: Offer grayscale conversion.
- M10.T3: Offer automatic contrast.
- M10.T4: Offer a contrast slider.
- M10.T5: Offer global threshold with an adjustable cutoff.
- M10.T6: Provide a dark-screenshot preset.
- State rule: do not publish partial color cleanup changes as a successful completed operation.
- Resource rule: include allocations and child processes used by color cleanup in the selected edition budget.
- Failure rule: preserve the current document when color cleanup cannot complete safely.
- Cancellation rule: dispose transient work owned by color cleanup before signaling a terminal state.
- M10.V1: Read inverted terminal text.
- M10.V2: Avoid alpha turning text transparent.
- M10.V3: Preserve punctuation and Arabic dots.
- M10.V4: Do not silently normalize user images.
- Principal risk: Aggressive thresholding destroys thin Arabic strokes.
- Evidence gate: record concrete validation of color cleanup in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit color cleanup for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the color cleanup changes in a coherent tested git iteration and push it.

### M11 — Geometry cleanup
- Responsibility: Rotate, mirror, and crop with explicit coordinate meaning.
- Primary implementation location: `ocready/core/preprocess.py`.
- Input contract: accept only validated values at the boundary of geometry cleanup.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep geometry cleanup independent of unrelated UI and inference implementations.
- M11.T1: Rotate by quarter turns.
- M11.T2: Flip horizontally.
- M11.T3: Flip vertically.
- M11.T4: Crop a user-selected rectangle.
- M11.T5: Use bounded resizing for small text.
- M11.T6: Document whether boxes refer to original or processed pixels.
- State rule: do not publish partial geometry cleanup changes as a successful completed operation.
- Resource rule: include allocations and child processes used by geometry cleanup in the selected edition budget.
- Failure rule: preserve the current document when geometry cleanup cannot complete safely.
- Cancellation rule: dispose transient work owned by geometry cleanup before signaling a terminal state.
- M11.V1: Rotate four times to the same dimensions.
- M11.V2: Crop edges without zero-size images.
- M11.V3: Mirror twice to restore content.
- M11.V4: Select words after a crop.
- Principal risk: Coordinate transformations must not point to another word.
- Evidence gate: record concrete validation of geometry cleanup in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit geometry cleanup for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the geometry cleanup changes in a coherent tested git iteration and push it.

### M12 — Automatic recipe selection
- Responsibility: Offer sequential alternatives without multiplying resident engines.
- Primary implementation location: `ocready/engines/pipeline.py`.
- Input contract: accept only validated values at the boundary of automatic recipe selection.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep automatic recipe selection independent of unrelated UI and inference implementations.
- M12.T1: Run a baseline original-image pass.
- M12.T2: Retry inverted text only when requested or justified.
- M12.T3: Try sparse segmentation for screenshots.
- M12.T4: Score alternatives by word confidence and coverage.
- M12.T5: Preserve each candidate for comparison.
- M12.T6: Never run candidates concurrently in Pocket.
- State rule: do not publish partial automatic recipe selection changes as a successful completed operation.
- Resource rule: include allocations and child processes used by automatic recipe selection in the selected edition budget.
- Failure rule: preserve the current document when automatic recipe selection cannot complete safely.
- Cancellation rule: dispose transient work owned by automatic recipe selection before signaling a terminal state.
- M12.V1: Compare two recipes deterministically.
- M12.V2: Cancel between candidates.
- M12.V3: Avoid replacing a better baseline with blank output.
- M12.V4: Disclose the selected recipe.
- Principal risk: OCR confidence is not calibrated across unrelated model families.
- Evidence gate: record concrete validation of automatic recipe selection in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit automatic recipe selection for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the automatic recipe selection changes in a coherent tested git iteration and push it.

### M13 — Tesseract runtime
- Responsibility: Use bundled or explicitly discovered offline OCR executables.
- Primary implementation location: `ocready/engines/tesseract.py`.
- Input contract: accept only validated values at the boundary of tesseract runtime.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep tesseract runtime independent of unrelated UI and inference implementations.
- M13.T1: Prefer the bundled runtime.
- M13.T2: Allow a user-selected executable.
- M13.T3: Set explicit tessdata location.
- M13.T4: Limit OpenMP worker count.
- M13.T5: Capture bounded stdout and stderr.
- M13.T6: Avoid shell interpolation entirely.
- State rule: do not publish partial tesseract runtime changes as a successful completed operation.
- Resource rule: include allocations and child processes used by tesseract runtime in the selected edition budget.
- Failure rule: preserve the current document when tesseract runtime cannot complete safely.
- Cancellation rule: dispose transient work owned by tesseract runtime before signaling a terminal state.
- M13.V1: Run from a path containing spaces.
- M13.V2: Reject missing language data.
- M13.V3: Report a missing executable.
- M13.V4: Recognize without internet.
- Principal risk: Host libraries may differ from development libraries.
- Evidence gate: record concrete validation of tesseract runtime in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit tesseract runtime for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the tesseract runtime changes in a coherent tested git iteration and push it.

### M14 — Fast language data
- Responsibility: Bundle compact Arabic and English language models.
- Primary implementation location: `scripts/prepare_runtime.py`.
- Input contract: accept only validated values at the boundary of fast language data.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep fast language data independent of unrelated UI and inference implementations.
- M14.T1: Pin upstream tessdata_fast revision.
- M14.T2: Download only ara and eng by default.
- M14.T3: Verify pinned SHA256 checksums.
- M14.T4: Write files atomically.
- M14.T5: Retain Apache license text.
- M14.T6: Record provenance in a runtime manifest.
- State rule: do not publish partial fast language data changes as a successful completed operation.
- Resource rule: include allocations and child processes used by fast language data in the selected edition budget.
- Failure rule: preserve the current document when fast language data cannot complete safely.
- Cancellation rule: dispose transient work owned by fast language data before signaling a terminal state.
- M14.V1: Detect a modified download.
- M14.V2: Use both languages together.
- M14.V3: Work with Arabic-only recognition.
- M14.V4: Build without full language catalog.
- Principal risk: An upstream moving branch cannot provide reproducible assets.
- Evidence gate: record concrete validation of fast language data in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit fast language data for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the fast language data changes in a coherent tested git iteration and push it.

### M15 — Best language data
- Responsibility: Offer slower high-quality Tesseract models for larger tiers.
- Primary implementation location: `scripts/prepare_runtime.py`.
- Input contract: accept only validated values at the boundary of best language data.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep best language data independent of unrelated UI and inference implementations.
- M15.T1: Pin tessdata_best revision.
- M15.T2: Keep fast and best in distinct directories.
- M15.T3: Enable best only in permitted editions.
- M15.T4: Expose installation size before download.
- M15.T5: Load one model set per subprocess.
- M15.T6: Retain the same engine result contract.
- State rule: do not publish partial best language data changes as a successful completed operation.
- Resource rule: include allocations and child processes used by best language data in the selected edition budget.
- Failure rule: preserve the current document when best language data cannot complete safely.
- Cancellation rule: dispose transient work owned by best language data before signaling a terminal state.
- M15.V1: Switch sets without mixing files.
- M15.V2: Keep Pocket on fast data.
- M15.V3: Handle partial installation.
- M15.V4: Measure best-model peak separately.
- Principal risk: Better model data can be slower and more memory hungry.
- Evidence gate: record concrete validation of best language data in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit best language data for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the best language data changes in a coherent tested git iteration and push it.

### M16 — Segmentation modes
- Responsibility: Expose understandable page-layout choices.
- Primary implementation location: `ocready/engines/tesseract.py`.
- Input contract: accept only validated values at the boundary of segmentation modes.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep segmentation modes independent of unrelated UI and inference implementations.
- M16.T1: Provide Automatic page mode.
- M16.T2: Provide Single block mode.
- M16.T3: Provide Sparse screenshot mode.
- M16.T4: Map labels to explicit Tesseract PSM values.
- M16.T5: Persist the last intentional choice.
- M16.T6: Include the mode in exported metadata.
- State rule: do not publish partial segmentation modes changes as a successful completed operation.
- Resource rule: include allocations and child processes used by segmentation modes in the selected edition budget.
- Failure rule: preserve the current document when segmentation modes cannot complete safely.
- Cancellation rule: dispose transient work owned by segmentation modes before signaling a terminal state.
- M16.V1: Read a single paragraph.
- M16.V2: Read scattered UI labels.
- M16.V3: Read an Arabic block.
- M16.V4: Avoid treating a mode as a different model.
- Principal risk: One segmentation setting does not work for every image.
- Evidence gate: record concrete validation of segmentation modes in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit segmentation modes for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the segmentation modes changes in a coherent tested git iteration and push it.

### M17 — TSV parser
- Responsibility: Convert real OCR rows into bounded word and line records.
- Primary implementation location: `ocready/core/text.py`.
- Input contract: accept only validated values at the boundary of tsv parser.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep tsv parser independent of unrelated UI and inference implementations.
- M17.T1: Parse tab-separated output with named columns.
- M17.T2: Ignore non-word hierarchy rows.
- M17.T3: Group by page block paragraph and line.
- M17.T4: Preserve logical recognition order.
- M17.T5: Compute confidence over real words only.
- M17.T6: Attach character ranges to joined text.
- State rule: do not publish partial tsv parser changes as a successful completed operation.
- Resource rule: include allocations and child processes used by tsv parser in the selected edition budget.
- Failure rule: preserve the current document when tsv parser cannot complete safely.
- Cancellation rule: dispose transient work owned by tsv parser before signaling a terminal state.
- M17.V1: Parse malformed numeric fields safely.
- M17.V2: Handle empty TSV.
- M17.V3: Keep mixed Arabic and Latin words.
- M17.V4: Highlight the intended text range.
- Principal risk: Sorting Arabic words by x coordinate reverses logical order.
- Evidence gate: record concrete validation of tsv parser in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit tsv parser for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the tsv parser changes in a coherent tested git iteration and push it.

### M18 — Arabic text behavior
- Responsibility: Preserve correct shaping and logical Unicode order.
- Primary implementation location: `ocready/ui/editor.py`.
- Input contract: accept only validated values at the boundary of arabic text behavior.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep arabic text behavior independent of unrelated UI and inference implementations.
- M18.T1: Use Qt native text shaping.
- M18.T2: Offer automatic paragraph direction.
- M18.T3: Offer explicit right-to-left direction.
- M18.T4: Keep Arabic diacritics and tatweel unchanged.
- M18.T5: Preserve Arabic-Indic and Western digits.
- M18.T6: Avoid destructive normalization by default.
- State rule: do not publish partial arabic text behavior changes as a successful completed operation.
- Resource rule: include allocations and child processes used by arabic text behavior in the selected edition budget.
- Failure rule: preserve the current document when arabic text behavior cannot complete safely.
- Cancellation rule: dispose transient work owned by arabic text behavior before signaling a terminal state.
- M18.V1: Copy Arabic with correct Unicode order.
- M18.V2: Edit mixed email addresses and Arabic.
- M18.V3: Display lam-alef correctly.
- M18.V4: Round-trip newlines and punctuation.
- Principal risk: Visually correct glyphs can still have incorrect logical order.
- Evidence gate: record concrete validation of arabic text behavior in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit arabic text behavior for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the arabic text behavior changes in a coherent tested git iteration and push it.

### M19 — English and mixed text
- Responsibility: Keep practical copied text intact.
- Primary implementation location: `ocready/core/text.py`.
- Input contract: accept only validated values at the boundary of english and mixed text.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep english and mixed text independent of unrelated UI and inference implementations.
- M19.T1: Preserve case.
- M19.T2: Preserve URLs and email addresses.
- M19.T3: Keep code punctuation.
- M19.T4: Offer optional line-break cleanup.
- M19.T5: Keep paragraph boundaries.
- M19.T6: Never translate OCR text unless requested.
- State rule: do not publish partial english and mixed text changes as a successful completed operation.
- Resource rule: include allocations and child processes used by english and mixed text in the selected edition budget.
- Failure rule: preserve the current document when english and mixed text cannot complete safely.
- Cancellation rule: dispose transient work owned by english and mixed text before signaling a terminal state.
- M19.V1: Copy a URL intact.
- M19.V2: Read a code snippet.
- M19.V3: Keep bilingual parentheses.
- M19.V4: Undo an optional cleanup.
- Principal risk: Well-meant cleanup can corrupt code and identifiers.
- Evidence gate: record concrete validation of english and mixed text in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit english and mixed text for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the english and mixed text changes in a coherent tested git iteration and push it.

### M20 — Image canvas
- Responsibility: Provide a clear original-image pane with word selection.
- Primary implementation location: `ocready/ui/canvas.py`.
- Input contract: accept only validated values at the boundary of image canvas.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep image canvas independent of unrelated UI and inference implementations.
- M20.T1: Fit the image when first opened.
- M20.T2: Allow wheel zoom.
- M20.T3: Allow drag panning.
- M20.T4: Render source word boxes only when available.
- M20.T5: Provide a processed-image toggle.
- M20.T6: Draw crop and selection feedback distinctly.
- State rule: do not publish partial image canvas changes as a successful completed operation.
- Resource rule: include allocations and child processes used by image canvas in the selected edition budget.
- Failure rule: preserve the current document when image canvas cannot complete safely.
- Cancellation rule: dispose transient work owned by image canvas before signaling a terminal state.
- M20.V1: Fit portrait and landscape inputs.
- M20.V2: Zoom without box drift.
- M20.V3: Pan without selecting words accidentally.
- M20.V4: Keep a usable minimum pane width.
- Principal risk: Scaled or high-DPI canvases can misalign overlays.
- Evidence gate: record concrete validation of image canvas in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit image canvas for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the image canvas changes in a coherent tested git iteration and push it.

### M21 — Source highlighting
- Responsibility: Make text in the picture directly usable.
- Primary implementation location: `ocready/ui/canvas.py`.
- Input contract: accept only validated values at the boundary of source highlighting.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep source highlighting independent of unrelated UI and inference implementations.
- M21.T1: Click a word to select it.
- M21.T2: Drag a region to collect intersecting words.
- M21.T3: Keep selection in OCR reading order.
- M21.T4: Highlight corresponding text in the editor.
- M21.T5: Offer Copy selection near the image.
- M21.T6: Show no fabricated boxes for vision-only text.
- State rule: do not publish partial source highlighting changes as a successful completed operation.
- Resource rule: include allocations and child processes used by source highlighting in the selected edition budget.
- Failure rule: preserve the current document when source highlighting cannot complete safely.
- Cancellation rule: dispose transient work owned by source highlighting before signaling a terminal state.
- M21.V1: Select an Arabic line from the picture.
- M21.V2: Select multiple English words.
- M21.V3: Clear selection with Escape.
- M21.V4: Copy only the selected source text.
- Principal risk: Vision model prose cannot be assigned invented coordinates.
- Evidence gate: record concrete validation of source highlighting in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit source highlighting for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the source highlighting changes in a coherent tested git iteration and push it.

### M22 — Editor-to-source linking
- Responsibility: Connect editor selection to verified word locations.
- Primary implementation location: `ocready/ui/editor.py`.
- Input contract: accept only validated values at the boundary of editor-to-source linking.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep editor-to-source linking independent of unrelated UI and inference implementations.
- M22.T1: Store start and end offsets for words.
- M22.T2: Highlight matching boxes on cursor selection.
- M22.T3: Invalidate offsets after manual edits.
- M22.T4: Keep whole-text copy available after editing.
- M22.T5: Expose a source-linked status.
- M22.T6: Allow re-recognition to restore linking.
- State rule: do not publish partial editor-to-source linking changes as a successful completed operation.
- Resource rule: include allocations and child processes used by editor-to-source linking in the selected edition budget.
- Failure rule: preserve the current document when editor-to-source linking cannot complete safely.
- Cancellation rule: dispose transient work owned by editor-to-source linking before signaling a terminal state.
- M22.V1: Select a word in text and see its box.
- M22.V2: Edit before a word without stale linking.
- M22.V3: Keep Unicode character ranges consistent.
- M22.V4: Avoid mixing bytes and Python code points.
- Principal risk: Qt cursor offsets use UTF-16 units for non-BMP characters.
- Evidence gate: record concrete validation of editor-to-source linking in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit editor-to-source linking for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the editor-to-source linking changes in a coherent tested git iteration and push it.

### M23 — Text editor
- Responsibility: Provide familiar editing and export actions.
- Primary implementation location: `ocready/ui/editor.py`.
- Input contract: accept only validated values at the boundary of text editor.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep text editor independent of unrelated UI and inference implementations.
- M23.T1: Support native undo and redo.
- M23.T2: Support select all.
- M23.T3: Support keyboard copy and paste.
- M23.T4: Offer text size controls.
- M23.T5: Show word and character counts.
- M23.T6: Export UTF-8 plain text.
- State rule: do not publish partial text editor changes as a successful completed operation.
- Resource rule: include allocations and child processes used by text editor in the selected edition budget.
- Failure rule: preserve the current document when text editor cannot complete safely.
- Cancellation rule: dispose transient work owned by text editor before signaling a terminal state.
- M23.V1: Undo an edit.
- M23.V2: Save Arabic text correctly.
- M23.V3: Copy without adding hidden marks.
- M23.V4: Keep selection after a copy action.
- Principal risk: Editor changes must not overwrite the source OCR record silently.
- Evidence gate: record concrete validation of text editor in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit text editor for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the text editor changes in a coherent tested git iteration and push it.

### M24 — Local vision adapter
- Responsibility: Run a local llama.cpp-compatible multimodal model.
- Primary implementation location: `ocready/engines/vision.py`.
- Input contract: accept only validated values at the boundary of local vision adapter.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep local vision adapter independent of unrelated UI and inference implementations.
- M24.T1: Accept an explicit runner executable.
- M24.T2: Require model GGUF and vision projector.
- M24.T3: Pass image input through a private temporary file.
- M24.T4: Use a transcription-only prompt by default.
- M24.T5: Keep generation token count bounded.
- M24.T6: Terminate the process tree on cancellation.
- State rule: do not publish partial local vision adapter changes as a successful completed operation.
- Resource rule: include allocations and child processes used by local vision adapter in the selected edition budget.
- Failure rule: preserve the current document when local vision adapter cannot complete safely.
- Cancellation rule: dispose transient work owned by local vision adapter before signaling a terminal state.
- M24.V1: Reject a text-only configuration.
- M24.V2: Read output without prompt echo.
- M24.V3: Recognize a known fixture on CPU.
- M24.V4: Preserve a clear runner error.
- Principal risk: Vision architecture and projector must match the runner version.
- Evidence gate: record concrete validation of local vision adapter in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit local vision adapter for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the local vision adapter changes in a coherent tested git iteration and push it.

### M25 — CUDA policy
- Responsibility: Prefer acceleration only when it is actually usable.
- Primary implementation location: `ocready/engines/vision.py`.
- Input contract: accept only validated values at the boundary of cuda policy.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep cuda policy independent of unrelated UI and inference implementations.
- M25.T1: Expose Auto CPU and CUDA preferences.
- M25.T2: Check runner-reported device support.
- M25.T3: Use GPU layers only for a CUDA-capable runner.
- M25.T4: Disable projector offload on CPU.
- M25.T5: Retry once on CPU after a GPU initialization failure.
- M25.T6: Record the backend actually used.
- State rule: do not publish partial cuda policy changes as a successful completed operation.
- Resource rule: include allocations and child processes used by cuda policy in the selected edition budget.
- Failure rule: preserve the current document when cuda policy cannot complete safely.
- Cancellation rule: dispose transient work owned by cuda policy before signaling a terminal state.
- M25.V1: Run on a machine without NVIDIA drivers.
- M25.V2: Simulate a CUDA initialization failure.
- M25.V3: Avoid retrying cancellation as CPU work.
- M25.V4: Show CPU fallback in the result.
- Principal risk: Presence of nvidia-smi alone does not prove the runner supports CUDA.
- Evidence gate: record concrete validation of cuda policy in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit cuda policy for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the cuda policy changes in a coherent tested git iteration and push it.

### M26 — Model admission
- Responsibility: Permit one or many methods according to edition and memory evidence.
- Primary implementation location: `ocready/core/models.py`.
- Input contract: accept only validated values at the boundary of model admission.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep model admission independent of unrelated UI and inference implementations.
- M26.T1: Use a local JSON model manifest.
- M26.T2: Record model and projector paths separately.
- M26.T3: Record estimated total inference working set.
- M26.T4: Add UI and image memory reserves.
- M26.T5: Reject a pack that exceeds the selected tier.
- M26.T6: Show measured versus estimated status.
- State rule: do not publish partial model admission changes as a successful completed operation.
- Resource rule: include allocations and child processes used by model admission in the selected edition budget.
- Failure rule: preserve the current document when model admission cannot complete safely.
- Cancellation rule: dispose transient work owned by model admission before signaling a terminal state.
- M26.V1: Reject an oversized pack.
- M26.V2: Reject a missing projector.
- M26.V3: Allow a permitted single-method pack.
- M26.V4: Allow multiple installed packs with serial loading.
- Principal risk: Quantized weights exclude vision encoder workspace and KV cache.
- Evidence gate: record concrete validation of model admission in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit model admission for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the model admission changes in a coherent tested git iteration and push it.

### M27 — Model installer
- Responsibility: Make offline model selection understandable and reversible.
- Primary implementation location: `ocready/core/models.py`.
- Input contract: accept only validated values at the boundary of model installer.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep model installer independent of unrelated UI and inference implementations.
- M27.T1: Provide file pickers for local GGUF files.
- M27.T2: Validate paths before saving settings.
- M27.T3: Show model source and license fields.
- M27.T4: Never execute downloaded installers.
- M27.T5: Permit deleting a configuration without deleting weights.
- M27.T6: Explain unsupported architectures.
- State rule: do not publish partial model installer changes as a successful completed operation.
- Resource rule: include allocations and child processes used by model installer in the selected edition budget.
- Failure rule: preserve the current document when model installer cannot complete safely.
- Cancellation rule: dispose transient work owned by model installer before signaling a terminal state.
- M27.V1: Configure files in paths with spaces.
- M27.V2: Reject a directory in place of a model.
- M27.V3: Keep the app usable without any VLM.
- M27.V4: Recover from a missing model after restart.
- Principal risk: Automatic large model downloads can surprise users and consume storage.
- Evidence gate: record concrete validation of model installer in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit model installer for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the model installer changes in a coherent tested git iteration and push it.

### M28 — LLM result integrity
- Responsibility: Keep generative transcription distinct from located OCR.
- Primary implementation location: `ocready/engines/vision.py`.
- Input contract: accept only validated values at the boundary of llm result integrity.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep llm result integrity independent of unrelated UI and inference implementations.
- M28.T1: Use temperature zero.
- M28.T2: Request only visible text.
- M28.T3: Treat image instructions as document content.
- M28.T4: Keep hallucination-sensitive output marked as AI transcription.
- M28.T5: Do not claim calibrated confidence.
- M28.T6: Keep classical results available for comparison.
- State rule: do not publish partial llm result integrity changes as a successful completed operation.
- Resource rule: include allocations and child processes used by llm result integrity in the selected edition budget.
- Failure rule: preserve the current document when llm result integrity cannot complete safely.
- Cancellation rule: dispose transient work owned by llm result integrity before signaling a terminal state.
- M28.V1: Handle a blank image without endless generation.
- M28.V2: Limit response length.
- M28.V3: Keep source text unchanged in comparison.
- M28.V4: Do not relabel generated text as verified geometry.
- Principal risk: No prompt can guarantee a generative model never hallucinates.
- Evidence gate: record concrete validation of llm result integrity in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit llm result integrity for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the llm result integrity changes in a coherent tested git iteration and push it.

### M29 — Engine registry
- Responsibility: Support replaceable methods without rewriting the UI.
- Primary implementation location: `ocready/engines/registry.py`.
- Input contract: accept only validated values at the boundary of engine registry.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep engine registry independent of unrelated UI and inference implementations.
- M29.T1: Define available methods as metadata.
- M29.T2: Declare language capabilities.
- M29.T3: Declare tier eligibility.
- M29.T4: Report installation readiness.
- M29.T5: Dispatch through a stable request contract.
- M29.T6: Allow one installed method to be the entire edition.
- State rule: do not publish partial engine registry changes as a successful completed operation.
- Resource rule: include allocations and child processes used by engine registry in the selected edition budget.
- Failure rule: preserve the current document when engine registry cannot complete safely.
- Cancellation rule: dispose transient work owned by engine registry before signaling a terminal state.
- M29.V1: List missing engines with reasons.
- M29.V2: Select an available method.
- M29.V3: Reject an unknown method identifier.
- M29.V4: Keep runner details out of the basic flow.
- Principal risk: Capability metadata can drift from the actual installed runtime.
- Evidence gate: record concrete validation of engine registry in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit engine registry for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the engine registry changes in a coherent tested git iteration and push it.

### M30 — Background work
- Responsibility: Keep recognition off the UI thread.
- Primary implementation location: `ocready/core/worker.py`.
- Input contract: accept only validated values at the boundary of background work.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep background work independent of unrelated UI and inference implementations.
- M30.T1: Use one recognition worker at a time.
- M30.T2: Send progress through Qt signals.
- M30.T3: Carry immutable request parameters.
- M30.T4: Avoid creating widgets in workers.
- M30.T5: Always emit a terminal state.
- M30.T6: Suppress outdated result delivery.
- State rule: do not publish partial background work changes as a successful completed operation.
- Resource rule: include allocations and child processes used by background work in the selected edition budget.
- Failure rule: preserve the current document when background work cannot complete safely.
- Cancellation rule: dispose transient work owned by background work before signaling a terminal state.
- M30.V1: Move the window during OCR.
- M30.V2: Cancel during a slow pass.
- M30.V3: Close during an active job.
- M30.V4: Receive an exception as a readable error.
- Principal risk: Destroying a running Qt thread can crash the process.
- Evidence gate: record concrete validation of background work in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit background work for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the background work changes in a coherent tested git iteration and push it.

### M31 — Cancellation and timeouts
- Responsibility: Bound every child process and dispose it reliably.
- Primary implementation location: `ocready/core/process.py`.
- Input contract: accept only validated values at the boundary of cancellation and timeouts.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep cancellation and timeouts independent of unrelated UI and inference implementations.
- M31.T1: Launch argument arrays with shell disabled.
- M31.T2: Track the process tree.
- M31.T3: Poll cancellation at short intervals.
- M31.T4: Set per-method deadlines.
- M31.T5: Terminate gracefully then kill when needed.
- M31.T6: Bound output capture on disk.
- State rule: do not publish partial cancellation and timeouts changes as a successful completed operation.
- Resource rule: include allocations and child processes used by cancellation and timeouts in the selected edition budget.
- Failure rule: preserve the current document when cancellation and timeouts cannot complete safely.
- Cancellation rule: dispose transient work owned by cancellation and timeouts before signaling a terminal state.
- M31.V1: Cancel Tesseract.
- M31.V2: Cancel a vision runner.
- M31.V3: Kill an unresponsive child.
- M31.V4: Leave no worker after an exception.
- Principal risk: Grandchildren can survive unless process-tree ownership is explicit.
- Evidence gate: record concrete validation of cancellation and timeouts in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit cancellation and timeouts for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the cancellation and timeouts changes in a coherent tested git iteration and push it.

### M32 — Memory governor
- Responsibility: Measure and enforce a whole-process-tree working-set budget.
- Primary implementation location: `ocready/core/memory.py`.
- Input contract: accept only validated values at the boundary of memory governor.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep memory governor independent of unrelated UI and inference implementations.
- M32.T1: Sample application RSS plus descendant RSS.
- M32.T2: Use decimal budget limits.
- M32.T3: Keep a safety reserve before admitting large work.
- M32.T4: Terminate recognition when a tier is exceeded.
- M32.T5: Report the measured observed peak.
- M32.T6: Distinguish polling guardrails from OS-enforced hard limits.
- State rule: do not publish partial memory governor changes as a successful completed operation.
- Resource rule: include allocations and child processes used by memory governor in the selected edition budget.
- Failure rule: preserve the current document when memory governor cannot complete safely.
- Cancellation rule: dispose transient work owned by memory governor before signaling a terminal state.
- M32.V1: Count both parent and child.
- M32.V2: Detect a deliberately allocating fixture.
- M32.V3: Keep cancellation fast under pressure.
- M32.V4: Avoid reporting VRAM as host RAM.
- Principal risk: A sampler can miss brief peaks and cannot guarantee an absolute ceiling.
- Evidence gate: record concrete validation of memory governor in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit memory governor for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the memory governor changes in a coherent tested git iteration and push it.

### M33 — OS hard limits
- Responsibility: Specify stronger release containment for each target OS.
- Primary implementation location: `docs/MEMORY.md`.
- Input contract: accept only validated values at the boundary of os hard limits.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep os hard limits independent of unrelated UI and inference implementations.
- M33.T1: Investigate Windows Job Object memory limits.
- M33.T2: Investigate Linux cgroup v2 delegation.
- M33.T3: Avoid RLIMIT_AS as an RSS substitute.
- M33.T4: Document when no hard limiter is available.
- M33.T5: Keep UI failure recoverable after worker termination.
- M33.T6: Gate strict budget claims on controlled benchmarks.
- State rule: do not publish partial os hard limits changes as a successful completed operation.
- Resource rule: include allocations and child processes used by os hard limits in the selected edition budget.
- Failure rule: preserve the current document when os hard limits cannot complete safely.
- Cancellation rule: dispose transient work owned by os hard limits before signaling a terminal state.
- M33.V1: Run a contained memory spike.
- M33.V2: Record containment support.
- M33.V3: Confirm driver allocations are reported separately.
- M33.V4: Fail a strict certification when containment is absent.
- Principal risk: Unprivileged cgroups are not universally delegated.
- Evidence gate: record concrete validation of os hard limits in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit os hard limits for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the os hard limits changes in a coherent tested git iteration and push it.

### M34 — Settings persistence
- Responsibility: Persist preferences without storing private documents.
- Primary implementation location: `ocready/core/settings.py`.
- Input contract: accept only validated values at the boundary of settings persistence.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep settings persistence independent of unrelated UI and inference implementations.
- M34.T1: Use a platform-specific config directory.
- M34.T2: Version the JSON schema.
- M34.T3: Write atomically.
- M34.T4: Validate edition and engine IDs.
- M34.T5: Store no image bytes or OCR text by default.
- M34.T6: Recover from corrupt settings.
- State rule: do not publish partial settings persistence changes as a successful completed operation.
- Resource rule: include allocations and child processes used by settings persistence in the selected edition budget.
- Failure rule: preserve the current document when settings persistence cannot complete safely.
- Cancellation rule: dispose transient work owned by settings persistence before signaling a terminal state.
- M34.V1: Restart with preferences intact.
- M34.V2: Load an older schema.
- M34.V3: Ignore unknown fields safely.
- M34.V4: Keep a malformed file from crashing startup.
- Principal risk: Persisted machine-specific paths can disappear or become untrusted.
- Evidence gate: record concrete validation of settings persistence in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit settings persistence for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the settings persistence changes in a coherent tested git iteration and push it.

### M35 — Visual design system
- Responsibility: Create a calm polished desktop interface.
- Primary implementation location: `ocready/ui/theme.py`.
- Input contract: accept only validated values at the boundary of visual design system.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep visual design system independent of unrelated UI and inference implementations.
- M35.T1: Use a warm neutral canvas with restrained blue accents.
- M35.T2: Give the main action one clear emphasis.
- M35.T3: Use consistent spacing and corner radii.
- M35.T4: Separate toolbar workspace and status regions.
- M35.T5: Keep labels readable at standard scaling.
- M35.T6: Offer light and dark appearance.
- State rule: do not publish partial visual design system changes as a successful completed operation.
- Resource rule: include allocations and child processes used by visual design system in the selected edition budget.
- Failure rule: preserve the current document when visual design system cannot complete safely.
- Cancellation rule: dispose transient work owned by visual design system before signaling a terminal state.
- M35.V1: Inspect at 100 percent scale.
- M35.V2: Inspect at 200 percent scale.
- M35.V3: Read disabled control labels.
- M35.V4: Distinguish focus from hover.
- Principal risk: A stylesheet can accidentally make native widgets inaccessible.
- Evidence gate: record concrete validation of visual design system in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit visual design system for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the visual design system changes in a coherent tested git iteration and push it.

### M36 — Main workspace
- Responsibility: Keep image and editable text side by side.
- Primary implementation location: `ocready/ui/window.py`.
- Input contract: accept only validated values at the boundary of main workspace.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep main workspace independent of unrelated UI and inference implementations.
- M36.T1: Use a horizontal resizable splitter.
- M36.T2: Put capture paste and open at the top.
- M36.T3: Keep engine language and edition controls grouped.
- M36.T4: Put Recognize near the input choices.
- M36.T5: Show a useful empty state in both panes.
- M36.T6: Preserve window dimensions between launches.
- State rule: do not publish partial main workspace changes as a successful completed operation.
- Resource rule: include allocations and child processes used by main workspace in the selected edition budget.
- Failure rule: preserve the current document when main workspace cannot complete safely.
- Cancellation rule: dispose transient work owned by main workspace before signaling a terminal state.
- M36.V1: Resize each pane.
- M36.V2: Use a narrow laptop window.
- M36.V3: Complete a task without opening settings.
- M36.V4: See status while recognition is active.
- Principal risk: Too many expert controls can overwhelm the primary copy workflow.
- Evidence gate: record concrete validation of main workspace in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit main workspace for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the main workspace changes in a coherent tested git iteration and push it.

### M37 — Keyboard accessibility
- Responsibility: Support a complete workflow without a mouse.
- Primary implementation location: `ocready/ui/window.py`.
- Input contract: accept only validated values at the boundary of keyboard accessibility.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep keyboard accessibility independent of unrelated UI and inference implementations.
- M37.T1: Use Ctrl+O for open.
- M37.T2: Use Ctrl+Shift+V for paste image.
- M37.T3: Use Ctrl+Return for recognize.
- M37.T4: Use Ctrl+Shift+C for copy all.
- M37.T5: Use Escape for cancellation and selection clearing.
- M37.T6: Provide accessible names and tooltips.
- State rule: do not publish partial keyboard accessibility changes as a successful completed operation.
- Resource rule: include allocations and child processes used by keyboard accessibility in the selected edition budget.
- Failure rule: preserve the current document when keyboard accessibility cannot complete safely.
- Cancellation rule: dispose transient work owned by keyboard accessibility before signaling a terminal state.
- M37.V1: Tab to every primary control.
- M37.V2: Read shortcut help.
- M37.V3: Keep editor native shortcuts intact.
- M37.V4: Show visible keyboard focus.
- Principal risk: Global desktop shortcuts can conflict with local app shortcuts.
- Evidence gate: record concrete validation of keyboard accessibility in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit keyboard accessibility for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the keyboard accessibility changes in a coherent tested git iteration and push it.

### M38 — Error and status design
- Responsibility: Make failure actionable and preserve user work.
- Primary implementation location: `ocready/ui/window.py`.
- Input contract: accept only validated values at the boundary of error and status design.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep error and status design independent of unrelated UI and inference implementations.
- M38.T1: Use inline status for ordinary failures.
- M38.T2: Explain missing language assets.
- M38.T3: Explain incompatible vision configuration.
- M38.T4: Offer retry after failure.
- M38.T5: Avoid stack traces in the basic UI.
- M38.T6: Keep a diagnostics detail view.
- State rule: do not publish partial error and status design changes as a successful completed operation.
- Resource rule: include allocations and child processes used by error and status design in the selected edition budget.
- Failure rule: preserve the current document when error and status design cannot complete safely.
- Cancellation rule: dispose transient work owned by error and status design before signaling a terminal state.
- M38.V1: Read a corrupt-image error.
- M38.V2: Recover after a missing runner.
- M38.V3: Retry without reloading the image.
- M38.V4: Keep edited text after a failed recognition.
- Principal risk: Friendly errors can hide useful details unless diagnostics remain available.
- Evidence gate: record concrete validation of error and status design in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit error and status design for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the error and status design changes in a coherent tested git iteration and push it.

### M39 — Diagnostics
- Responsibility: Report runtime readiness without exposing document content.
- Primary implementation location: `ocready/core/diagnostics.py`.
- Input contract: accept only validated values at the boundary of diagnostics.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep diagnostics independent of unrelated UI and inference implementations.
- M39.T1: Show application and Qt versions.
- M39.T2: Show edition and memory policy.
- M39.T3: Show OCR executable version.
- M39.T4: Show installed language sets.
- M39.T5: Show selected vision runner backend.
- M39.T6: Export diagnostics without source paths when possible.
- State rule: do not publish partial diagnostics changes as a successful completed operation.
- Resource rule: include allocations and child processes used by diagnostics in the selected edition budget.
- Failure rule: preserve the current document when diagnostics cannot complete safely.
- Cancellation rule: dispose transient work owned by diagnostics before signaling a terminal state.
- M39.V1: Diagnose a missing engine.
- M39.V2: Distinguish CPU from CUDA execution.
- M39.V3: Avoid including OCR text.
- M39.V4: Keep access tokens out of diagnostics.
- Principal risk: Logs and temporary filenames can reveal sensitive document information.
- Evidence gate: record concrete validation of diagnostics in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit diagnostics for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the diagnostics changes in a coherent tested git iteration and push it.

### M40 — Command-line interface
- Responsibility: Make the same OCR pipeline useful in scripts and validation.
- Primary implementation location: `ocready/__main__.py`.
- Input contract: accept only validated values at the boundary of command-line interface.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep command-line interface independent of unrelated UI and inference implementations.
- M40.T1: Provide --help.
- M40.T2: Provide --version.
- M40.T3: Provide --diagnostics.
- M40.T4: Provide headless recognize with JSON output.
- M40.T5: Use explicit exit codes.
- M40.T6: Allow selecting edition language and method.
- State rule: do not publish partial command-line interface changes as a successful completed operation.
- Resource rule: include allocations and child processes used by command-line interface in the selected edition budget.
- Failure rule: preserve the current document when command-line interface cannot complete safely.
- Cancellation rule: dispose transient work owned by command-line interface before signaling a terminal state.
- M40.V1: Run OCR without a display server.
- M40.V2: Parse JSON stdout.
- M40.V3: Keep progress on stderr.
- M40.V4: Use filenames beginning with a dash safely.
- Principal risk: Importing UI modules too early can require a display in CLI mode.
- Evidence gate: record concrete validation of command-line interface in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit command-line interface for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the command-line interface changes in a coherent tested git iteration and push it.

### M41 — Runtime preparation
- Responsibility: Collect redistributable OCR binaries and assets reproducibly.
- Primary implementation location: `scripts/prepare_runtime.py`.
- Input contract: accept only validated values at the boundary of runtime preparation.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep runtime preparation independent of unrelated UI and inference implementations.
- M41.T1: Support Debian package extraction without root.
- M41.T2: Support Windows Tesseract package collection.
- M41.T3: Collect dependency libraries with a manifest.
- M41.T4: Exclude system loaders from copied payloads.
- M41.T5: Retain third-party copyright files.
- M41.T6: Validate the prepared executable before packaging.
- State rule: do not publish partial runtime preparation changes as a successful completed operation.
- Resource rule: include allocations and child processes used by runtime preparation in the selected edition budget.
- Failure rule: preserve the current document when runtime preparation cannot complete safely.
- Cancellation rule: dispose transient work owned by runtime preparation before signaling a terminal state.
- M41.V1: Prepare on a clean CI runner.
- M41.V2: Fail on a missing DLL.
- M41.V3: Verify language checksums.
- M41.V4: Run OCR from the prepared tree.
- Principal risk: Bundling the wrong C library can break Linux portability.
- Evidence gate: record concrete validation of runtime preparation in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit runtime preparation for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the runtime preparation changes in a coherent tested git iteration and push it.

### M42 — Linux onefile build
- Responsibility: Produce one compiled executable including Qt and classical OCR.
- Primary implementation location: `scripts/build.py`.
- Input contract: accept only validated values at the boundary of linux onefile build.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep linux onefile build independent of unrelated UI and inference implementations.
- M42.T1: Use Nuitka standalone then onefile mode.
- M42.T2: Embed runtime and language data.
- M42.T3: Include the Qt platform plugins actually required.
- M42.T4: Preserve executable bits on the OCR child.
- M42.T5: Use a private extraction location.
- M42.T6: Smoke-test the resulting file without the development environment.
- State rule: do not publish partial linux onefile build changes as a successful completed operation.
- Resource rule: include allocations and child processes used by linux onefile build in the selected edition budget.
- Failure rule: preserve the current document when linux onefile build cannot complete safely.
- Cancellation rule: dispose transient work owned by linux onefile build before signaling a terminal state.
- M42.V1: Run compiled CLI diagnostics.
- M42.V2: Recognize a fixture from the binary.
- M42.V3: Launch on X11.
- M42.V4: Exercise Wayland on a compatible machine.
- Principal risk: Building on a new glibc can prevent execution on older distributions.
- Evidence gate: record concrete validation of linux onefile build in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit linux onefile build for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the linux onefile build changes in a coherent tested git iteration and push it.

### M43 — Windows onefile build
- Responsibility: Produce a compiled Windows executable with no Python installation requirement.
- Primary implementation location: `scripts/build.py`.
- Input contract: accept only validated values at the boundary of windows onefile build.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep windows onefile build independent of unrelated UI and inference implementations.
- M43.T1: Build on a Windows GitHub runner.
- M43.T2: Include Qt platform DLLs.
- M43.T3: Include the OCR executable and dependency DLLs.
- M43.T4: Use a GUI entry point without a console window.
- M43.T5: Keep CLI diagnostics usable through an output file if needed.
- M43.T6: Scan the artifact for missing runtime files.
- State rule: do not publish partial windows onefile build changes as a successful completed operation.
- Resource rule: include allocations and child processes used by windows onefile build in the selected edition budget.
- Failure rule: preserve the current document when windows onefile build cannot complete safely.
- Cancellation rule: dispose transient work owned by windows onefile build before signaling a terminal state.
- M43.V1: Start on a clean Windows 11 machine.
- M43.V2: Read Arabic filenames.
- M43.V3: Paste a snip from Snipping Tool.
- M43.V4: Run offline recognition.
- Principal risk: A green build does not replace a real Windows 11 usability test.
- Evidence gate: record concrete validation of windows onefile build in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit windows onefile build for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the windows onefile build changes in a coherent tested git iteration and push it.

### M44 — Build profiles
- Responsibility: Allow edition and engine-subset packaging.
- Primary implementation location: `scripts/build.py`.
- Input contract: accept only validated values at the boundary of build profiles.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep build profiles independent of unrelated UI and inference implementations.
- M44.T1: Select Pocket Everyday or Studio at build time.
- M44.T2: Include only requested OCR model sets.
- M44.T3: Optionally embed a vetted vision runner.
- M44.T4: Allow local external GGUF packs.
- M44.T5: Emit a build manifest inside the executable.
- M44.T6: Name artifacts by platform edition and architecture.
- State rule: do not publish partial build profiles changes as a successful completed operation.
- Resource rule: include allocations and child processes used by build profiles in the selected edition budget.
- Failure rule: preserve the current document when build profiles cannot complete safely.
- Cancellation rule: dispose transient work owned by build profiles before signaling a terminal state.
- M44.V1: Build a classical-only Pocket edition.
- M44.V2: Build an Everyday fast+best edition.
- M44.V3: Build a Studio with local vision adapter.
- M44.V4: Verify excluded assets are absent.
- Principal risk: Shipping all models defeats a small-download edition even if RAM is bounded.
- Evidence gate: record concrete validation of build profiles in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit build profiles for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the build profiles changes in a coherent tested git iteration and push it.

### M45 — Continuous integration
- Responsibility: Run meaningful source checks for Linux and Windows.
- Primary implementation location: `.github/workflows/ci.yml`.
- Input contract: accept only validated values at the boundary of continuous integration.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep continuous integration independent of unrelated UI and inference implementations.
- M45.T1: Install locked dependencies.
- M45.T2: Run unit and pipeline tests.
- M45.T3: Run headless UI smoke tests.
- M45.T4: Prepare Arabic and English runtime assets.
- M45.T5: Exercise real OCR fixture recognition.
- M45.T6: Upload diagnostics and test reports on failure.
- State rule: do not publish partial continuous integration changes as a successful completed operation.
- Resource rule: include allocations and child processes used by continuous integration in the selected edition budget.
- Failure rule: preserve the current document when continuous integration cannot complete safely.
- Cancellation rule: dispose transient work owned by continuous integration before signaling a terminal state.
- M45.V1: Fail on a deliberate parser regression.
- M45.V2: Run Windows path tests.
- M45.V3: Run Arabic OCR assertions.
- M45.V4: Avoid skipping every native-engine test silently.
- Principal risk: CI image differences may hide issues found on user desktops.
- Evidence gate: record concrete validation of continuous integration in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit continuous integration for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the continuous integration changes in a coherent tested git iteration and push it.

### M46 — Release pipeline
- Responsibility: Publish reviewable compiled artifacts and checksums.
- Primary implementation location: `.github/workflows/release.yml`.
- Input contract: accept only validated values at the boundary of release pipeline.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep release pipeline independent of unrelated UI and inference implementations.
- M46.T1: Support manual release builds.
- M46.T2: Compile Linux and Windows separately.
- M46.T3: Build the three edition profiles.
- M46.T4: Generate SHA256 sums.
- M46.T5: Attach notices and build manifests.
- M46.T6: Label unverified tiers and models explicitly.
- State rule: do not publish partial release pipeline changes as a successful completed operation.
- Resource rule: include allocations and child processes used by release pipeline in the selected edition budget.
- Failure rule: preserve the current document when release pipeline cannot complete safely.
- Cancellation rule: dispose transient work owned by release pipeline before signaling a terminal state.
- M46.V1: Download each artifact.
- M46.V2: Check its hash.
- M46.V3: Recognize from the packaged artifact.
- M46.V4: Keep unverified builds marked prerelease.
- Principal risk: Compilation alone does not verify memory accuracy or usability.
- Evidence gate: record concrete validation of release pipeline in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit release pipeline for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the release pipeline changes in a coherent tested git iteration and push it.

### M47 — Accuracy corpus
- Responsibility: Establish a small transparent bilingual quality baseline.
- Primary implementation location: `tests/fixtures`.
- Input contract: accept only validated values at the boundary of accuracy corpus.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep accuracy corpus independent of unrelated UI and inference implementations.
- M47.T1: Generate clean English screenshots.
- M47.T2: Generate shaped Arabic screenshots.
- M47.T3: Include mixed-direction text and digits.
- M47.T4: Include dark background and low contrast.
- M47.T5: Include blank and malformed images.
- M47.T6: Keep expected text and licenses with fixtures.
- State rule: do not publish partial accuracy corpus changes as a successful completed operation.
- Resource rule: include allocations and child processes used by accuracy corpus in the selected edition budget.
- Failure rule: preserve the current document when accuracy corpus cannot complete safely.
- Cancellation rule: dispose transient work owned by accuracy corpus before signaling a terminal state.
- M47.V1: Measure Arabic character error rate.
- M47.V2: Measure English word error rate.
- M47.V3: Compare preprocessing against baseline.
- M47.V4: Record known failures.
- Principal risk: Synthetic fixtures do not represent scanned books or handwriting.
- Evidence gate: record concrete validation of accuracy corpus in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit accuracy corpus for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the accuracy corpus changes in a coherent tested git iteration and push it.

### M48 — Memory benchmark
- Responsibility: Measure each edition over representative full workflows.
- Primary implementation location: `scripts/benchmark.py`.
- Input contract: accept only validated values at the boundary of memory benchmark.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep memory benchmark independent of unrelated UI and inference implementations.
- M48.T1: Launch a fresh process per scenario.
- M48.T2: Measure parent and child RSS.
- M48.T3: Include image decode preprocessing and OCR.
- M48.T4: Run repeated documents for leak detection.
- M48.T5: Record OS CPU runner model and image dimensions.
- M48.T6: Emit machine-readable pass or fail results.
- State rule: do not publish partial memory benchmark changes as a successful completed operation.
- Resource rule: include allocations and child processes used by memory benchmark in the selected edition budget.
- Failure rule: preserve the current document when memory benchmark cannot complete safely.
- Cancellation rule: dispose transient work owned by memory benchmark before signaling a terminal state.
- M48.V1: Catch a budget violation.
- M48.V2: Count onefile launcher overhead where applicable.
- M48.V3: Report cold and warm runs.
- M48.V4: Keep benchmark artifacts reproducible.
- Principal risk: Peak sampling is evidence with uncertainty rather than a universal guarantee.
- Evidence gate: record concrete validation of memory benchmark in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit memory benchmark for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the memory benchmark changes in a coherent tested git iteration and push it.

### M49 — Performance and responsiveness
- Responsibility: Protect interaction quality while improving recognition.
- Primary implementation location: `docs/BENCHMARKS.md`.
- Input contract: accept only validated values at the boundary of performance and responsiveness.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep performance and responsiveness independent of unrelated UI and inference implementations.
- M49.T1: Measure capture-to-text latency.
- M49.T2: Measure cancellation latency.
- M49.T3: Measure first-launch extraction time.
- M49.T4: Keep large decoding off the UI path where feasible.
- M49.T5: Avoid loading unused AI frameworks.
- M49.T6: Benchmark sequential comparison.
- State rule: do not publish partial performance and responsiveness changes as a successful completed operation.
- Resource rule: include allocations and child processes used by performance and responsiveness in the selected edition budget.
- Failure rule: preserve the current document when performance and responsiveness cannot complete safely.
- Cancellation rule: dispose transient work owned by performance and responsiveness before signaling a terminal state.
- M49.V1: Move and resize while OCR runs.
- M49.V2: Cancel within a documented interval.
- M49.V3: Open a common screenshot quickly.
- M49.V4: Keep idle CPU near zero.
- Principal risk: Adding heavyweight inference libraries to the UI process harms all editions.
- Evidence gate: record concrete validation of performance and responsiveness in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit performance and responsiveness for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the performance and responsiveness changes in a coherent tested git iteration and push it.

### M50 — Privacy and temp files
- Responsibility: Keep image processing local and transient.
- Primary implementation location: `ocready/core/process.py`.
- Input contract: accept only validated values at the boundary of privacy and temp files.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep privacy and temp files independent of unrelated UI and inference implementations.
- M50.T1: Use private temporary directories.
- M50.T2: Clean worker files on success and failure.
- M50.T3: Avoid logging recognized text.
- M50.T4: Never enable remote inference by default.
- M50.T5: Make model downloads explicit.
- M50.T6: Do not persist screenshot history without opt-in.
- State rule: do not publish partial privacy and temp files changes as a successful completed operation.
- Resource rule: include allocations and child processes used by privacy and temp files in the selected edition budget.
- Failure rule: preserve the current document when privacy and temp files cannot complete safely.
- Cancellation rule: dispose transient work owned by privacy and temp files before signaling a terminal state.
- M50.V1: Inspect network traffic during OCR.
- M50.V2: Check cleanup after cancellation.
- M50.V3: Check cleanup after exceptions.
- M50.V4: Confirm settings contain no OCR content.
- Principal risk: A hard crash can leave temporary files until OS cleanup.
- Evidence gate: record concrete validation of privacy and temp files in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit privacy and temp files for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the privacy and temp files changes in a coherent tested git iteration and push it.

### M51 — Git iteration discipline
- Responsibility: Keep every reviewable implementation iteration committed and pushed.
- Primary implementation location: `docs/PROGRESS.md`.
- Input contract: accept only validated values at the boundary of git iteration discipline.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep git iteration discipline independent of unrelated UI and inference implementations.
- M51.T1: Commit architecture before implementation.
- M51.T2: Commit a functional vertical slice.
- M51.T3: Commit screenshot and preprocessing integration.
- M51.T4: Commit vision and resource governance.
- M51.T5: Commit packaging and verification.
- M51.T6: Record tests limitations and next improvements.
- State rule: do not publish partial git iteration discipline changes as a successful completed operation.
- Resource rule: include allocations and child processes used by git iteration discipline in the selected edition budget.
- Failure rule: preserve the current document when git iteration discipline cannot complete safely.
- Cancellation rule: dispose transient work owned by git iteration discipline before signaling a terminal state.
- M51.V1: See a clean worktree after each iteration.
- M51.V2: See commits on the public OCReady repository.
- M51.V3: Reproduce recorded commands.
- M51.V4: Distinguish tested from planned features.
- Principal risk: Large untested commits make review and regression recovery difficult.
- Evidence gate: record concrete validation of git iteration discipline in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit git iteration discipline for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the git iteration discipline changes in a coherent tested git iteration and push it.

### M52 — Ongoing improvement cycle
- Responsibility: Revisit requirements after each stable increment while the goal remains active.
- Primary implementation location: `docs/PROGRESS.md`.
- Input contract: accept only validated values at the boundary of ongoing improvement cycle.
- Output contract: return a typed outcome with sufficient context for the calling module.
- Dependency rule: keep ongoing improvement cycle independent of unrelated UI and inference implementations.
- M52.T1: Audit every user requirement against evidence.
- M52.T2: Review confusing UI paths.
- M52.T3: Review resource usage and stale state.
- M52.T4: Fix the highest-impact verified gap.
- M52.T5: Repeat targeted validation after changes.
- M52.T6: Continue meaningful improvements until the user stops the goal.
- State rule: do not publish partial ongoing improvement cycle changes as a successful completed operation.
- Resource rule: include allocations and child processes used by ongoing improvement cycle in the selected edition budget.
- Failure rule: preserve the current document when ongoing improvement cycle cannot complete safely.
- Cancellation rule: dispose transient work owned by ongoing improvement cycle before signaling a terminal state.
- M52.V1: Find remaining unverified requirements.
- M52.V2: Avoid empty commits.
- M52.V3: Keep public progress accurate.
- M52.V4: Never claim all goals complete from a narrow smoke test.
- Principal risk: Continuous work must prioritize real improvements over cosmetic churn.
- Evidence gate: record concrete validation of ongoing improvement cycle in `docs/PROGRESS.md` before claiming it verified.
- Review gate: audit ongoing improvement cycle for Arabic, English, platform differences, and edition constraints.
- Delivery gate: include the ongoing improvement cycle changes in a coherent tested git iteration and push it.

## Requirement traceability

R-001: At least 1,000 lines of modular plan → this document; verify with wc -l and module IDs.
R-002: Less than 350 MB host RAM → M02 M04 M09 M32 M33 M48; verify with controlled whole-tree benchmarks.
R-003: Less than 1 GB host RAM → M02 M15 M25 M32 M48; verify with separate Everyday measurements.
R-004: Less than 4 GB host RAM → M02 M24 M25 M26 M32 M48; verify with full configured VLM process tree.
R-005: Classical and LLM methods → M13 M16 M24 M28 M29; verify real Tesseract and real multimodal runner jobs.
R-006: Single Linux executable → M41 M42 M44 M46; inspect artifact, run on a clean compatible host.
R-007: Single Windows executable → M41 M43 M44 M46; inspect artifact, run on a clean Windows 11 host.
R-008: One or many methods per build → M02 M25 M29 M44; inspect manifests and built profile assets.
R-009: CUDA with CPU fallback → M24 M25; exercise usable CUDA, missing CUDA, and CUDA initialization failure.
R-010: KDE snipping → M06; exercise Spectacle region capture and cancellation on KDE.
R-011: Windows 11 snipping → M07; exercise screen clip activation and image clipboard return.
R-012: User-friendly polished interface → M35 M36 M37 M38; inspect rendered UI and a complete capture-to-copy flow.
R-013: Image preprocessing with inversion → M09 M10 M11 M12; compare preview and real OCR output.
R-014: Image and text split view → M20 M23 M36; inspect resize behavior and simultaneous content.
R-015: Highlight text from picture → M17 M21 M22; select and copy located Arabic and English words.
R-016: Primary copy-and-paste OCR → M01 M05 M21 M23 M37; validate familiar clipboard shortcuts.
R-017: Arabic and English → M14 M15 M18 M19 M47; inspect shaping, logical order, recognition accuracy.
R-018: Multimodal versatility → M24 M26 M27 M28; process actual image plus text prompt through a local VLM.
R-019: Commit and push each iteration → M51; inspect public repository history and remote refs.
R-020: Continue reviewing while the goal is active → M52; prioritize measured and user-visible improvements.

## Candidate VLM policy

Start with a user-provided compatible llama.cpp model rather than silently downloading several gigabytes.
Investigate GLM-OCR, PaddleOCR-VL, and multilingual Qwen vision models using current upstream support.
Do not equate good English OCR results with Arabic competence.
Do not promise a 0.3B or 1B parameter model fits a particular edition without the vision projector and runtime footprint.
A text-only LLM cannot read pixels without a visual encoder; reject text-only packs for the OCR method.
A 4-bit 1B model uses roughly 500 MB for idealized raw weights before all runtime and visual overhead.
Pocket vision experiments must use a separately measured compact architecture or remain disabled.
Everyday vision experiments need strong image and context limits and must remain opt-in until measured.
Studio admits only configurations with enough reserve for the image, Qt, and CPU fallback working set.
Keep token limits low for screenshot transcription and expose advanced limits only in model settings.
Document model prompt requirements because dedicated OCR families may need specific task prefixes.
Retain original transcription alongside any optional AI cleanup so copy operations remain auditable.

## Release gates

G-01: Source lint and automated tests pass on both supported platforms.
G-02: Offline Arabic and English OCR passes a transparent real-engine corpus.
G-03: The UI renders Arabic shaping and preserves logical clipboard text.
G-04: Image selection and editor selection map correctly for real OCR word boxes.
G-05: No stale OCR result can replace text belonging to a newer document.
G-06: Cancellation cleans up child processes and temporary images.
G-07: Pocket, Everyday, and Studio artifacts launch and recognize independently.
G-08: Whole-tree RAM evidence covers image intake, preprocessing, recognition, and repeated jobs.
G-09: Strict memory marketing is withheld if hard containment or adequate workload evidence is absent.
G-10: CUDA execution and CPU fallback are separately exercised on appropriate hardware.
G-11: Windows 11 and KDE screenshot round-trips are exercised on actual desktops.
G-12: Packaged binaries run without a Python environment and include required OCR language assets.
G-13: Public release artifacts include SHA256 sums, build manifests, notices, and known limitations.
G-14: At least one real compatible local VLM produces a usable image transcription before VLM is called verified.
G-15: All explicit user requirements are re-audited against current authoritative evidence before a completion claim.

## Primary technical references

Qt Arabic and complex text behavior: https://doc.qt.io/qt-6/internationalization.html
Qt for Python Nuitka deployment: https://doc.qt.io/qtforpython-6/deployment/deployment-nuitka.html
Nuitka standalone and onefile guidance: https://nuitka.net/user-documentation/use-cases.html
Tesseract language-data variants: https://tesseract-ocr.github.io/tessdoc/Data-Files.html
Tesseract TSV output: https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html
KDE Spectacle invocation: https://docs.kde.org/trunk_kf6/en/spectacle/spectacle/starting.html
Windows Snipping Tool protocol restrictions: https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-snipping-tool
llama.cpp multimodal model and projector support: https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md
PaddleOCR-VL original model card: https://huggingface.co/PaddlePaddle/PaddleOCR-VL

## M53 — independent non-generative neural OCR

- Responsibility: Add detected-line neural OCR alongside classical OCR and generative transcription.
- M53.T1: Use a separate compiled numerical worker; keep Qt and heavy inference libraries isolated.
- M53.T2: Pin official detector/recognizer configurations, model revisions, licenses and dictionary digest.
- M53.T3: Preserve logical Arabic/English copy order and offer an explicit paragraph-base override.
- M53.T4: Return actual detected polygons with line granularity; never fabricate word coordinates.
- M53.T5: Admit complete runner memory, input buffers and resident application usage per edition.
- M53.T6: Keep CPU inference and explicitly reported CUDA/CPU fallback within the worker contract.
- M53.T7: Support external packs, embedded packs, neural-only and combined onefile variants.
- M53.T8: Bundle only declared worker-distribution files and verify their hashes.
- M53.T9: Keep model loading offline, block implicit downloads and retain third-party notices.
- M53.V1: Copy a detected Arabic line from the native image pane.
- M53.V2: Verify mixed Arabic/English digits and email punctuation against ground truth.
- M53.V3: Compile and run the worker independently of its development environment.
- M53.V4: Exercise GUI and cap-sized memory workloads with the complete embedded binary.
- M53.V5: Compile and test Windows and Linux variants separately.
- M53.V6: Test actual CUDA inference/failure fallback separately from provider-presence metadata.
- Release gate: Real engine, Unicode, geometry and complete-process resource evidence for each published variant.
Qt redistribution obligations: https://www.qt.io/development/open-source-lgpl-obligations

## M54 — interchangeable local vision runtime adapters

- Responsibility: Keep model choice and inference-runtime details independent of the OCR workflow.
- M54.T1: Preserve the existing local pack format and default llama.cpp behavior for saved packs.
- M54.T2: Identify each pack's runtime adapter through a validated stable identifier.
- M54.T3: Define command creation, runtime environment, capability probing and result decoding at one adapter boundary.
- M54.T4: Keep shared admission, cancellation, worker containment and CPU retry policy outside model-specific adapters.
- M54.T5: Describe supported model/projector formats and give actionable compatibility errors before inference.
- M54.T6: Offer an offline versioned JSON worker protocol for additional local vision runtimes.
- M54.T7: Carry adapter identity through pack import, settings, embedding and build/release provenance.
- M54.T8: Never import arbitrary Python modules named by a pack manifest.
- M54.V1: Existing GLM, SmolVLM and Qwen packs continue working without migration.
- M54.V2: Swap two different runtime adapters without changing the pipeline or text/source UI.
- M54.V3: Validate actual response schemas, Unicode text, dimensions and declared backend.
- M54.V4: Fail unsupported adapters, protocol versions and malformed output before displaying a result.
- M54.V5: Exercise real CPU/GPU fallback with cancellation and memory failure exclusions retained.
- Release gate: At least two concrete adapter implementations, backward compatibility and per-pack packaged evidence.
