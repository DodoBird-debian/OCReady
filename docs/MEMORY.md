# Memory budgets and measured evidence

The budgets are decimal **350,000,000 / 1,000,000,000 / 4,000,000,000 bytes** for Pocket / Everyday / Studio. They cover the application plus its descendant OCR processes. GPU VRAM is separate. A weight file's byte size is a lower bound, not an inference memory measurement.

Image admission is part of the budget. Pocket processes at most 2 million pixels, Everyday 8 million, Studio 16 million. Inputs above twice those pixel counts (and above the global 32 million decode limit) are rejected **before decoding**, because resizing an arbitrarily large compressed image can itself exhaust RAM. Accepted images are fitted to the processing cap. The UI displays the working image dimensions.

## Linux workload measurements

Machine: AMD Ryzen 5 3600, Debian 13, Python 3.12.16, Qt/PySide 6.8.3, Tesseract 5.5.0. Native source runs used the offscreen Qt platform. Samples include the observed root process and all descendants every 10 ms. Shared library mappings may be counted more than once, making these RSS sums conservative relative to physical-memory ownership.

| Workload | Pocket / 350 MB | Everyday / 1 GB | Studio / 4 GB |
| --- | ---: | ---: | ---: |
| Small bilingual screenshot | 78.0 MB | 98.1 MB | 98.0 MB |
| Dark screenshot + inversion | 78.2 MB | 109.3 MB | 98.1 MB |
| Image at processing pixel cap | 96.2 MB | 206.6 MB | 326.8 MB |
| Native GUI, four repeated cap-sized jobs | 241.5 MB | 516.4 MB | 789.3 MB |

Everyday and Studio used Precision (best language data); Pocket used Fast. The repeated GUI workload includes loading, display, recognition, and retained buffers between four documents. It does not prove an absence of leaks over an unlimited session. These runs passed their respective budgets.

The compiled Linux Pocket onefile artifact at `65bd416` passed four cases while an external observer included the onefile launcher and extraction overhead: 200.1 MB sample, 200.2 MB inverted image, 200.0 MB cap-sized image, and **313.6 MB for the full cap-sized GUI**. The prior 3 MP Pocket cap reached 347.3 MB. Reducing it to 2 MP restored useful headroom. The internal governor also counts Nuitka's actual parent launcher, after verifying the environment PID is the real OS parent.

A separate real GLM-OCR Q8 CPU run on the small bilingual image observed 1.86 GB total RSS. A compatible locally built CUDA runner completed the same image in 6.9 seconds with 1.24 GB host RSS; an incompatible upstream runner had already exercised real CPU fallback. These are different workloads from the table and do not certify large-image VLM inference.

An Everyday vision-only onefile build from clean source `e9cdf23` contains the CPU runner, SmolVLM Q4 model and projector in a 269.7 MB executable. All four external memory scenarios passed, including **921.2 MB for the 8 MP GUI case** and 826.7 MB for cap-sized headless input. The report includes the executable SHA256, clean source revision, included model hashes, dependency versions and distinct worker allocation counters. [Raw embedded-vision measurements](benchmarks/linux-everyday-smolvlm-q4-onefile.json). This tiny model supports English; these numbers are memory evidence, not evidence of Arabic transcription quality.

Raw reports: [source scenarios](benchmarks/linux-source.json), [Pocket onefile scenarios](benchmarks/linux-pocket-onefile.json). Recognition text is omitted from benchmark reports.

## Releasing unused launcher pages

Nuitka 4.3.5's onefile launcher retains its linked, file-backed payload after extraction. New builds use a private compiler overlay to release unused launcher residency once extraction and decompressor cleanup finish. Linux applies `MADV_DONTNEED` only to whole pages inside the linked const blob; Windows requests a one-time trim of the launcher's own working set. Neither path changes another process or imposes a memory limit. The installed Nuitka package remains unchanged, including after build failure.

