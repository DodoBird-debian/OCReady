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

## Iteration 17 — embedded vision headroom verified

- The clean `e9cdf23` Everyday vision-only build completed with provenance enabled. Verified its clean source record, dependency versions, selected methods, safe runtime-manifest subset and gate protocol.
- Real compiled CLI/native GUI transcription checks passed. Four externally observed packaged scenarios passed: sample 780.9 MB, dark/inverted 777.2 MB, 8 MP headless 826.7 MB, and 8 MP native GUI 921.2 MB. Counts include the resident onefile launcher and all OCR descendants.
- Published the raw report with executable SHA256, model hashes and build metadata. Both source and executable remained unchanged during measurement.
- Integrated and pushed iteration 16 after the clean build and benchmark finished. Its 104-test validation used the same prepared real OCR runtime. The newer source CI and default six-build matrix remain under observation.
- The tested compact model remains English-only. Open priorities include broader Arabic/English accuracy evaluation, actual KDE/Windows 11 interactive capture, Windows GPU/VLM packaging, downloadable prerelease assets, and continued UI/resource review. The goal remains active.

## Iteration 18 — verified downloadable release preparation

- Added release preparation that requires all six default platform/edition artifacts, their exact clean source revision, matching executable checksums and benchmark provenance, and four numerically passing packaged memory scenarios.
- Prepared distribution files include binaries, individual/aggregate checksums, build manifests, benchmark reports, a release evidence index, and generated notes with measured peaks and remaining validation limits. Existing output files are preserved rather than overwritten.
- Added a tag-only prerelease job after the six-build matrix. Only that job receives release-write permission; ordinary pushes keep read-only build permissions. Existing releases are not replaced.
- Added six tests covering complete preparation and rejection of modified executables, mismatched source, failed GUI runs, numeric budget exceedance and changed measurement sources.
- Validation: all 110 local tests and Ruff passed. The complete six-build matrix at `e9cdf23` is now green with provenance enabled. The newer `1192174` builds, including the crop/editing fixes, are still running; release publication waits for verified candidate artifacts.

## Iteration 19 — bilingual transcription corpus and error measurement

- Added eleven original, visually inspected Qt-rendered fixtures with ground-truth Unicode and image digests: clean English/Arabic, mixed scripts/digits, Naskh/Kufi/UI fonts, diacritics, small Arabic, dark/low-contrast text, and corrected rotation.
- Added sequential Fast/Precision/local-vision evaluation with explicit completed/skipped/error counts, strict NFC/whitespace normalization, per-case CER/WER and weighted summaries. Diacritics, digits, punctuation and directional controls are not silently removed to improve scores.
- Exploratory results exposed Fast missing Arabic lines that Precision recovered, difficult diacritics/digits, and layout confidence selecting incomplete text in one case. These are recorded as quality gaps rather than hidden by memory-test success.
- Source CI now uploads the synthetic-corpus accuracy report on Linux and Windows. No accuracy percentage threshold is inferred from this small artificial corpus; runtime evaluation errors still fail the step.
- Added six scoring tests, including canonical Unicode equivalence, preserved Arabic marks, Arabic/Western digit errors and hallucination rates above 100%. A clean-source baseline and further UI/reading-order improvements follow.
- The six packaged builds at `1192174`, including the crop/editing fixes, are now all green. The `v0.1.0-preview.1` tag build is still running its own verification/release path.

## Iteration 20 — remembered choices and published accuracy evidence

- Fixed the GUI entrypoint overriding the saved edition on every launch. Available saved editions now restore; explicit CLI editions and compiled edition restrictions take precedence.
- Remember method choices per edition and restore layout/backend alongside existing language preferences. Fresh Everyday/Studio sessions prefer Precision, informed by the measured bilingual omissions in Fast. Headless method/edition defaults remain stable.
- Added native tests for restored choices, edition switching, compiled restrictions, fresh Precision defaults and the actual GUI entrypoint override contract.
- Published clean-source `1595c32` accuracy reports: weighted synthetic-corpus CER/WER were Fast 29.2%/26.7%, Precision 9.9%/11.7%; with automatic layout comparison, Fast 28.4%/28.3%, Precision 7.5%/8.3%. These are limited corpus error rates, not universal accuracy claims.
- All six tag builds and the release verification/publishing job passed. The first public prerelease, `v0.1.0-preview.1` at `ffc654b`, contains 27 assets including six native executables and their evidence. Development continues beyond that tagged snapshot.
- Verified the public release's downloaded evidence index and notes against its published aggregate checksums. All six listed workload peaks remained below their respective budgets.
- The expanded GUI suite initially retained extra closed test windows and exhausted a Pocket worker allowance. Test teardown now disposes all windows created by each test and flushes deferred Qt deletion. All 119 tests and Ruff then passed. The runtime guard correctly refused the overfilled test process without killing it.

## Iteration 21 — inspect and choose OCR alternatives

- Exposed retained comparison readings in a native selector with their engine, actual layout, character count and clearly labeled OCR score. Confidence-based initial selection remains a convenience; users can now choose another read without running inference again.
- Switching readings installs that reading's exact text and boxes, clears stale selection, protects unsaved edits through the existing replacement confirmation, and stays disabled while recognition is active.
- Image/source changes discard stale alternatives. Single-read workflows keep the comparison bar hidden. Added real layout provenance to result JSON.
- Replayed the real Arabic Kufi corpus failure: automatic confidence selected an incomplete read; choosing the retained Screenshot reading recovered the complete reference. Inspected the native split view and clicked a real Arabic source word after switching. Saved the rendered comparison workspace.
- Validation: all 121 tests and Ruff passed, including a real background comparison, source geometry switching, edit protection, source replacement and selector lifecycle. Cross-platform source CI follows this push.

## Iteration 22 — release dormant onefile payload residency

- Identified retained file-backed payload pages in Nuitka 4.3.5's launcher after extraction. Added a version-checked private compiler overlay and native post-extraction helper; the installed compiler is never modified.
- Linux releases only inward-aligned payload pages. Windows trims only the launcher's own working set after decompressor cleanup. Failures retain ordinary admission/monitoring; this optimization is not a memory limit or a claim about global file-cache ownership.
- Built two controlled onefile probes with identical 48 MiB data. Verified extracted SHA256, child completion and launcher identity. Steady launcher RSS changed from 62.4 MB to 2.0 MB; total steady tree RSS changed from 90.0 MB to 29.5 MB. Cold-start/full-app peaks remain separate measurements.
- Added native file-mapping preservation/RSS tests, overlay isolation/failure cleanup, and unknown compiler/layout rejection. All 124 tests and Ruff passed. Full Pocket, embedded vision and Windows builds are the next verification gates.
- Separately evaluated official PP-OCRv5 mobile detection/Arabic recognition models in an isolated CPU harness: eleven fixtures in about three seconds, 6.3% CER and 230 MB observed tree peak including the harness. Mixed-direction copy order needs explicit handling before integration. The prototype is not a shipped method or a GUI memory result.
- Preview 2 at `a46aeb6` passed all six platform/edition builds and publication verification; it includes remembered choices and visible OCR alternatives. Later launcher/engine work is outside that tagged snapshot.

## Iteration 23 — full-app payload and session evidence

- Rebuilt Pocket and the entirely embedded vision-only Everyday executable from clean `2ba93c6` with the compiler overlay. Verified matching source/patch provenance before running real packaged CLI and native GUI checks.
- All four packaged scenarios passed. Pocket's maximum GUI peak was 242.4 MB. Embedded SmolVLM Q4 peaked at 651.6 MB for the full 8 MP GUI case, versus 921.2 MB before the launcher optimization. Reports include cold startup, launcher and OCR descendants; small Pocket headless jobs still peaked near 200 MB during extraction.
- Both executables and project sources remained unchanged during measurement. Published the binary-identified reports rather than extrapolating from the small native probe.
- A separate source-GUI soak completed all 100 cap-sized image loads/recognitions. Peak was 231.6 MB; average idle usage stayed flat (160.5 MB first ten jobs, 158.4 MB last ten). The raw report distinguishes source testing from a compiled soak and records when its source fingerprint was captured.
- The Linux default-edition matrix is green with the new bootstrap. Windows jobs are still under observation. Neural OCR integration remains next, with explicit logical text ordering and honest line geometry required before shipping it.

## Iteration 24 — neural worker, protocol and native source workflow

