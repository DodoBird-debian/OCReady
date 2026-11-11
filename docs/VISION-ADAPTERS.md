# Swapping local models and inference runtimes

Model packs are the unit of configuration. Swap the pack in **Settings → Vision models**, then choose it in the method selector. Each pack owns its model, optional projector, CPU/CUDA runner paths, language declaration, prompt, output limit and image/memory limits. Installed models run sequentially. Existing manifests without an `adapter` field use `llama.cpp` automatically; no migration is needed.

The runtime adapter owns command construction, capability probing, its process environment and response decoding. Shared orchestration owns memory admission, contained subprocess execution, cancellation and CPU retry after backend initialization failure. The OCR pipeline and split image/text workspace do not depend on a model architecture. Pack data cannot import arbitrary Python modules: adapter identifiers select a fixed in-app registry.

## Built-in adapters

| Adapter ID | Model assets | Runner interface | Response |
| --- | --- | --- | --- |
| `llama.cpp` | GGUF model plus matching GGUF projector | `llama-mtmd-cli` | Transcribed stdout with known terminal/template artifacts removed |
| `json-cli-v1` | A model file; projector optional if the worker does not require it | Local executable implementing the contract below | Strict versioned JSON, exact input dimensions and actual backend |

The default adapter is already exercised with SmolVLM, GLM-OCR and Qwen3-VL. Choosing another GGUF model does not require changing application code, provided the runner supports that architecture and the matching projector. An integrated model or a different local inference runtime can use the JSON interface. Its worker remains responsible for its model format and preprocessing requirements. The adapter contract itself is not a claim that any arbitrary model fits an edition or reads Arabic accurately.

## JSON worker v1 contract

The application invokes the executable directly with an argument list, without a shell. Capability probing uses:

```text
worker --ocready-vision-capabilities
```

Successful stdout is one JSON object:

```json
{"schema":1,"backends":["cpu","cuda"]}
```

Declare only usable backends. A CPU worker can return `["cpu"]`. An incompatible probe is treated as unavailable CUDA; the inference response must still satisfy the protocol. Cancellation and memory failures are never converted into a second inference attempt.

Recognition uses:

```text
worker --ocready-vision-v1 --image INPUT.png --model MODEL \
  --prompt "Transcribe visible text" --max-output-tokens 512 \
  --backend cpu --max-image-tokens 1024 [--projector PROJECTOR]
```

The input is already bounded by the pack's image policy and has the requested reversible cleanup applied. Paths and the prompt are distinct arguments. The worker must stay offline, honor CPU-only requests and constrain output generation. If it creates descendants, they remain within the application's worker resource containment where the platform supports it.

On success stdout is exactly one JSON object, with diagnostic logs on stderr:

```json
{
  "schema": 1,
  "width": 1100,
  "height": 720,
  "text": "مرحبا بالعالم\nYour text is ready.",
  "backend": "CPU",
  "note": "Optional brief runtime note"
}
```

`width` and `height` must be integer dimensions of the supplied image. `text` is logical Unicode, at most 100,000 characters; the client does not reverse it or strip arbitrary content. `backend` is exactly `CPU` or `CUDA`. A CPU request cannot report CUDA. A CUDA request may report internal CPU fallback, which remains visible in the result. `note` is optional and at most 2,000 characters. Schema booleans, unsupported versions, malformed fields and mismatched dimensions are rejected.

Return a nonzero exit status for inference failure, with an actionable stderr message. The shared orchestrator retries once on the CPU runner only for a recognized CUDA/backend-initialization failure. Budget failures and cancellation stop the operation. Vision transcription has no source coordinates or invented confidence, regardless of adapter; use classical/neural OCR for linked regions.

## Pack example

```json
{
  "id": "my-local-vision",
  "name": "My offline model",
  "adapter": "json-cli-v1",
  "runner": "worker/vision-worker",
  "model": "model.onnx",
  "projector": "",
  "cuda_runner": "",
  "memory_mb": 2800,
  "tokens": 512,
  "languages": "ara+eng"
}
```

