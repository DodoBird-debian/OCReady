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

## Iteration 5 — Pocket memory headroom and interaction safeguards

- Reduced Pocket's processing cap from 3 MP to 2 MP (decode admission 4 MP) after the measured compiled-GUI near miss. The rebuilt binary peaked at 311.9 MB instead of 347.3 MB, counting its launcher.
- Fixed the internal governor to count Nuitka's resident onefile parent, with validation against the actual OS parent PID. The packaged small-image monitor now reports about 161 MB rather than omitting roughly 66 MB of launcher residency.
- Re-ran all 12 source workloads: Pocket maximum GUI 241.5 MB, Everyday 516.4 MB, Studio 789.3 MB. Checked in fresh reports including explicit pixel caps.
- Prevented editing existing text while a new recognition result is pending, preserving copy access. Flushed pending cleanup previews before recognition to keep displayed pixels and returned geometry aligned.
- Bounded VLM input dimensions to 1600 × 1600, in addition to image-token/context/output limits.
- Added compiled native-GUI plus cap-sized memory benchmarks to future Linux/Windows build checks and artifact reports.
- The initial six-platform/edition build matrix completed successfully: all three editions compiled on Linux and Windows and passed real packaged Arabic/English OCR smoke checks. Those initial artifacts predate this headroom fix; updated builds are required before release.
- Validation: 35 tests and Ruff passed; rebuilt Linux Pocket compiled CLI/GUI smoke tests and all four external compiled-memory scenarios passed.
- Next: updated platform builds, a CUDA runner compiled for the existing driver, embedding selected vision packs and vision-only editions, further source-geometry and usability improvements, and stronger memory containment.

## Iteration 6 — Windows benchmark encoding correction

- The updated matrix passed five edition/platform builds and packaged checks. Windows Pocket compiled and passed small-image real OCR and native-GUI checks, but its cap-sized benchmark report reader failed on Arabic UTF-8 bytes under Windows cp1252.
- Corrected all benchmark JSON reads/writes to specify UTF-8 explicitly. Added a cross-platform regression test that simulates the Windows default codepage and preserves Arabic text.
- This was a verification-tool failure, not evidence of a memory exceedance. The full Windows Pocket memory check still needs a successful rerun.
- Local validation: targeted encoding regression passed. In-progress vision-pack work remains a separate iteration.

## Iteration 7 — embedded vision editions, real CUDA, and Arabic layout

- Added embedding of one or multiple model packs (runner, libraries, model, projector, provenance and notices), plus true vision-only builds. Runtime extraction safely preserves internal library aliases and rejects escaping links.
- Compiled and ran a 269.6 MB Linux vision-only Everyday executable with a Q4 SmolVLM model and Q8 projector inside the binary. Packaged CLI and native-GUI transcriptions passed; observed small-image CLI peak was 775 MB, counting the launcher. Large embedded-vision jobs still need tighter pixel/working-set admission tuning.
- Enabled memory-admissible vision packs in Everyday. Measured SmolVLM Q8 over all four source scenarios, including 8 MP input and repeated GUI inference; largest GUI peak was 847.5 MB. This model reads English and omits Arabic, so manifests and UI enforce English-only selection. Default bilingual OCR stays classical.
- Added native CUDA runner build tooling with pinned llama.cpp/NVIDIA inputs and no system driver changes. Resolved local SDK/glibc compatibility and relocatable compiler/runtime linking issues.
- Real GLM-OCR CUDA inference on the GTX 1660 Ti completed in 6.9 seconds with 1.24 GB host process-tree RSS; the same model took 23.8 seconds on CPU. The earlier incompatible CUDA runner had already exercised real CPU fallback.
- Auto mode now detects CUDA support in either a dedicated CUDA runner or a shared CPU/CUDA executable.
- Reworked the text editor's paragraph layout while keeping rich-text paste disabled: English aligns left, Arabic aligns right, and logical Unicode/copy order is preserved. Added a cursor-position assertion to verify actual rendered placement, not just format metadata.
- Validation: 43 tests and Ruff passed; real embedded-vision CLI/GUI checks passed; tiny-model source memory workloads passed. Native CUDA inference was exercised on real hardware.
- Windows Pocket's encoding-corrected rerun is now green, including compiled CLI, GUI and cap-sized memory scenarios. The latest feature changes still need an updated full-platform build matrix.
- Remaining: embedded-vision large-image headroom, broader bilingual accuracy corpora and real desktop snip interactions, cross-platform GPU validation, strict OS memory containment, packaging provenance refinements, and continued usability review.

## Iteration 8 — native worker allocation containment