- Added a separate PP-OCRv5 worker, strict line-polygon response parsing, memory admission, pipeline/CLI routing, configurable pack storage, native settings and line selection. Word positions are not invented for this engine.
- Fixed visual CTC copy order for the tested Arabic-led mixed text, Arabic digits, English punctuation and email cases. Reading direction remains an explicit pack option for ambiguous mixed layouts.
- Compiled a standalone numerical worker and ran it outside the project without a virtual environment. The app-to-worker pipeline read the bilingual sample with six detected lines; clicking/copying the Arabic line in the real native GUI preserved logical Unicode. Observed sample tree peaks were 313 MB headless and 398 MB source GUI, not complete onefile/cap-sized certification.
- Added pinned official ONNX/config downloads and a verified derived dictionary, offline worker loading, declared-distribution hash manifests, retained runtime/model notices, neural-only/combined build options and separate artifact variant names.
- Extended accuracy/resource tools for neural packs. Fixed a benchmark blind spot so a successful exit without a valid result, or an error-bearing result, cannot pass; GUI timeout explicitly fails.
- Default app builds do not import numerical libraries into the Qt process. Full embedded variants, neural GPU inference and Windows worker packaging remain independent verification gates.
- Fixed a onefile restart bug in both model families: built-in options no longer persist ephemeral asset paths. They are reapplied to freshly extracted assets, remain saved across editions, and protect built-in asset fields from accidental replacement.
- All 140 tests and Ruff passed. Rebuilt the worker with offline loading/telemetry settings and declared runtime/Python notices. A real prefer-CUDA request on the CPU worker reported CPU fallback and preserved the expected mixed Arabic/English/digit text.
- The previous launcher change is now green on all six Linux/Windows builds. The complete neural-only/combined application builds, cap-sized measurements and Windows worker packaging follow this source integration.

## Iteration 25 — complete neural onefile evidence and platform workflow

- Built the entire neural-only Everyday application from clean `b2576b9`: a 194.2 MB executable containing the compiled numerical worker, models and runtime notices. Real CLI and native GUI checks returned six linked line regions.
- All four packaged resource scenarios passed, including cold startup and descendants. The 8 MP GUI peak was 531.1 MB. The separate four-job source GUI peak was 591.5 MB. Recorded binary/source identities and unchanged-source checks accompany the reports.
- All eleven fixed synthetic accuracy cases completed: weighted CER 3.9%, WER 7.5%. Diacritic-heavy text remains a clear weakness (38.9% CER), so these results are not a general accuracy promise.
- Added a manual Linux/Windows workflow that compiles the standalone worker, downloads checksum-locked official models, runs source tests and real neural accuracy, embeds the worker in a variant executable, then runs packaged GUI and memory checks before uploading artifacts.
- Both platform source checks passed at `b2576b9`. Complete Windows neural packaging remains a separate gate under observation.

## Iteration 26 — checksum-locked vision presets

- Added reproducible SmolVLM Q8 and GLM-OCR Q8 preparation with pinned official weights/projectors, model cards, licenses and llama.cpp CPU archives for Linux/Windows x86_64. Generated manifests use relative paths and can be embedded together.
- Downloads require the exact locked size and SHA256 before atomic publication. Runtime extraction checks paths, links, entry counts and unpacked size; verified archives are re-extracted rather than trusting a stale marker.
- Prepared both real presets locally and verified all locked assets. Upstream language declarations are now explicit: these vision presets expose English; Arabic remains served by the tested classical/neural engines. CPU presets do not claim validated CUDA packaging.
- Added regression checks for oversized/corrupt download rejection, valid-cache reuse, Windows archive paths and Linux shared-library links. Three focused tests and Ruff passed. Complete combinations still require their own executable and per-method resource evidence.

## Iteration 27 — verify every embedded engine choice

- Added explicit installed pack selection for CLI and native GUI. Ordinary GUI launches retain preferences; explicit requests select the requested method/pack and reject missing or inadmissible choices before inference.
- Extended packaged smoke checks to enumerate every embedded classical/neural/vision choice, verify the actual returned engine in CLI and GUI, and run all four resource scenarios separately. Reports include requested method/pack IDs and distinct variant/method filenames.
- Added curated neural, classical-plus-neural, and multimodal build commands. Everyday multimodal includes SmolVLM; Studio includes both SmolVLM and GLM-OCR. Their Windows/Linux workflow runs per-method validation before uploading artifacts.
- Both real curated CPU runners completed bilingual-image input locally, reporting CPU and their exact model IDs. SmolVLM omitted Arabic; GLM-OCR repeated its known Arabic word error, consistent with the retained language limitations.
- All 146 tests and Ruff passed, including preference preservation, exact GUI selection, rejection of missing/oversized packs, and complete embedded-choice enumeration. Full multimodal binaries are the next measured gate.

## Iteration 28 — compact workspace and method guidance

- Adjusted method/layout selectors so long model names do not force the workspace beyond its 960 px minimum. Short layout labels retain their full explanations in tooltips. Classical layout/comparison controls hide for neural and vision methods.
- Added guidance for word selection, whole-line selection and AI transcription directly to the current-method tooltip and Help. Default neural names no longer repeat the engine family twice. The GLM example manifest explicitly declares English.
- Rendered the real native 960×700 workspace, ran the compiled neural worker, selected/copied the Arabic line and verified logical clipboard text. Classical minimum layout width was 938 px; neural was 829 px. Saved the inspected compact screenshot.
- All 146 tests and Ruff passed. The combined executable continues building from the separate clean `602cc5b` snapshot, so these later UI edits do not alter that build's provenance.

## Iteration 29 — worker source identity and exact resource selections

- The neural worker builder now captures its source identity before compilation and rejects any source change before writing the distribution manifest, matching the outer application's provenance discipline.
- Explicit per-method resource workloads now fail if the returned engine/pack identity differs from the requested choice, even when the process exits successfully. This guards against silently measuring a smaller fallback selection.
- Added regression coverage for a wrong family, wrong pack and valid explicit/default local choices. Existing provenance checks and the new resource checks passed; Ruff passed.
- The clean `602cc5b` combined Linux binary built at 530.3 MB and began real per-method validation. The first four Fast OCR workloads passed with a largest observed tree peak of 666.7 MB. Both Windows/Linux neural workers compiled in Actions and moved to the outer-app build; complete results remain pending.

## Iteration 30 — evaluate a bilingual Studio vision candidate

- Provisioned official Qwen3-VL-2B Q4_K_M weights and the matching Q8 projector with pinned revision, sizes, digests, model card and Apache notice. The preset uses a conservative 3400 MB runner estimate and Arabic + English evaluation mode.
- The actual model read the full bilingual sample correctly on CPU and CUDA. Observed host tree RSS/time: CPU 3.03 GB/20.6 s; CUDA 1.43 GB/5.9 s using the previously verified CUDA 12.4 native SM75 runner. Raw development probe outputs explicitly distinguish this from clean packaged certification and VRAM measurement.
- Changed the curated Studio multimodal combination to SmolVLM plus Qwen3-VL, alongside classical and neural OCR. GLM remains available as a separately selectable pinned preset. Broader accuracy, cap-sized source workloads and full Studio packaging remain required gates.
- Previous iteration's full source suite passed all 147 tests. Exact current-source Qwen corpus/resource measurements follow this checkpoint; no universal Arabic accuracy or 4 GB guarantee is inferred from one image.

## Iteration 31 — full combined evidence and broader vision limitations

- The clean `602cc5b` Linux Everyday multimodal binary passed CLI and native GUI checks for all four embedded engine choices, then all sixteen packaged resource scenarios. Its largest observed tree peak was 666.7 MB, including cold startup and descendants; binary/source identities remained unchanged. Published separate raw reports for every engine.
- Both Linux and Windows neural-only Actions builds at `f4000b8` completed source tests, worker compilation, real bilingual accuracy, complete onefile CLI/GUI checks and four resource scenarios. Artifacts remain distinct from older public preview releases.
- Clean `7a252b4` Qwen CUDA accuracy completed eleven cases with 7.0% weighted CER / 13.3% WER. Mixed-digit substitution and Arabic diacritic failures are retained in the public report. Curated model-rich builds now default to the bilingual neural engine, while preserving saved GUI choices and classical word selection.
- Qwen's first CPU resource run stayed below 4 GB (3.45 GB peak) but the four-job GUI case failed its fixed 120-second timeout after two jobs. Preserved the failed report. The benchmark now gives sequential jobs proportional time, with a separate outer watchdog; memory budgets and failure reporting are unchanged. A fresh complete run is required before claiming success.

