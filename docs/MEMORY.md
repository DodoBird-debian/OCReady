# Memory budgets and measured evidence

The budgets are decimal **350,000,000 / 1,000,000,000 / 4,000,000,000 bytes** for Pocket / Everyday / Studio. They cover the application plus its descendant OCR processes. GPU VRAM is separate. A weight file's byte size is a lower bound, not an inference memory measurement.

Image admission is part of the budget. Pocket processes at most 3 million pixels, Everyday 8 million, Studio 16 million. Inputs above twice those pixel counts (and above the global 32 million decode limit) are rejected **before decoding**, because resizing an arbitrarily large compressed image can itself exhaust RAM. Accepted images are fitted to the processing cap. The UI displays the working image dimensions.

## Linux workload measurements

Machine: AMD Ryzen 5 3600, Debian 13, Python 3.12.16, Qt/PySide 6.8.3, Tesseract 5.5.0. Native source runs used the offscreen Qt platform. Samples include the observed root process and all descendants every 10 ms. Shared library mappings may be counted more than once, making these RSS sums conservative relative to physical-memory ownership.

| Workload | Pocket / 350 MB | Everyday / 1 GB | Studio / 4 GB |
| --- | ---: | ---: | ---: |
| Small bilingual screenshot | 78.0 MB | 98.0 MB | 97.9 MB |
| Dark screenshot + inversion | 78.0 MB | 97.9 MB | 112.7 MB |
| Image at processing pixel cap | 111.5 MB | 206.5 MB | 326.9 MB |
| Native GUI, four repeated cap-sized jobs | 272.2 MB | 508.2 MB | 853.5 MB |

Everyday and Studio used Precision (best language data); Pocket used Fast. The repeated GUI workload includes loading, display, recognition, and retained buffers between four documents. It does not prove an absence of leaks over an unlimited session. These runs passed their respective budgets.

The compiled Linux Pocket onefile artifact also passed three headless cases while an external observer included the onefile launcher and extraction overhead: 199.5 MB sample, 200.4 MB inverted image, 199.8 MB cap-sized image. A full compiled GUI run at the pixel cap reached **347.3 MB**, just below 350 MB. This margin is too small for a comfortable release. The next iteration must reduce image-buffer pressure and include launcher residency in the internal governor. At this revision the internal monitor sees the application and its children; the external artifact benchmark also counts its onefile parent launcher.

A separate real GLM-OCR Q8 CPU run on the small bilingual image observed 1.86 GB total RSS. That is a different workload from the table and does not certify large-image VLM inference. CUDA discovery and real GPU failure fallback have been tested; successful CUDA inference remains unverified with the installed driver.

Raw reports: [source scenarios](benchmarks/linux-source.json), [Pocket onefile scenarios](benchmarks/linux-pocket-onefile.json). Recognition text is omitted from benchmark reports.

## Reproducing the measurements

```sh
uv run python scripts/benchmark.py --edition all
uv run python scripts/benchmark.py --edition pocket \
  --binary dist/pocket/OCReady-pocket-linux-x86_64 \
  --output test-output/pocket-onefile.json
```

The benchmark emits a nonzero exit code if an observed budget is exceeded or an OCR process fails. It runs each scenario in a fresh subprocess. The GUI case opens four cap-sized tiled bilingual documents, waits for each OCR job, and reports both idle memory and worker peaks.

## Guardrails versus strict containment

The recognition runner samples process-tree RSS every 40 ms, stops a job that exceeds its edition's budget, and always cleans up the child process. The image decoder, processing pixel limits, sequential engine loading, one OpenMP thread, bounded context/output, and model admission reduce the chance of exceeding a budget.

Sampling cannot prevent or observe every brief allocation spike. It is **not an OS-enforced absolute RAM ceiling**. Linux `RLIMIT_AS` limits virtual address space, not RSS, and is unsuitable as a substitute for this requirement. Strong containment needs delegated cgroup v2 memory limits on Linux, and memory-aware Job Objects on Windows, combined with a reserve for the UI and launcher. Those hard-limit integrations and cross-platform memory certification remain open release gates.

Until those gates pass, these editions are measured target budgets for the documented workloads, rather than universal promises for every image, desktop, driver, or user-supplied model.