- Added Linux workers that wait in a tiny native execution gate until their own user-managed cgroup v2 scope is active. Applied a page-aligned memory allowance, zero worker swap, and group OOM behavior where permitted.
- Added suspended Windows worker launch, job-wide committed-memory limits, and kill-on-close Job Objects. Windows validation is pending source CI at this commit.
- Kept whole-application RSS monitoring, including the launcher, because OS allocation counters have different ownership and mapping semantics. Result metadata now names both the containment mode and its distinct worker counters.
- Verified on the real Linux desktop that the kernel stopped a 320 MB allocation under an approximately 96 MB worker allowance and kept the parent alive. Verified cleanup of an orphaned grandchild after its immediate worker parent exited.
- Real bilingual Tesseract OCR completed in a cgroup worker; observed charged worker peak was about 35 MB. No transient worker scopes remained after the test suite.
- Corrected controller compatibility with systemd 257 and page-rounded `memory.max` readback during implementation.
- Validation: Ruff and 46 local tests passed, including the three native containment cases. The previous iteration's full six-build matrix is now green, including real packaged GUI and memory checks on both platforms.
- Remaining: Windows native worker validation, packaged containment smoke checks, model-specific memory/preview headroom, original-image geometry linking after transformations, capture lifecycle validation, and full application containment/certification.

## Iteration 9 — source highlighting across transformations

- Added an engine-independent inverse geometry module covering crop offsets, all quarter-turn rotations, horizontal/vertical flips, and final resizing.
- Original-image view now keeps real OCR word selection and editor linking after preprocessing, instead of requiring the processed view. Text order and character ranges stay identical between views.
- Mapped boxes are clamped to the working source and never fabricated for generative results without geometry.
- Validated 32 crop/rotation/flip combinations against the actual rasterized preprocessing result, plus a combined resize case and out-of-bounds handling.
- Added a native GUI test that clicks a rotated word in the original image and copies its Arabic Unicode text correctly.
- Validation: 81 tests and Ruff passed locally. Capture cancellation/import state and model-specific memory headroom are the next UI/resource priorities.

## Iteration 10 — retain kernel memory-limit evidence

- Windows source CI passed the native Job Object allocation and descendant-cleanup tests. Ubuntu CI exposed a cgroup evidence-lifetime race after a very fast OOM kill: memory was constrained, but the UI could report a generic engine failure after the kernel counters disappeared.
- Reworked the Linux gate into a small supervisor that retains the worker scope until status/counters are observed. Used `OOMPolicy=continue` when supported, with a version-compatible fallback for pre-253 systemd.
- Kept kernel OOM targeting on the engine while the supervisor remains lightweight. Added explicit process-group cleanup for headless systems without a user service bus.
- Added a real native regression that delays the observer after an OOM kill and still verifies the kernel event, plus an orphan-cleanup test with cgroup support deliberately unavailable.
- Versioned the gate protocol in the runtime manifest so source/runtime mismatches safely retain RSS monitoring instead of invoking an incompatible helper.
- Validation: 83 local tests and Ruff passed after rebuilding the runtime. Updated Linux/Windows CI still needs to verify the compatibility fix.

## Iteration 11 — capture lifecycle and honest output state

- Corrected Windows capture import so failed/oversized images keep the current picture, edited text, dirty flag, and actual error message. Successful import reuses the already-confirmed replacement without a second prompt.
- Preserved maximized window state when returning from capture. Added clean cancellation through Escape and temporary-file preparation errors.
- Isolated typed Windows clipboard-generation and foreground-host primitives. Added best-effort cancellation detection after an observed clipping host leaves, with a short grace period for delayed image delivery and a timeout fallback for unknown hosts.
- Validated Spectacle file import/cleanup, cancellation with unsaved Arabic edits, stale clipboard rejection, successful new-generation import, oversized-image failure, and known/unknown host transitions using native Qt state and controlled platform callbacks. Actual interactive KDE/Windows 11 desktop round-trips remain open validation gates.
- Unlocated AI output now says “AI transcription” and disables unavailable word-box controls while preserving whole-text copying. It no longer masquerades as manually edited text.
- The cgroup compatibility fix from iteration 10 is now green in both Linux and Windows CI, including native allocation/descendant tests.
- Validation: 90 local tests and Ruff passed. Next priorities are fresh packaged builds, embedded-model image headroom, release artifacts, and continued capture/accuracy review.

## Iteration 12 — shared vision preview and input limits