## Iteration 32 — release model variants with complete evidence

- Added a dedicated release verifier for both Linux/Windows model-rich variants. It checks executable checksums, clean source/content identities, edition/variant identity, matching platform choices, four actual-engine resource scenarios for every embedded model, and the complete matching-source neural corpus report.
- Added a narrow compatibility path for the first neural-only workflow, which predates explicit method-selection fields; every returned workload engine still must match its single embedded neural pack. Combined builds cannot use this inference to omit per-model reports.
- Release output carries both native executables, per-method resource reports, neural accuracy, source manifests, individual/aggregate checksums and explicit CPU, geometry and memory limitations. Existing release output is preserved rather than overwritten.
- Added opt-in workflow publication after both platform build jobs and evidence verification succeed, with write permission restricted to the release job. Eleven focused tampering/completeness tests and Ruff passed.
- The user explicitly added easy LLM swapping to the objective. Existing packs swap models, projectors, prompts and runners; a runtime adapter boundary and compatibility checks are the next architecture iteration.

## Iteration 33 — published neural preview and completed Studio source baseline

- Applied the new release verifier to the real `f4000b8` Linux/Windows neural artifacts from successful workflow `42974440284`. Both executable hashes, all eight packaged resource scenarios and both eleven-case accuracy reports matched their clean platform source records.
- Published `neural-preview.1` with two native model-embedded executables and thirteen total assets, including individual/aggregate checksums, manifests, resource/accuracy reports and limitations. Linux/Windows peak GUI RSS was 537.7/342.3 MB respectively. Updated direct download documentation.
- Reran Qwen CPU source workloads from clean `423a1b3` after scaling the sequential benchmark deadline. All four passed; the repeated 16 MP GUI completed four 43–45 second recognitions in 178 seconds, with 3.45 GB peak tree RSS. The failed earlier deadline-limited report is retained.
- Interrupted work was explicitly restarted after the user resumed early; the scheduled later restart was disabled. The canceled combined Actions run remains canceled rather than being counted as passed.
- The release-gate change passed all 158 tests and Ruff before integration. Complete Studio onefile measurements and the new runtime-adapter architecture remain active work.

## Iteration 34 — interchangeable vision runtime adapters

- Extracted a fixed adapter registry and protocol for model validation, commands, capability probing, environments and response decoding. The pipeline/UI continue using shared orchestration for admission, containment, cancellation and selective CPU retry. Manifests cannot name arbitrary Python imports.
- Preserved llama.cpp as the default for all old packs. Added an offline JSON v1 worker adapter with strict schema, Unicode text, input dimensions and actual CPU/CUDA reporting; its model format is worker-owned and its projector can be optional.
- Added native runtime selection for external packs, immutable bundled runtime identity, format-preserving embedding, adapter provenance/diagnostics and result runtime identity. Documented the worker contract and backward-compatible pack format.
- All 174 tests and Ruff passed, including malformed protocol rejection, missing/unknown adapters, exact-image validation, CPU-only enforcement, fallback reporting, cancellation/budget exclusions, native settings swap and opaque-file embedding.
- Replayed actual SmolVLM CPU and Qwen CUDA inference through the refactored default adapter. Both retained expected sample text and backend identity; Qwen preserved the full Arabic/English sample. The JSON interface is protocol-tested; a separately compiled real reference worker remains its next validation step.
- A complete local Studio binary with classical/neural OCR plus both SmolVLM and Qwen is compiling independently at `3d2adb7`; its packaged resource evidence remains pending. See iteration 42 for the later provenance audit.

## Iteration 35 — verified reuse of the isolated numerical worker

- Added the builder digest to worker provenance and a dedicated reuse verifier for current worker/builder input hashes, exact Python/dependency versions, clean worker source state, protocol and every declared distribution-file hash. Incompatible inputs and escaping paths fail validation.
- Wired an exact-key, platform-specific Actions cache for only the compiled worker distribution. No prefix restore is used. Fresh/reused workers are verified and run against the corpus before caching; outer executables still require full per-method platform/resource verification before publication.
- Pinned the official cache action's verified v5 commit. Reusing the independent worker is intended to avoid recompiling numerical libraries for UI/model-pack changes; no cache-hit timing improvement is claimed before the new workflow exercises it.
- All 182 tests and Ruff passed, including modified executable/library content, entrypoint/builder changes, dependency/Python/protocol mismatches, unclean source state and escaping inventory paths.

## Iteration 36 — compiled JSON vision reference worker

- Added a standalone, stdlib-only JSON v1 reference worker around a selected native multimodal CLI. It returns logical Unicode, exact processed-PNG dimensions and backend identity, with explicit CPU offload disabling and native error forwarding. Its descendants stay under the parent application's containment/cancellation policy.
- Added a cross-platform worker compiler that retains Python/OCReady/native notices, source/native-runner hashes and a declared nested-file inventory. Copying a different runtime removes stale libraries from the owned native subdirectory.
- Added optional runner/adapter selection to pinned vision preparation. Model weights/prompts remain separate from the worker interface, so the same model can be evaluated through either adapter without pipeline/UI changes.
- Consolidated declared-distribution bundling for neural and JSON workers, preserving nested native descendants and excluding undeclared siblings. Protocol/input, CPU-only flags, stale-library cleanup, declared nesting and tamper rejection are covered by focused tests.
- Compilation and actual-model validation of this second adapter follow the clean checkpoint; unit protocol tests are not presented as real OCR proof.

## Iteration 37 — real second-adapter CPU inference and runtime aliases

- Compiled the JSON reference worker from clean `edfd7db`, including its own Python runtime and native llama.cpp descendant. Prepared the official SmolVLM pack for `json-cli-v1` and ran actual CPU inference through shared orchestration.
- The result retained the expected English sample text and explicitly reported runtime `json-cli-v1`, CPU backend and cgroup-v2 containment. Observed development-run tree peak was 522.5 MB in 4.3 seconds; this is a source/client probe, not a complete outer onefile resource certification.
- Runtime copying now preserves shared-library aliases as hard links where supported, with a copy fallback. This prevents needless duplication of large native GPU libraries in worker distributions and their onefile archives. Existing stale-runtime cleanup and nested-file hash verification remain in place.
- The complete local `3d2adb7` Studio binary built at 2062.8 MB. It has begun real per-method CLI/GUI and resource validation on disk-backed temporary storage. First neural CLI recognition returned six real linked lines; full evidence remains pending. Later audit found its provenance correctly marked dirty due to the untracked runtime symlink; it is development evidence, not a clean build.

## Iteration 38 — actual CUDA and relocation through the second interface

- Compiled a separate JSON worker around the verified CUDA 12.4 native SM75 runtime from clean `1bc6e76`. Qwen ran through `json-cli-v1` on actual CUDA and retained the entire bilingual sample, reporting 1.45 GB observed host tree RSS in this development probe.
- Ran the CPU worker directly from a different working directory without virtual-environment/PYTHONPATH settings. Its standalone Python/native runtime returned the expected SmolVLM transcription.
- Created an archive using the production declared-distribution bundler, extracted it to another directory and performed actual SmolVLM inference from the relocated manifest. Nested native dependencies resolved without referring to the original worker directory.
- Published raw functional outputs and both worker source identities. These probes are distinct from complete outer onefile resource or Windows GPU certification. All 185 tests and Ruff passed at the preceding implementation checkpoint.
- Studio's first packaged resource scenarios include its cold 2 GB launcher and remain below 4 GB. Startup is noticeably dominated by archive extraction; the next packaging iteration addresses the measured extra traversal without changing model behavior.

## Iteration 39 — one-pass staged runtime extraction

- Replaced the full gzip member-list scan followed by extraction with one forward validation/extraction pass. Every member/link remains checked, partial staging is removed on failure/interruption, and only a complete runtime is atomically published. Existing internal library aliases remain supported.
- Added a late-invalid-member regression check that confirms earlier staged files are removed and no runtime is published. All 186 tests and Ruff passed, including the existing extraction/alias and real native containment suite.
- Selected Nuitka's supported low-memory build flag rather than adding another compiler patch. In pinned 4.3.5 this also selects level-3 onefile compression; the requested policy/compiler and known level are recorded in provenance. Standalone builds do not claim onefile compression. Full compiled memory/startup checks follow this checkpoint.
- The already-frozen `3d2adb7` Studio executable continues its original packaged measurements independently; its first neural CLI/GUI and all four resource scenarios passed at roughly 2.20 GB cold tree RSS. Later startup changes are not retroactively attributed to those results.