A controlled Linux onefile experiment used the same 48 MiB incompressible payload and verified its SHA256 after extraction. Steady launcher RSS fell from **62.4 MB to 2.0 MB**; launcher plus child fell from 90.0 MB to 29.5 MB. [Raw residency probe](benchmarks/linux-payload-residency-probe.json). These are steady-state probe measurements, not full-app or cold-start peaks. Full application and Windows builds require their own packaged checks.

The optimization does not promise that file-cache pages disappear from system RAM. It releases unused process residency; the OS may retain reclaimable cache. Unsupported or denied OS operations leave ordinary memory monitoring/admission in place. [Linux mapping semantics](https://man7.org/linux/man-pages/man2/madvise.2.html), [Windows working-set trim](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-setprocessworkingsetsize).

The overlay is version-checked against the locked compiler and records original/patched bootstrap and helper digests in the build manifest. `--no-payload-trim` provides an unmodified diagnostic build. An unknown compiler/bootstrap layout requires explicit review rather than a blind patch.

Clean-source `2ba93c6` full builds then passed real compiled CLI/GUI checks and all four externally observed memory workloads:

| Packaged workload | Pocket | Everyday, embedded English-only SmolVLM Q4 |
| --- | ---: | ---: |
| Small screenshot | 200.6 MB | 511.2 MB |
| Inverted screenshot | 200.8 MB | 510.3 MB |
| Image at edition processing cap | 199.3 MB | 556.5 MB |
| Full cap-sized native GUI | **242.4 MB** | **651.6 MB** |

These peaks include cold startup, the launcher and all OCR descendants. Pocket's cold extraction still dominates its smaller headless jobs; trimming is not a claim that every phase shrinks equally. The prior embedded-vision GUI case was 921.2 MB. Both source and binaries stayed unchanged during the new measurements. [Pocket raw report](benchmarks/linux-pocket-onefile-trimmed.json), [embedded vision raw report](benchmarks/linux-everyday-smolvlm-q4-onefile-trimmed.json). Windows checks remain separate.

A separate **source GUI** soak completed 100 cap-sized Pocket image loads/recognitions in one window. Its peak was 231.6 MB; mean idle RSS was 160.5 MB over the first ten jobs and 158.4 MB over the last ten. This is evidence of stable memory over that workload, not a proof of unlimited-session behavior or a compiled 100-job test. [Raw 100-job source soak](benchmarks/linux-pocket-soak-100.json).

## Streaming startup and current platform evidence

Clean `31d32ae` uses one-pass runtime extraction and Nuitka's supported low-memory build policy (level-3 compression in pinned 4.3.5). Both Pocket CI binaries passed CLI/native GUI smoke checks and all four packaged resource scenarios:

| Packaged workload | Linux | Windows |
| --- | ---: | ---: |
| Sample | 98.0 MB | 94.3 MB |
| Inverted sample | 97.6 MB | 94.4 MB |
| Cap-sized headless | 128.2 MB | 112.4 MB |
| Cap-sized GUI | 226.7 MB | 172.7 MB |

The reports retain exact executable hashes and unchanged clean-source identities: [Linux CI](benchmarks/ci-linux-pocket-stream.json), [Windows CI](benchmarks/ci-win32-pocket-stream.json). The separate local Linux binary from that revision peaked at 248.2 MB ([local report](benchmarks/linux-pocket-stream.json)); machine/build differences remain visible. Workloads include launcher residency. These are measured budget passes, not an absolute allocation ceiling.

The published four-method Everyday release at clean `3d2adb7` passed sixteen workloads per platform with 683.9 MB Linux and 622.6 MB Windows maximum observed RSS ([release evidence](benchmarks/everyday-multimodal-release.json)). Models are sequential and all embedded choices were exercised.

The later published JSON-runtime composition at clean `65f6b1f` passed the same sixteen resource scenarios per platform with **658,493,440-byte Linux** and **561,381,376-byte Windows** maxima ([release evidence](benchmarks/everyday-json-release.json)). It includes the JSON bridge, compact Q4 vision weights, classical OCR and bilingual neural OCR. Different weights, runtime packaging, source and machines prevent attributing the change to a single optimization.

A separate clean `af3baa9` Everyday Linux executable tests the alternate JSON vision interface end to end. It embeds the standalone JSON CPU worker, native descendant and compact English SmolVLM Q4 model/projector in a 295.4 MB onefile. All four resource workloads passed, with a 679,141,376-byte GUI maximum ([raw report](benchmarks/linux-json-smol-q4-onefile.json)). This is a single-method configuration and does not certify Windows, Arabic accuracy or another model combination.

Clean `31d32ae` Studio CI completed all twenty Linux resource workloads across five choices. Qwen reached the largest observed tree RSS, 3,255,017,472 bytes ([raw report](benchmarks/ci-linux-packaged-studio-multimodal-vision-qwen3-vl-2b-q4.json)). The matched Windows executable failed before launch, so the workflow failed overall and produced no verified paired release.

The compact SmolVLM Q4 + Qwen composition at clean `25c7477` subsequently passed all twenty packaged scenarios on **both** platforms. Linux peaked at **3,254,996,992 bytes** and Windows at **3,138,465,792 bytes**, under the 4,000,000,000-byte budget. The [paired CI index](benchmarks/studio-multimodal-verified.json) records source, exact binaries, matching model assets and scenario counts; individual reports are retained alongside it. The Windows launcher was 1,945,837,568 bytes on disk with a 1,946,038,272-byte mapped PE image ([layout](benchmarks/ci-windows-studio-q4-pe-layout.json)). This tested composition launches successfully; the earlier rejected binary's absent headers prevent claiming its precise loader failure cause.

The new branded Pocket binaries at clean `8fa1f03` also passed all four scenarios per platform: **227,549,184-byte Linux** and **174,751,744-byte Windows** maxima ([Linux](benchmarks/ci-linux-pocket-icons.json), [Windows](benchmarks/ci-windows-pocket-icons.json)). The [Windows layout](benchmarks/ci-windows-pocket-icons-pe-layout.json) includes icon/group-icon resources. These update the measured artifact identities rather than replacing older observations.

A later Studio release candidate at `0ed066a` stayed under budget in all four Qwen measurements, but its large-image GUI case exited with the diagnostic's fixed 120-second timeout ([failed report](benchmarks/ci-linux-studio-qwen-gui-timeout.json)). Publication remained blocked. Diagnostic envelopes now derive from the unchanged engine attempt limits, possible CPU retry and startup/GUI allowances; reports retain each outer deadline and timeout status. This corrects an inconsistent test deadline and does not count the failed run as passed or increase RAM budgets.

The local Linux Pocket build at clean `b727c8e` passed the newer isolated-runtime contract on a private X11 display: **106,041,344-byte sample**, **104,943,616-byte inverted**, **127,430,656-byte cap-sized headless**, and **260,603,904-byte cap-sized GUI** peaks. Its [raw report](benchmarks/local-linux-pocket-native-copy.json) confirms the actual `xcb` platform, Arabic filenames/runtime directories and matching unchanged source/binary. The [basic GUI record](benchmarks/local-linux-pocket-native-copy-gui.json) verifies clicking a real Arabic word, linked highlighting and selected/Copy-all clipboard readback. This is clean local Linux evidence, not Windows or a paired release. A reviewed [native screenshot](images/workspace-linux-x11.png) uses the fixed public sample.

The corrected deadline policy at clean `5dec752` subsequently passed all twenty resource workloads on each platform and published [Studio preview.9](https://github.com/DodoBird-debian/OCReady/releases/tag/v0.1.0-studio-multimodal-preview.9). Maximum observed tree RSS was **3,256,041,472 bytes Linux** and **3,140,337,664 bytes Windows**. The [public-release index](benchmarks/studio-multimodal-release.json) and ten `published-*-studio-*.json` reports retain exact binary/source/model identities. All eleven neural accuracy fixtures completed on both platforms at 3.9% CER / 7.5% WER. These reports used their original offscreen Qt GUI policy; later isolated native-platform gates require fresh binaries and evidence.

A local complete Studio binary at `3d2adb7` passed twenty workloads across classical, neural, SmolVLM Q8 and Qwen3 choices; its maximum observed RSS was 3,268.1 MB ([Qwen report](benchmarks/development-linux-packaged-studio-multimodal-vision-qwen3-vl-2b-q4.json)). Its source record is explicitly **dirty** because the build worktree's runtime symlink was untracked; source content and binary stayed unchanged throughout testing. This remains development evidence. It must not be substituted for clean CI or Windows validation. The initial Windows Studio build failed before launch with WinError 193; the smaller Q4 combination and PE layout diagnostics require fresh platform checks.

## Reproducing the measurements

```sh
uv run python scripts/benchmark.py --edition all
uv run python scripts/benchmark.py --edition pocket \
  --binary dist/pocket/OCReady-pocket-linux-x86_64 \
  --output test-output/pocket-onefile.json
```

The benchmark emits a nonzero exit code if an observed budget is exceeded or an OCR process fails. It runs each scenario in a fresh subprocess. The GUI case opens four cap-sized tiled bilingual documents, waits for each OCR job, and reports both idle memory and worker peaks.

## Whole-tree monitoring and worker containment

The recognition runner samples process-tree RSS every 40 ms, including the resident onefile launcher when present, stops a job that exceeds its edition's budget, and always cleans up the child process. The image decoder, processing pixel limits, sequential engine loading, one OpenMP thread, bounded context/output, and model admission reduce the chance of exceeding a budget. VLM preview and inference images share a per-pack cap, defaulting to one million pixels and a 1600-pixel longest edge, in addition to the runner's image-token limit. The larger working source remains available for cropping.

Workers now also receive an OS allocation allowance: edition budget minus the application's observed resident memory and a 16 MB reserve, rounded down to a page boundary. Jobs are refused before launch if fewer than 16 MB remain.

On a delegated Linux desktop, a small native gate waits while the user systemd manager attaches it to its own transient cgroup v2 scope. It then supervises the OCR engine. The scope sets `memory.max` and disables worker swap. A lightweight supervisor retains the scope until the app has observed the engine status and kernel OOM counters. Newer systemd versions use `OOMPolicy=continue`; older versions use their supported scope controls. Only the OCR engine receives a higher OOM selection score. The parent never changes another application's scope or system memory policy. Disposing the scope and private process group also removes grandchildren after their immediate parent exits. On this Debian desktop, a real 320 MB allocation was stopped under a roughly 96 MB worker allowance, without killing the app. Real bilingual OCR also completed inside a worker scope. Headless systems without a delegated user bus retain whole-tree RSS monitoring and process-group cleanup.

On Windows, the worker starts suspended, enters a Job Object with a job-wide committed-memory limit and kill-on-close behavior, and is then resumed. The Windows implementation and native allocation/descendant tests run in source CI; platform results are recorded in PROGRESS.md.

Result JSON reports `containment`, `worker_limit`, and `worker_peak`. The peak is the OS worker counter: cgroup charged memory on Linux or job committed memory on Windows. It must not be relabeled as RSS.

Sampling cannot prevent or observe every brief allocation spike. Worker containment strengthens allocation safety but is **not an OS-enforced absolute RSS ceiling for the complete application**. Linux charges a memory area to the cgroup that first instantiated it; moving a process does not move earlier charges, and shared file-cache pages may be charged elsewhere. The gate therefore joins before engine exec, minimizing earlier allocation, while the whole-tree monitor still counts mapped resident pages. Windows Job Object limits constrain committed memory rather than all resident DLL/file mappings. The UI and onefile launcher remain under whole-tree monitoring and admission limits, not the worker's OS limit. [Linux memory ownership](https://cdn.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html), [Windows job memory semantics](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information).

Linux `RLIMIT_AS` limits virtual address space, not RSS, and is unsuitable as a substitute. Full application containment from before onefile extraction and cross-platform certification remain open release gates.

Until those gates pass, these editions are measured target budgets for the documented workloads, rather than universal promises for every image, desktop, driver, or user-supplied model.