- All six default Linux/Windows builds at `65bd416` passed packaged CLI, native GUI, and cap-sized memory checks. The corresponding local Pocket executable also passed, with a 313.6 MB maximum observed GUI RSS including its launcher.
- Added per-pack image limits shared by preview and inference, defaulting to 1 MP / 1600-pixel longest edge. Switching methods refreshes only when the image policy changes; returning to classical OCR restores its larger preview. Original working pixels remain available for crop/view operations.
- Reduced temporary preprocessing copies and fit images before color-filter buffers are allocated. Native tests verify exact preview/engine pixels and source preservation across cleanup, method changes, and settings edits.
- Added model image-limit controls and manifest validation. Corrected the compiled benchmark's method selection for vision-only binaries and rejected unsupported benchmark combinations explicitly.
- Real Q4 SmolVLM source inference passed four fresh-process scenarios, including four repeated 8 MP GUI jobs; maximum observed peak was 735.0 MB. These stress cases validate memory/inference, not tiled-image transcription accuracy.
- Validation: 96 tests and Ruff passed. The updated embedded Everyday vision-only binary is compiling for its own cap-sized checks. Settings now need a scrollable layout for small screens; broader bilingual accuracy and real desktop capture remain open priorities.

## Iteration 13 — settings on smaller screens

- Put the advanced model form inside a resizable scroll area while keeping Done outside it. The form no longer forces an 854-pixel-tall dialog.
- Inspected the actual rendered 790 × 700 dialog and verified the prompt remains reachable by scrolling at a 560-pixel dialog height. Keyboard-accessible native controls are retained.
- Validation: the native GUI suite (20 tests) and Ruff passed; the smaller-screen case was rerun after simplifying its viewport assertion. The core vision build and fresh source CI are still being observed separately.

## Iteration 14 — traceable builds and failed benchmark evidence

- Added source revision, dirty state, source-content digest, dependency versions and UTC build time to future build manifests. Compilation now rejects sources that changed during the build. Diagnostics expose the embedded source record.
- Runtime manifests now list the included subset of prepared assets and verify their existing hashes. Pocket manifests no longer imply that excluded Precision weights are present; vision-only manifests retain the gate record without claiming an embedded Tesseract engine.
- Benchmarks now record the actual binary digest and build profile, plus source state and changes during measurement. Fixed failed GUI report redaction so zero words stored as an integer cannot mask the real admission error.
- The newly compiled 269.7 MB vision-only Everyday binary passed small-image CLI/native GUI and all three headless memory cases (largest 826.4 MB). Its 8 MP GUI case was safely refused at an estimated 1,037 MB; admission reserves still need review. This is not a passing embedded large-GUI result.
- Downloaded all six successful `65bd416` CI artifacts and independently verified their binary checksums and benchmark success. Largest observed peaks: Linux Pocket 301.6 MB, Everyday 549.3 MB, Studio 739.3 MB; Windows Pocket 306.9 MB, Everyday 495.1 MB, Studio 672.6 MB. These are the documented classical workloads.
- Validation: 99 local tests and Ruff passed after the provenance/reporting fixes. Fresh builds are required to exercise the new manifest controls; the shared-preview source CI was already green on both platforms.

## Iteration 15 — reserve image memory according to actual policy

- Replaced the fixed extra 80 MB vision admission reserve with 16 MB plus 24 bytes per bounded input pixel. The runner estimate continues to cover weights, encoder, context and workspace; the additional application reserve covers six pixel buffers and the fixed safety margin.
- A default 1 MP pack now reserves 40 MB, while a 2.56 MP pack reserves 77.4 MB. This avoids reserving almost the larger input allowance after the UI and engine have both been limited to 1 MP.
- Added boundary tests: the compact policy admits a 500 MB runner beside a 457 MB resident app, refuses the same app with the larger image policy, and still refuses the compact policy if resident usage rises too far.
- This is a conservative admission heuristic followed by native worker limits and RSS monitoring, not a claim that future allocations are known. A fresh clean-source embedded build is required to validate the previously refused GUI workload.
- Validation: the 100-test suite exposed one old test's fixed-reserve assumption; its refusal case was updated to remain above the new budget boundary and the vision suite was rerun. Ruff passed.

## Iteration 16 — stable recognition workspace and native text editing

- Reproduced a live crop gesture changing the preview while the worker retained its original recipe. Recognition now exits crop mode, restores the exact processing preview, and prevents crop/settings/original-view changes until the worker finishes.
- Disabled the Join lines action during recognition and guarded its programmatic path, so read-only pending text cannot be changed through an action before replacement.
- Added picture-focused Ctrl+C for selected source words while retaining native text-pane copying.
- Automatic paragraph direction now follows newly typed/pasted Arabic and English, not only the initial OCR result. Direction formatting joins the text operation so one Undo/Redo restores both content and layout; explicit direction choices remain respected.
- Native GUI validation covers the reproduced crop race, pending-text protection, focus-sensitive copying, mixed-language paste, and undo/redo. All 104 tests and Ruff passed in the isolated worktree, using the real prepared OCR runtime. Work was isolated while the clean embedded vision build completed its source check.