## Iteration 40 — preserve language intent when swapping models

- Fixed English/Arabic-only models overwriting the user's broader recognition choice. Model constraints now temporarily select supported languages, disable incompatible choices and restore the explicit user preference when returning to a compatible method.
- Closing while a constrained model is selected saves the underlying preference, so merely trying the English-only vision model does not make later classical/neural sessions omit Arabic. Explicit user language changes remain persistent.
- Rejected unsupported language declarations while reading model/neural manifests, with defensive UI handling for invalid programmatic packs. Existing valid packs need no migration.
- Added native tests for bilingual → English model → classical restoration, explicit English → Arabic model → classical restoration, enabled-item lifecycle and saved preference preservation. Focused UI/vision/neural checks and Ruff passed; full source validation follows the checkpoint.

## Iteration 41 — diagnose and reduce Windows Studio image size

- Full validation of iteration 40 passed all 189 tests. The initial complete Studio multimodal workflow at clean `31d32ae` passed every Linux per-method CLI/GUI and resource check, but Windows rejected its 2011.9 MB executable with WinError 193 before startup. This is a launch failure, not a passing Windows memory result. The exact failed PE layout was not retained by that workflow.
- Added a bounded PE32+ header audit that records machine, mapped image size and sections separately from on-disk size. Windows builds reject incompatible machine/image layouts before success metadata. The workflow retains small failure diagnostics and successful PE reports, enabling evidence-based investigation rather than inferring image layout from file size.
- Added a compact SmolVLM Q4_0 preset derived from the pinned official Q8 weights with the pinned native quantizer. Exact input/output size and SHA256 are required; mismatches never publish partial model weights. Studio retains both the small English model and bilingual Qwen; Everyday keeps its existing Q8 choice.
- Real Linux preparation reproduced the locked Q4 digest and CPU inference retained the expected English sample. This functional probe is distinct from clean packaged resource or corpus accuracy evidence. The smaller Windows combination remains unverified until the next build actually launches and completes its workloads.
- All 192 tests and Ruff passed before two additional malformed mapped-image cases were added; the focused final validation follows before commit.

## Iteration 42 — preserve complete measurements and update downloads

- Published Everyday multimodal workflow `42998895423` at clean `3d2adb7` succeeded on Linux and Windows and automatically released both native binaries. All sixteen per-method resource scenarios passed on each platform; maxima were 683,921,408 and 622,592,000 bytes. Both neural corpus evaluations completed all eleven fixtures at 3.9% CER / 7.5% WER. Added the unchanged public evidence index and direct four-method download links.
- Clean `31d32ae` Pocket workflow `43003993770` compiled and verified both platform binaries; its other edition jobs ran source checks without compilation. All eight Pocket resource scenarios passed, with Linux/Windows GUI peaks of 226,672,640 / 172,695,552 bytes. Preserved both CI raw reports and the separate local Linux four-case report (248,242,176-byte maximum).
- The frozen local Studio Q8/Qwen combination finished every CLI/GUI check and twenty resource scenarios, with a 3,268,141,056-byte maximum. Retained the raw reports with their dirty-source flag intact and corrected the earlier clean-build wording. The runtime symlink explains the flag; it is not erased or excused into a release certification.
- Independently retrieved all five clean Linux Studio resource reports from workflow `43003987676` at `31d32ae`. All twenty scenarios passed with a 3,255,017,472-byte maximum. Retained exact report/model/binary/source identities. The workflow's Windows launch failure remains the reason this pair cannot be released.
- Iteration 41's final eight focused preparation/PE checks and Ruff passed before commit. Its new dual-model Studio CI run is in progress; the failed previous Windows launch is not counted as passed.

## Iteration 43 — verify identical models and meaningful corpus identity

- Strengthened the paired release gate beyond matching model IDs. It now validates and compares model/projector or detector/recognizer/dictionary hashes, declared languages, real line geometry and registered vision adapters. Older packs retain the default llama.cpp identity; JSON workers can omit their projector. A bilingual neural model remains required.
- Added shared asset identities to the release evidence index while keeping OS-specific executable hashes independent. The gate rejects missing/malformed/duplicate asset records and consistent-looking but different platform model contents.
- Testing against the actual published neural pair exposed raw corpus hashes differing solely because Git translated manifest line endings on Windows. Added canonical JSON content identity to new accuracy reports while retaining raw file hashes. Release preparation compares the committed corpus content and every expected case/model, accepting only that corpus's exact LF/CRLF legacy file checksums for old reports.
- The new identity preserves digits, diacritics, fixture image hashes and cleanup recipes. Changed text, images, recipes, duplicate cases, wrong models and unrelated legacy hashes fail verification. The actual published Linux/Windows neural pair passes the stronger gate.
- All 215 tests and Ruff passed. Studio's compact dual-model build has entered packaged executable/resource verification on both platforms; final results remain pending.

## Iteration 44 — keep selections while inspecting the original

- Reproduced a source/text mismatch: selecting recognized text or clicking a source word, then toggling the original picture, cleared canvas selection while the editor stayed highlighted and the copy action appeared available.
- Preserved the same logical selection indices as geometry is mapped between processed and original images. Copying remains usable after repeated view changes; edits and genuinely new recognition results retain their existing invalidation behavior.
- Reset stale hover indices when replacing image/word geometry, preventing a hover from a previous view/result being painted over unrelated text.
- Extended the real rotated Arabic source-click test and added text-driven word/line selection cases. All three cases failed before the fix and passed afterward; the complete 217-test suite and Ruff passed.
- Reviewed the native workspace at 960 × 700 with cleanup open; the split view and primary copy/recognition controls remained usable. Startup caching remains research: the supported compiler cache has per-file checksums, but first-run concurrency and interrupted runtime extraction require explicit engineering before enabling it for users.

## Iteration 45 — isolate startup-cache experiments

- Added a reproducible, disposable native probe for supported compiler temporary streaming versus cached archive extraction, with an identical incompressible payload, full SHA256 verification, cold/warm wall times, changed-byte repair and simultaneous cold-launch pairs. Reports preserve binary, asset, source/compiler and trim-overlay identities.
- Kept caching out of application defaults. Reviewed pinned compiler code and official guidance: cached archive entries can skip decompression after checksum validation, but there is no first-extraction inter-process serialization. OCReady's current runtime extraction also needs additional process coordination before sharing a persistent directory.
- Added a modular implementation/release gate covering build identities, private storage, atomic stages, interruption/repair, Windows locks, document separation, bounded disk lifecycle and full platform/RAM validation. Documented existing observed startup/recognition times without calling their difference a pure extraction measurement.
- Probe CLI and Ruff passed. Actual native measurements follow this clean checkpoint; no performance improvement or cache safety is claimed from implementing a benchmark wrapper.

## Iteration 46 — measured cache prototype and compact-model accuracy

- Ran the native startup probe from clean `5911af8` with a 128 MiB incompressible asset. All sequential payload checks and changed-byte repair passed. Temporary launches took 0.282–0.289 s, a fresh cached directory 0.285 s and warm cached launches 0.167–0.169 s. Repair took 2.68 s. These are synthetic timings including child SHA256 verification, not whole-app performance claims.
- All six launches across three concurrent cold pairs returned the correct payload, with 2.94–4.78 s wall times. Preserved the raw report without turning finite successful race samples into a concurrency guarantee. “Cold” is explicitly an empty extraction directory; OS page caches were not flushed. Application cache defaults remain unchanged.
- Hardened the probe controller to clean its own launcher/descendants and close pipes on timeout or interruption; added the cold-cache definition to future reports.
- Verified the controller against real child output, mismatched output and a timed-out process with its own sleeping descendant; the descendant was terminated. All 218 tests and Ruff passed after the final controller change.
- Preserved clean `0ed066a` compact SmolVLM Q4 corpus evidence: one supported English fixture completed with zero CER/WER; ten unsupported Arabic/bilingual fixtures were skipped. This is not bilingual accuracy certification.
- Studio platform/resource validation and the subsequent gated release run remain active independently of these developer experiments.

