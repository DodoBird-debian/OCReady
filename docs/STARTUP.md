# Startup work and cache research

The single executable contains its runtimes/models. The compiler unpacks the Python/Qt application and compressed runtime bundle, then OCReady validates and extracts that bundle into a private directory. Current application releases use temporary extraction. Repeated launches therefore repeat both stages.

Clean `31d32ae` Linux Studio CI measured a 54.1-second full Qwen sample process, of which 34.6 seconds were reported by recognition ([raw report](benchmarks/ci-linux-packaged-studio-multimodal-vision-qwen3-vl-2b-q4.json)). The difference includes launch, extraction, application setup and observer overhead; it is not an isolated extraction timer. A different local Q8/Qwen binary needed 100.5 seconds overall and 22.7 seconds recognition ([development report](benchmarks/development-linux-packaged-studio-multimodal-vision-qwen3-vl-2b-q4.json)). Machine, source and dirty-state differences remain explicit.

One-pass runtime extraction and supported lower-memory compression already shipped into the later build policy. Persistent caching is a subsequent experiment, not an enabled application feature.

## Supported compiler mechanism

[Nuitka documents](https://nuitka.net/user-documentation/use-cases.html) a static per-user `--onefile-tempdir-spec` and cached mode. In pinned 4.3.5 the [native bootstrap](https://github.com/Nuitka/Nuitka/blob/4.3.5/nuitka/build/static_src/OnefileBootstrap.c) checks cached files using their payload checksums. Archive mode can skip decompression of already matching files. The cached files must still be read for checksumming; a cache hit does not mean zero work.

The same source does not serialize multiple simultaneous first extractions. OCReady's second extraction currently uses a per-process thread lock and private staging, appropriate to its current per-launch directory. A shared persistent directory would need process coordination, atomic publication and recovery. Simply changing the compiler flag is insufficient for production use.

## Reproducible isolated probe

```sh
uv run python -m scripts.startup_probe --size-mib 128 --rounds 3 \
  --output test-output/startup-probe.json
```

The script compiles two minimal native onefiles containing the same incompressible synthetic asset: temporary streaming extraction and supported cached archive extraction. It measures wall time and checks the entire asset SHA256 after each run. It tests cold/warm launches, repairs one deliberately changed cached byte, and runs simultaneous cold-launch pairs. Files are confined to its own disposable temporary directory; source images and user settings are never inputs.

The report identifies source/compiler, payload, native binaries and trim overlay. A synthetic result does not establish full OCReady startup time, whole-application RAM, model correctness, cross-platform cache safety or resistance to deliberately malicious filesystem changes. The measurement includes the child's asset hash verification. A failed concurrency experiment is retained as evidence rather than treated as a reason to enable caching.

The first clean `5911af8` Linux probe used a 128 MiB payload. Three temporary launches took 0.282–0.289 seconds; a newly empty cached directory took 0.285 seconds, and three warm cached launches took 0.167–0.169 seconds. Changed-byte repair returned the correct payload in 2.68 seconds. All six launches in three simultaneous cold pairs returned the expected SHA256, taking 2.94–4.78 seconds each. [Unchanged raw result](benchmarks/linux-onefile-startup-cache-probe.json). Here “cold” means a fresh extraction directory; OS file caches were not flushed. These small synthetic timings are not estimates for the large Studio application. Successful race samples do not supply the missing process coordination or Windows locking evidence.

## Conditions for an application implementation

- Use a private, per-user cache namespace with an identity covering source, dependencies, platform, runtime bundle and compiled packaging policy.
- Coordinate first extraction across processes before shared executable/DLL creation and before the second runtime archive extraction.
- Publish only complete stages, verify expected files and remove interrupted partial stages safely.
- Repair damaged assets without replacing executable files used by an active Windows process.
- Keep document images, OCR text, clipboard contents and user prompts outside the cache.
- Bound retained cache generations/disk use and provide a clear-cache action with an understandable busy state.
- Preserve cancellation, cleanup, model option rebinding and portable cold-launch behavior.
- Measure real cold/warm/repaired/concurrent starts on Linux and Windows and rerun every packaged RAM workload before release.
