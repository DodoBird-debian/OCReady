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