## Iteration 47 — consistent native application branding

- Replaced font-dependent runtime icon drawing with an owned vector mark and matching portable PNG. Added a reproducible Qt/Pillow renderer producing nine ICO resolutions from 16 to 256 pixels, preserving transparency and consistent appearance across systems.
- Attached the ICO to the Windows executable itself. Inspection of the actual previous Pocket executable confirmed it contained version/manifest resources but no icon/group-icon resources; setting the Qt window icon alone had not branded the downloadable file.
- Extended bounded PE diagnostics to record root resource types and reject a new Windows output missing its attached icon resources. Added resource-table bounds coverage and successfully parsed the earlier real Windows PE. Both build workflows retain layout diagnostics for failures and completed artifacts.
- Visually inspected the generated mark, decoded all nine ICO sizes and loaded the runtime icon in native Qt. All 219 tests and Ruff passed after the resource changes. A font-independent vector fallback keeps incomplete source/package installations usable; actual Windows compilation follows this checkpoint before packaging claims.
- A clean `af3baa9` Everyday onefile using the separately compiled JSON vision adapter is building independently. This tests the second modular LLM interface inside a complete application, beyond its earlier relocated worker probes.

## Iteration 48 — second LLM interface verified inside one executable

- Built a clean `af3baa9` Everyday vision-only Linux executable containing the JSON worker, its standalone Python runtime, native llama.cpp descendant, SmolVLM Q4 model and projector. The 295.4 MB single file needs no external Python/model installation for its tested operation.
- Actual headless and native GUI transcription passed through `json-cli-v1`. All four packaged process-tree resource workloads passed: the largest observed RSS was 679,141,376 bytes for the cap-sized GUI workflow, below Everyday's decimal 1 GB budget.
- Verified the saved report against the actual binary SHA256 and unchanged clean source identity before retaining it. Embedded provenance records the adapter and exact model/projector hashes. These are Linux CPU single-method measurements; no Arabic, Windows, neural-combination or complete CUDA-onefile claim is inferred.
- The icon iteration passed 219 tests, Ruff, ICO decoding and actual prior-PE inspection before push. Its Pocket Linux/Windows compilation run `43011766996` is active. Studio compact-model workflow `43007639337` has passed Linux; its Windows job and the subsequent gated-release workflow remain active.

## Iteration 49 — paired-platform builds for the alternate LLM interface

- Added a curated `multimodal-json` composition to the common builder, platform workflow and paired release verifier. It retains classical and bilingual neural OCR, and compiles one standalone JSON CPU bridge for its vision choices.
- Alternate manifests reuse the verified model/projector files without duplicate downloads or changing prompts, language declarations, input limits, display names or the original native manifests. Distinct IDs and artifact names allow the two runtime choices to coexist. Studio retains both SmolVLM and Qwen.
- Centralized curated variant names/model selections. The release gate requires every vision pack in the JSON composition to identify the JSON adapter and still verifies every model/asset and all platform resource workloads before publication.
- All 222 tests and Ruff passed, including pack-swap, two-model retention and release-verifier checks. The first real Linux/Windows combined JSON build follows this checkpoint; previous Linux single-method evidence does not substitute for those gates.

## Iteration 50 — complete Studio evidence and honest diagnostic bounds

- Workflow `43007639337` at clean `25c7477` passed every CLI/native GUI check and twenty resource scenarios on each platform for classical, neural, SmolVLM Q4 and Qwen. Retained ten raw reports and the matched model/binary CI index: maximum observed RSS was 3,254,996,992 bytes on Linux and 3,138,465,792 bytes on Windows. The compact combination launches successfully; the exact cause of the earlier missing-header WinError 193 artifact remains unproven.
- Pocket workflow `43011766996` at clean `8fa1f03` passed all eight platform resource scenarios, with 227,549,184 / 174,751,744-byte Linux/Windows maxima. Retained its reports and actual Windows PE diagnostics containing icon and group-icon resources.
- The subsequent Studio release workflow at `0ed066a` failed Linux's large-image Qwen GUI case at the smoke harness's fixed 120-second deadline despite a 3,254,956,032-byte peak and a 300-second allowed inference attempt. Publication stayed blocked and the full failed report is retained.
- Centralized existing worker/probe limits and derived finite diagnostic deadlines from method, possible CPU fallback, iterations and startup/GUI allowances. The actual inference limits, pixel caps, memory budgets, accuracy checks and required scenario counts remain unchanged.
- Fixed observer timeouts abandoning the report: failed cases now retain deadline/status, sampled RSS and error details. Both observer and smoke commands clean owned descendants on timeout/interruption. Diagnostic log tail reads are bounded.
- A scaled real-Qt regression reproduced premature cancellation with the old policy and passed with the new one. Real subprocess tests retain timeout measurements and verify descendant cleanup. All 225 tests and Ruff passed; the release CLI also imports without site packages. Fresh packaged Studio verification follows the clean checkpoint.

## Iteration 51 — published combined JSON runtime for both operating systems

- Workflow `43012855397` at clean `65f6b1f` completed Linux, Windows and the strict release job successfully. Published `v0.1.0-everyday-multimodal-json-preview.8` with two native onefiles and nineteen assets covering manifests, per-method resources, neural accuracy and checksums.
- Both platform binaries include Fast, Precision, the bilingual neural worker/models and the separately compiled JSON vision bridge with compact English SmolVLM Q4. All sixteen resource scenarios passed per platform; observed maxima were 658,493,440 bytes Linux and 561,381,376 bytes Windows. Every neural corpus run completed all eleven fixtures at 3.9% CER / 7.5% WER.
- Matched the public release evidence against retrieved CI profiles, individual checksums, all eight resource reports and canonical corpus results before adding the raw reports/index and updated download links. Windows native icon resources are also retained in its layout report.
- This adds genuine Windows CPU and multi-method onefile proof for the second LLM adapter. It does not infer a CUDA onefile, Arabic capability for the English model or a universal RAM ceiling. The earlier native-interface composition remains available.
- Corrected Studio verification is running independently at `5dec752`; the earlier deadline-limited release remains failed rather than being relabeled as passed.

## Iteration 52 — isolated runtimes and native bilingual desktop checks

- Prevented packaged classical OCR from silently borrowing a system executable or language directory when its bundled assets are missing. Source development fallback and explicitly selected external assets remain supported. Missing/inapplicable packaged methods now have user-facing messages instead of developer setup instructions.
- Added a shared isolated test environment: remove Python/OCR/plugin/loader overrides, restrict PATH to OS directories, use private configuration and Arabic runtime temporary paths, and give resource images Arabic filenames. Windows SystemRoot/case handling is validated independently. Source benchmarks retain their intentional runtime overrides and record that narrower policy.
- Switched platform workflow GUI checks to private X11 on Linux and Win32 on Windows. New build metadata declares the validation requirement; both release verifiers reject missing isolation or a GUI result that does not confirm the actual native backend. Default-edition evidence now also binds the benchmark controller's source identity.
- Compiled GUI diagnostics now send mouse events only to their own source widget, select a genuine Arabic region, verify linked highlighting/selected copying and read Copy all back through Qt's clipboard API. VLM results retain no fabricated source selection. Screenshots and GUI records of the fixed public sample are kept for review, including failures when files exist.
- Preliminary Linux probes on existing Pocket and JSON vision binaries passed with developer search paths removed and Arabic runtime directories. Those older builds do not prove the new native-platform/copy contract; fresh complete builds are required.
- Real source Qt/clipboard and process-isolation checks passed with the full 236-test suite and Ruff. Release tools still import without site packages. Native compiled screenshots, all model combinations and both operating systems follow the clean checkpoint before new portability claims.

## Iteration 53 — loader preflight and published Studio downloads

