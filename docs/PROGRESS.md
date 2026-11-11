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