Use `.exe` runner paths on Windows. Relative paths resolve against the manifest. The language setting is a declaration to validate against real images, not an automatic quality guarantee. Import validates files and adapter identity before inference. Bundled packs retain their runtime identity when saving options across onefile extraction directories; choose a new external pack to change bundled assets or runtime format. Adapter identity is retained in result JSON, embedded model provenance and diagnostics.

## Compile the reference JSON worker

The repository includes a small reference worker that bridges JSON v1 to a selected llama.cpp runtime. It has no numerical Python or Qt dependencies. This demonstrates swapping runtime interfaces with the same real model; it does not introduce another model or claim an accuracy improvement.

```sh
uv run python -m scripts.build_vision_bridge --runner /path/to/llama-mtmd-cli
uv run python -m scripts.prepare_vision --preset smol --adapter json-cli-v1 \
  --runner runtime/vision-bridge/cpu/vision_bridge.dist/ocready-vision-bridge \
  --model-dir models/json-vision
uv run python -m ocready assets/sample-bilingual.png --edition everyday \
  --method vision --model-pack models/json-vision/smol/pack.json --backend cpu --json
```

The worker contains its own Python runtime and native descendant, so running it does not require Python on the user's machine. Compile a separate worker using a compatible CUDA CLI and choose a distinct `--output` folder, then supply its executable through `--cuda-runner` when preparing a pack. On Windows both worker and native runner have `.exe` extensions.

The builder retains source/native-runner digests, Python/native notices and a `vision-build.json` inventory. Embedding a worker with this manifest copies its declared nested runtime files and verifies their hashes, excluding unrelated siblings. The common distribution bundler also handles neural workers. Parent resource containment covers the reference worker and its native descendant; cancellation/fallback stays in shared orchestration. The reference worker accepts the processed PNG input generated by OCReady and applies explicit CPU/GPU offload flags.

Real Linux validation has exercised SmolVLM on CPU and Qwen on CUDA through this second adapter. Qwen retained the complete public Arabic/English sample. The compiled worker also ran directly from `/tmp` without `VIRTUAL_ENV` or `PYTHONPATH`, and a declared-file archive was extracted elsewhere and successfully used for real SmolVLM inference. [Functional probe outputs and worker source identities](benchmarks/linux-json-vision-samples.json). These establish the tested protocol/runtime/relocation behavior, not complete outer onefile resource certification or Windows JSON-worker validation. The default llama.cpp adapter has separate real CPU/CUDA/fallback evidence.

The second interface now also has complete Linux onefile evidence. Clean `af3baa9` embedded the compiled CPU JSON worker, its native descendant, compact SmolVLM Q4 weights and projector in a 295.4 MB Everyday vision-only executable. Real CLI/native GUI transcription and all four packaged resource workloads passed, including 679.1 MB maximum observed tree RSS in the cap-sized GUI case ([binary-identified report](benchmarks/linux-json-smol-q4-onefile.json)). Python, separate model files and the development environment were not required by this executable. Its pack is English only and supplies no source boxes. Windows JSON-worker packaging, neural combinations and a complete CUDA onefile remain independent measurements.

To build the combined composition after preparing the classical runtime and neural worker/pack:

```sh
uv run python -m scripts.build_variant --edition everyday --variant multimodal-json
uv run python -m scripts.smoke_binary dist/everyday-multimodal-json --all-methods --benchmark
```

The builder provisions locked native weights, compiles one standalone CPU JSON bridge and writes sibling manifests that reference the same assets. Display names, prompts, languages and input/output limits remain intact. Separate IDs distinguish runtime choices if both manifests are installed. Studio uses both compact SmolVLM and bilingual Qwen through this interface. The shared workflow independently builds/tests Linux and Windows; release verification rejects a JSON composition containing a different vision adapter, missing models or incomplete per-method evidence.