- The stricter `85835ee` builds failed honestly: Linux's real X11 plugin could not load, and Windows source validation exposed a test reading UTF-8 JSON through its default legacy encoding. No release was published from those failed workflows; the `v0.1.0-preview.3` tag remains unchanged.
- Qt's actual Linux dependency inventory and official requirements identify separate ICCCM/key-symbol dependencies that were absent from the CI compilation inventory. Added `libxcb-icccm4` and `libxcb-keysyms1` explicitly to both native build environments. The generic cursor warning was insufficient to identify the missing dependencies by itself.
- Added a no-display loader preflight before bundling/compilation and a second check of the generated standalone X11 plugin. Unresolved dependencies fail the build and retain loader diagnostics. A genuine compiled shared-library test passes with its dependency present and fails after the dependency is removed; local wheel and existing packaged-plugin checks also pass.
- Corrected both new UI test report reads to explicit UTF-8 and emulated Windows's legacy default in the Arabic clipboard regression. The application had passed its Windows clipboard assertions; report decoding caused the test failure.
- Workflow `43015398593` at clean `5dec752` completed both platforms and publication of `v0.1.0-studio-multimodal-preview.9`. Verified its public index against all ten retrieved resource reports, exact binary hashes, clean source and all twenty cases per platform. Observed peaks were 3,256,041,472 bytes Linux / 3,140,337,664 bytes Windows; neural accuracy completed eleven cases on each at 3.9% CER / 7.5% WER.
- Retained the public Studio index/raw reports, replaced outdated pending-release wording and added exact downloadable Pocket/Everyday/Studio assets for both systems. The published snapshots retain their original GUI evidence scope; they do not inherit the newer native-platform validation contract.
- The complete 237-test suite, Ruff and bare-Python release-tool import pass. Corrected compiled X11/Win32 workflows follow this checkpoint; no native startup fix is certified until they pass.

## Iteration 54 — consistent GUI launch options

- Found that explicit language/backend/layout, external manifests and cleanup flags were ignored when opening a GUI workspace. Added a small immutable GUI launch-options module boundary and kept omitted choices distinct from overrides, so saved GUI preferences and existing headless automatic defaults remain intact.
- A single external vision/neural manifest now infers and selects its matching method, validates/resolves its relative assets and remains a session import. Conflicting pack/method arguments fail before opening the app. Explicit unsupported language requests fail instead of silently selecting the model's language.
- Image cleanup applies only after a successful launch-image load. A shared recipe setter synchronizes controls, cancels stale preview work, updates the preview and preserves ordinary reset/link invalidation behavior. Hidden GUI diagnostics use the same launch recipe.
- Invalid launch windows are disposed without saving partially applied preferences. Regression coverage verifies unchanged configuration bytes after a selected English model rejects an Arabic launch request.
- Both external model families were exercised without installation. A real native-Qt source OCR workflow read an inverted, rotated Arabic-named image with the requested cleanup, retained Arabic/English text and source links, and reset cleanly. A separate offscreen GUI smoke verified real located selection and Qt clipboard copying; its screenshot was visually reviewed. This is source/offscreen evidence, not a new packaged/native-platform certification.
- All 242 tests and Ruff passed. Iteration 53's exact-source default, JSON Everyday and Studio platform builds remain active independently; no running build checkout was changed.

## Iteration 55 — prevent loader checks borrowing developer libraries

- Tightened the Linux X11 loader preflight to remove developer `LD_LIBRARY_PATH` / `LD_PRELOAD` overrides and force stable C-locale diagnostics. A desktop language or developer library directory must not conceal an unresolved packaged dependency.
- Extended the actual shared-library regression by moving its dependency into a developer-only directory, putting that directory on `LD_LIBRARY_PATH` and requesting an Arabic locale. The preflight still rejects the unresolved deployment dependency and retains its exact name. The focused native test and Ruff passed; application behavior is unchanged.
- Added local private-X11 validation to the next verification step: download/extract Xvfb into the ignored diagnostic directory without installing system packages or interacting with the user's desktop. Native-window results remain pending at this clean checkpoint.

## Iteration 56 — compiled private-X11 proof and actionable Windows failures

- Compiled the complete Linux Pocket onefile at clean `b727c8e` with the new launch behavior and loader isolation. Both plugin preflights passed. The binary then passed real CLI/native-X11 GUI checks with developer overrides removed, Arabic runtime directories and genuine Arabic located selection/clipboard copying.
- All four complete-tree resource scenarios passed: 106,041,344 / 104,943,616 / 127,430,656 / 260,603,904-byte sample, inverted, cap-sized headless and cap-sized GUI peaks. Source/binary stayed unchanged. Retained the exact raw report, basic GUI record and visually reviewed public-sample screenshot.
- The new Windows default builds compiled successfully but failed classical CLI recognition under the isolated Arabic runtime environment. Correcting the earlier encoding-only source test did not resolve this separate native failure. The Everyday JSON Windows binary did pass genuine Win32 neural selection/clipboard copying and all four neural resource cases before classical OCR failed; the composition remains failed and unpublished.
- Added bounded redirected CLI/GUI diagnostics so attach-mode Windows errors cannot disappear with a missing CI console. A real failing child regression retains its Unicode error after more than 64 KiB of preceding output. Failure/timeout log tails are included in both build workflows.
- Added an independent Windows source-worker probe/workflow that compares ASCII, Arabic-temp, Arabic-runtime and combined cases with the actual code page and error text. It copies only prepared classical assets into its private temporary directory and cleans owned processes on timeout. This investigates the failing native boundary without another full compile; no speculative Unicode workaround is claimed yet.
- All 243 tests and Ruff passed. The Windows path probe follows this checkpoint; existing exact-source platform runs remain separate, including Linux CI's still-running dependency installation.

## Iteration 57 — signed Ubuntu dependency setup without failing runner mirrors

- Source workflow `43045950534` eventually failed package installation: its runner-provided mirrorlist repeatedly could not resolve `azure.archive.ubuntu.com`. This is a dependency transport failure before application tests, separate from the earlier missing X11 libraries and the successful local native run.
- Replaced duplicated workflow apt commands with a small installer restricted to disposable GitHub Actions Ubuntu 22.04 runners. It uses task-private source/index configuration for the official signed Ubuntu main, updates and security archives, retains the Ubuntu signing key, bounds network retries/timeouts and fails on update errors.
- The helper leaves system repository configuration intact, removes its private lists on exit and refuses local execution. All three Ubuntu workflows retain their requested dependency lists, including the native X11 additions. Bash syntax and the local refusal guard passed. Actual hosted archive connectivity follows the pushed source checkpoint; no CI success is inferred from shell validation.

## Iteration 58 — UTF-8 native worker manifests for Arabic Windows paths

- Windows source probe `43048291668` at clean `a671ae0` demonstrated the failure with native ANSI code page 1252: ASCII recognition passed; Arabic temporary paths failed image reads; Arabic runtime paths failed both traineddata loads. Retained its exact four-case report. This establishes the native classical path boundary independently of onefile packaging.
- Added a Windows resource updater that reads the copied engine's existing manifest as data, preserves its resource languages/settings and requests Microsoft's per-process UTF-8 active code page. It modifies only `runtime/bin/tesseract.exe`, retaining other resource entries and the installed engine. It does not change the system locale or depend on 8.3 aliases.
- Runtime preparation retains the resulting XML and a modification notice, then hashes the actual modified executable with all other assets. Source/configuration tests verify existing execution-level/DPI settings survive and repeated manifest application is stable. Windows 11 is the requested platform; the underlying process-code-page feature requires Windows 10 version 1903 or newer.
- Retained the previous combined binary's successful native Win32 neural GUI/resource reports separately: actual Arabic line selection, linked highlighting and clipboard copying passed, while classical failure prevented publication of the composition. Its screenshot was visually reviewed. This is partial method evidence and not a paired release.
- All 245 tests and Ruff passed locally, including native loader and bounded diagnostic checks. The updated actual Windows worker probe follows this checkpoint; full packaged verification remains required even if source path cases pass.

## Iteration 59 — verified Windows path correction and reliable font fallback

- Windows probe workflow `43049176735` at clean `e949d48` passed all four ASCII/Arabic runtime/temp combinations with genuine bilingual OCR output after private-engine manifest preparation. The parent/system code page remained 1252. Retained the complete passing report alongside the original three failing cases; no global locale change or short-path alias was required.
- Reviewed the actual Win32 neural screenshot and removed the editor's hardcoded Noto Sans requirement. The application now requests a Qt font-family fallback list ending in the OS general font, with an explicit sans-serif hint; the editor inherits that same choice. QSS no longer overrides it with a separate family list. This avoids depending on Linux fonts being installed on Windows.
- GUI evidence now records the resolved UI/editor font families. A genuine private-X11 source smoke used Noto Sans for both and passed Arabic region selection/clipboard checks. Source widget tests require an available intended sans family on hosts that supply one. Actual new Windows font resolution remains a source/packaged CI check, separate from screenshot inference.
- All 246 tests and Ruff passed. New complete onefile/platform/model validation follows this clean checkpoint; older failed native candidates remain failed, and published snapshots retain their original source/evidence scope.

## Iteration 60 — bounded signed mirror fallback for hosted DNS failures

- Actual hosted source runs confirmed that direct `archive.ubuntu.com` and `security.ubuntu.com` DNS also fail, so removing the Azure mirrorlist alone was insufficient. These runs failed dependency setup rather than application tests.
- Added a fixed HTTPS Princeton Ubuntu mirror fallback, a transport also used in Canonical's Landscape documentation. The helper first checks all three suite indexes through bounded requests, then requires ordinary Ubuntu archive signatures/package hashes through apt. It does not disable TLS, trust a new signing key, change the Ubuntu release or rewrite system repositories.
- Moved disposable public apt indexes under `/tmp` so `_apt` can traverse them independently of the runner's private work-temp parent. Cleanup remains confined to the helper-created directory, and the local-execution guard remains in place.
- Local HTTPS checks reached the mirror's Jammy base/security indexes; Bash syntax and diff checks passed. Actual hosted mirror reachability remains a new source-CI gate. Windows source validation at `3ebd77c` passed, including resolved-font widget checks and native runtime preparation; full packaged checks are still running separately.

## Iteration 61 — complete XCB dependency inventory and native Windows correction

- Source workflow `43049995332` at clean `af3e3f8` passed both platforms using the signed Princeton transport. Linux reported 245 passed / 1 skipped; Windows 240 passed / 6 skipped, alongside lint, real headless OCR and accuracy reporting. The local suite remains 246 passed. Platform skips retain their actual scope rather than being counted as executed tests.
- The default Linux native build then failed its new *early* loader gate with the precise remaining dependency `libxcb-shape.so.0`. ICCCM/key-symbol/cursor libraries now resolved. Centralized the complete required Qt/X11 package list, including `libxcb-shape0`, in the shared installer for all three workflows; callers retain only their OCR/compiler/display-specific extras.
- Curated variant preparation now checks the Qt loader before downloading vision weights or compiling a JSON bridge, in addition to the outer builder's existing checks. This prevents expensive model preparation from masking an incomplete GUI build environment.
- Windows default Everyday and Studio builds at clean `3ebd77c` completed native Win32/classical OCR and all resource cases successfully after UTF-8 preparation. The retrieved Studio GUI record confirms actual **Segoe UI** for both workspace/editor, Arabic located selection and clipboard copying; its maximum resource peak was 557,826,048 bytes. Linux failures prevent a paired release from that run, and these are default classical editions rather than the model-rich Studio composition.
- Bash syntax, focused loader/variant checks and Ruff pass. Fresh Linux compiled verification follows the corrected complete dependency inventory; previous failed tags and runs remain unchanged.

## Iteration 62 — faster screenshot paste without PNG round trips

- Replaced clipboard PNG encoding/decoding with a bounded Qt-to-Pillow pixel transfer. It normalizes channel order/alpha, flattens transparent pixels onto white and returns owned RGB data before the temporary Qt buffer goes away. Existing clipboard prechecks, file loading, edition caps and source/reset behavior remain intact.
- Verified pixel identity against the lossless PNG reference for padded RGB rows, straight/premultiplied alpha, grayscale and indexed palettes. Tests mutate/free the original Qt image, verify white transparency handling, reject oversized/null inputs and retain the Pocket processing cap.
- A real Qt clipboard test changes the clipboard and original QImage after paste, then completes Arabic/English OCR with linked text from the retained image. Capture integration uses the same paste path.
- An initial owned-data experiment reduced a 2 MP conversion from 223 ms to 3.9 ms and an 8 MP conversion from 851 ms to 13.3 ms with identical RGB pixels. Added a repeatable benchmark with alternating method order and source/dependency identity; clean-checkpoint measurements follow. These are in-process conversion timings, excluding native clipboard-provider decoding, transfer, OCR and packaged memory certification.
- The full 254-test suite and Ruff pass. In parallel, all six default binaries at clean `dac37a9` have passed their native platform/resource jobs and the release job is active; model-rich native checks remain active at that same frozen source. This paste improvement does not change those running build checkouts or retroactively enter their evidence.

## Iteration 63 — published native-platform editions and measured clipboard conversion

- Workflow `43051274081` at clean `dac37a9` completed all six native builds and the strict release job, publishing `v0.1.0-preview.7` with twenty-seven assets. Retrieved small public metadata/checksums and verified all six profiles, unchanged source/binary records, exact hashes, native/isolation policy and twenty-four passing resource scenarios before retaining the reports/index.
- Pocket's maximum observed complete-tree RSS was 236,044,288 bytes Linux and 234,164,224 Windows; Everyday 452,354,048 / 372,678,656; Studio 650,006,528 / 556,900,352. These are default/classical compositions, independently of the model-rich releases still being refreshed. Updated the Pocket direct downloads and exposed the fresh native classical editions.
- Ran the reproducible clipboard conversion benchmark from clean `150ef2f`: three alternating-order repetitions per method and exact RGB checks all passed. Median PNG/direct times were 207/3.5 ms for 2 MP and 829/12.5 ms for 8 MP owned random images. Retained raw source/dependency/timing evidence and its conversion-only scope; OS clipboard decoding and packaged RAM remain distinct.
- Latest complete local verification remains 254 passing tests and Ruff. The native published binaries predate the direct clipboard optimization. Both model-rich native platform workflows at `dac37a9` remain active; their individual results and strict release jobs determine publication.

## Iteration 64 — compiled clipboard-input gates and explicit pixel ownership

- Made Qt buffer ownership explicit on the temporary borrowing Pillow image before creating independent RGB pixels. This protects the transfer from compiled/local-variable lifetime changes without retaining Qt pixels on the returned source image.
- GUI diagnostics now set the owned test image on their own Qt clipboard and call the application's actual Paste image path before recognizing. Cap-sized onefile RAM scenarios use the same diagnostic, so future packaged measurements include the paste/conversion phase and retained clipboard image. Source repeated-GUI workloads also paste each input.
- New build metadata declares `clipboard_image_input`; both release verifiers require the actual GUI resource record to identify its clipboard input route. Existing published profiles retain their original file-input scope. Headless scenarios continue verifying file input independently.
- Failed paste now stops immediately instead of recognizing a previous image. A genuine Qt regression with an already recognized result and an unavailable new image verifies the error exit and absence of a recognition call. Native-platform policy tests reject absent/file routes for new builds.
- All 255 local tests and Ruff pass. A clean Pocket onefile build and private-X11 cap-sized paste/RAM checks follow this checkpoint; model-rich builds already running at `dac37a9` do not inherit this newer paste claim.

## Iteration 65 — native Everyday publication and compiled Pocket paste proof

- Workflow `43051274800` at clean `dac37a9` passed both platforms and its strict release job, publishing `v0.1.0-everyday-multimodal-json-preview.18`. Verified public profiles/checksums against every per-method report, all thirty-two native resource cases and shared clean source. Retained the native index/eight reports and updated the four-method downloads.
- Everyday observed maxima were 665,980,928 bytes Linux / 584,425,472 Windows. Both eleven-case neural corpus runs retained 3.9% CER / 7.5% WER. This is actual combined JSON-runtime, classical, neural and compact English-VLM proof on X11/Win32 with isolated Arabic paths; the earlier release remains historical evidence.
- Built the complete Linux Pocket clipboard variant at clean `51f1408`, then passed real CLI and private-X11 clipboard-input GUI checks. All four resource cases passed, with a 268,468,224-byte GUI maximum below the 350,000,000-byte budget. The result confirms the actual clipboard input route and Arabic source selection/copying, including compiled Qt/Pillow ownership.
- Retained the exact resource/basic-GUI records and verified unchanged source/binary hashes through the shared release-policy checker. Both source CI platforms at `51f1408` also passed; the complete local suite is 255 tests.
- Started fresh default/model-rich builds at that frozen clipboard source under `v0.1.0-preview.8` and the model workflows. The preceding Studio native refresh at `dac37a9` is still performing its resource checks; no active build is relabeled or canceled merely for taking time.

## Iteration 66 — published clipboard-input editions and next modular review

- Workflow `43055836729` at clean `51f1408` passed all six native clipboard-input builds/resource jobs and its strict release job, publishing `v0.1.0-preview.8`. Retrieved the public small metadata/checksums and verified every declared clipboard policy, actual route/backend, unchanged source/profile/binary identity and all twenty-four required cases before retaining the index/six reports.
- Maximum complete-tree RSS was 249,655,296 / 241,475,584 bytes Linux/Windows Pocket, 484,122,624 / 405,090,304 Everyday, and 650,403,840 / 621,875,200 Studio. These include actual cap-sized pasting and each launcher. Updated the Pocket downloads and latest native classical release link without extending this evidence to an untested model combination.
- The prior model-rich Studio native refresh has now passed both platform jobs and is in strict release verification. The newer model-rich clipboard runs remain active at `51f1408`; their results determine publication independently.
- Revisited remaining original requirements: bundled CPU models still need a clean way to attach a stable external GPU helper, and Pocket local-model choices require complete memory/accuracy evidence before relaxing edition restrictions. Added separate modular gates for those improvements. Existing Linux GPU/fallback source evidence and classical Pocket passes are not substitutes for those future configurations.
- Source/application code remains the already verified 255-test clipboard revision. This iteration changes only reviewed public evidence, documentation and the next modular work items; the working tree is clean after commit/push.

## Iteration 67 — paired model-rich releases and explicit Arabic VLM probes

- Studio native workflow `43051280875` at clean `dac37a9` completed both platforms and publication of `v0.1.0-studio-multimodal-preview.19`: forty passing resource cases across five methods, with 3,275,939,840-byte Linux / 3,202,158,592-byte Windows maxima. Retained the index and ten per-method reports.
- Everyday clipboard workflow `43055836497` at clean `51f1408` published `v0.1.0-everyday-multimodal-json-preview.20`: thirty-two native clipboard/resource cases with 703,029,248 / 616,587,264-byte Linux/Windows maxima. Retained its index/eight reports. Both releases' neural evaluations completed eleven cases per platform at 3.9% CER / 7.5% WER.
- Verified downloaded small metadata bytes against aggregate checksums before normalizing JSON for the repository, then checked individual binary checksums, source/profile identities, every scenario and declared native/clipboard scope. Updated the primary model-rich downloads without overwriting older evidence.
- Found a smoke-check gap: bilingual VLMs previously had only an English sample assertion. New expectations follow the actual selected pack's declared languages and validate both CLI/GUI language metadata and corresponding public-sample text. Arabic-only and English-only compatible packs keep their intended scope.
- Audited actual Qwen GUI text from both native artifacts. Linux's first Arabic line matches; Windows reads `مربح بالعالم` instead of `مرحبا بالعالم`, while both read the second Arabic sentence correctly. Retained both complete records and documented this word error explicitly. The basic VLM capability probe requires an expected Arabic phrase, without presenting it as full corpus accuracy or changing the corpus's strict normalization.
- All 267 tests and Ruff pass, including missing-language, selected-pack and optional-mark cases. Studio's newer clipboard run at `51f1408` remains active. The application/engine code in that running build remains unchanged; the new language assertions apply to subsequent diagnostic runs.

## Iteration 68 — retain native failure status before choosing a runtime fix

- Studio clipboard workflow `43055841931` at clean `51f1408` finished Linux successfully but failed Windows's initial native SmolVLM CLI read, after neural/Fast/Precision checks. The failure occurred before the paste path for that method and prevented publication. Retained its original worker log and a compact index distinguishing known completed cases from the unknown native status/cause.
- The error text retained stderr but discarded the child's numeric exit status. Core process errors now preserve that code and its Windows hexadecimal form. The standalone JSON bridge also appends its native descendant's status after the bounded stderr tail, so an outer worker cannot hide it by returning its generic protocol error code.
- Actual subprocess tests preserve Unicode stderr plus a nonzero status. A Windows-only native ExitProcess test covers an NT status, and bridge tests retain nested statuses after a long log. Local validation is 268 passed / 1 Windows-specific skip, with Ruff clean; no runtime fix is inferred from better diagnostics.
- Added a bounded Windows reference-binary probe: verify the public Studio preview.19 checksum, run ASCII/Arabic temporary paths under automatic/CPU selection, retain handles only for native descendants of the launched process, and collect actual exit statuses plus sampled private/RSS usage. Process identity is checked against PID reuse and owned descendants are cleaned on timeout.
- The reference binary is explicitly the previously passing public snapshot, not the unavailable failed executable. Four successful reference runs would not establish the original failure's cause or repair it. The focused hosted probe follows this checkpoint before changing CPU kernels, limits or model artifacts speculatively.

## Iteration 69 — recover when optional CUDA helpers disappear

- Both source CI platforms passed at clean `956c3e0`, including the actual Windows native exit-status test. Dispatched the bounded reference probe as workflow `43067260969`; its results remain pending at this checkpoint. This independent fallback correction does not explain or repair the earlier Windows Studio crash.
- Reviewed M66 and found that a removed optional CUDA helper blocked all inference during pack validation, including explicit CPU selection. Vision and neural inference now validate their required CPU/model files independently, then use the intact CPU worker when that optional helper is missing. Automatic/preferred-CUDA requests report the fallback; explicit CPU does not require or probe the absent helper.
- Manifest import, Settings saves and build preparation retain strict validation of every configured asset. Missing CPU runners, weights, projectors and neural dictionaries are still errors. Existing CUDA driver-error retry, cancellation, containment and budget policies remain unchanged.
- Six regression cases remove a previously valid helper and verify automatic, CPU and preferred-CUDA dispatch for both engine families; they also confirm required model-file removal still fails before another worker launch. The complete local suite passed 274 tests with one Windows-only skip, and Ruff/diff checks passed.
- Actual Linux SmolVLM Q4 source inference with a deleted helper completed on CPU, read the English sample and reported fallback: 479,117,312-byte sampled tree RSS and 3.69 seconds. This is source inference evidence rather than a new packaged RAM certificate or a neural GPU claim. Stable user-configured helpers for bundled model assets remain the next M66 step.

## Iteration 70 — stable CUDA helpers for embedded weights

- Added optional external helper selections for built-in vision and neural packs while retaining managed CPU/model assets. Preferences are keyed by engine family, model ID and runtime adapter, so Everyday's JSON worker and Studio's native llama.cpp helper do not cross accidentally. Fresh extraction paths are resolved from current manifests; only the external helper path is persisted separately.
- Native settings now allow browsing/saving/clearing these helpers without duplicating weights. Clearing restores the current bundled default; absent optional helpers remain visible for correction while CPU inference stays available. Choices inside the managed runtime are rejected, including resolved aliases, to avoid saving a temporary executable. Existing external packs keep their ordinary manifest configuration.
- Core/settings checks cover fresh extraction, unavailable editions, helper deletion, unchanged preferences after invalid choices, adapter/model/family isolation, immutable CPU assets and restoring built-in defaults. The complete suite passed 279 tests with one Windows-only skip; focused settings checks and Ruff passed after the visual review.
- Actual Linux source inference reused the existing SmolVLM Q4 weights through the configured native CUDA helper, then honored explicit CPU selection: CUDA 1.96 seconds / 446,025,728-byte sampled tree RSS; CPU 3.12 seconds / 479,399,936 bytes. Retained source/asset/helper identities and the dirty-development scope in `local-bundled-helper-cuda.json`. This is not a new onefile, neural-CUDA or Windows-GPU certification.
- Reviewed actual private-X11 settings captures and corrected default gray tab/page backgrounds to match the workspace. Built-in CPU fields remain read-only, the optional CUDA action stays available, and empty neural configurations disable unavailable option controls. Retained the reviewed source captures separately from packaged evidence.
- Windows reference probe `43067260969` at clean controller `956c3e0` passed all four ASCII/Arabic × automatic/CPU runs on an AMD EPYC 7763 runner. All observed native workers exited `0x00000000`; decode-worker sampled maxima were 418,189,312-byte RSS and 577,159,168-byte private memory. These are distinct counters, not whole-app RAM certification. Retained the complete report with the public Studio preview.19 binary SHA; this passing reference does not resolve the unavailable preview.21 candidate's original failure.
- Both source CI platforms also passed the preceding CPU-fallback checkpoint `1d0ae47`. A new compiled Studio diagnostic candidate remains necessary to reproduce any newer failure with its actual native status and retained executable before claiming a runtime repair.
