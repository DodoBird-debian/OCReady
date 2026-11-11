# Verified prereleases

Tag builds compile all three default editions on Linux and Windows. A release job runs only after all six builds and packaged checks succeed. It verifies each executable's checksum, exact clean source revision, matching benchmark binary/profile, all four required workloads, and each numeric RAM peak against its edition's budget before publishing an experimental prerelease.

The release directory contains six single executables, individual SHA256 files, corresponding build manifests and benchmark reports, a release evidence index, release notes, and aggregate checksums. Default executables contain Arabic/English classical OCR. Local vision packs can be configured separately in Everyday/Studio; custom embedded-model builds use the developer build options.

To prepare the same files manually from an already successful Actions run:

```sh
gh run download RUN_ID --dir test-output/release-input
python -m scripts.release_assets \
  --artifacts test-output/release-input \
  --output dist/release \
  --revision FULL_40_CHARACTER_COMMIT \
  --run-id RUN_ID
```

Use an empty output directory. The command fails before copying files if any platform/edition, clean-source record, checksum, required scenario, or budget result is missing or inconsistent. It also rejects evidence from a changed source tree or an executable replaced during measurement. It does not replace an existing release or its assets.

The reported RAM values are observed workload peaks, including the launcher and OCR descendants. Worker allocation limits strengthen safety, but complete application hard-RSS certification and actual interactive capture/GPU testing remain distinct validation work. Prerelease notes retain those limits.

## Releases with embedded model choices

The neural-edition workflow can compile `neural`, `combined` or `multimodal` variants and publish only after both native platform jobs pass. Its verifier checks four packaged resource scenarios for every embedded choice, actual engine identity and complete bilingual neural corpus evaluation. Studio multimodal needs at least two vision choices; a failed model or platform prevents a paired release.

```sh
python -m scripts.release_variants --artifacts artifacts --output dist/release \
  --revision FULL_40_CHARACTER_COMMIT --edition everyday --variant multimodal --run-id RUN_ID
```

Run preparation from the source checkout whose committed corpus was evaluated. Matching pack IDs alone are insufficient: both platforms must also match model/projector or detector/recognizer/dictionary SHA256 values, language capabilities, neural geometry and registered vision adapter. Legacy vision manifests default to llama.cpp. Platform-specific executable/library hashes are intentionally independent.

Accuracy reports retain the raw corpus-manifest checksum and a canonical JSON content digest that includes image hashes, expected text and cleanup recipes. The release checks the corpus content and every expected case against this checkout. Older reports may use either exact LF or CRLF manifest checksum for that same committed corpus; an arbitrary legacy checksum is rejected. Changed diacritics, digits, images or recipes are content changes. The release evidence index records shared model/corpus identities alongside individual platform measurements.

New Windows builds also retain `pe-layout.json`: x64 machine, mapped image size, section bounds and numeric root resource types, following the [Microsoft PE format](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format). The builder requires icon and group-icon resources after attaching the owned application ICO. The vector source is `assets/ocready.svg`; `uv run python -m scripts.make_icon` regenerates the matching PNG and nine-resolution ICO. Runtime window branding uses the same mark without depending on an installed letterform font. Both build workflows retain small layout/compiler diagnostics after failures.

Diagnostic timeouts derive from the same unchanged attempt limits used by the engines: 120 seconds for classical/neural workers, 300 seconds for a vision attempt and 20 seconds for its capability probe. Envelopes include a possible backend-to-CPU retry, sequential GUI iterations, a 30-second GUI allowance and a 120-second outer startup allowance. The limits bound test execution; they are not performance targets. A deadline failure retains its partial measurements and fails publication. The harness must never silently replace a failed result with a later successful run.

## Isolated desktop validation

New build manifests declare a validation requirement for isolated runtimes, native GUI backends and Unicode paths. Packaged checks remove inherited Python, OCR and Qt/loader overrides, use only OS directories on PATH and keep a private application configuration. Original benchmark images and runtime temporary directories include Arabic names. Deliberately configured external runtimes remain an app feature; the diagnostic isolation ensures those choices cannot accidentally mask missing bundled files.

Linux workflow GUI checks use X11 through `xvfb-run`; Windows uses the native Win32 Qt platform. The GUI reports its actual platform name, and publication rejects a missing or mismatched result for the new validation policy. Older releases keep their original evidence scope. A local Linux developer can request the same path with:

```sh
OCREADY_GUI_TEST_PLATFORM=xcb xvfb-run -a --server-args="-screen 0 1600x1200x24" \
  uv run python -m scripts.smoke_binary dist/pocket --benchmark
```

Each basic GUI smoke read also exercises Copy all through Qt's clipboard API. For classical/neural output it clicks a genuine detected Arabic region inside the application's own widget, checks linked highlighting and copies that selection. This is an in-application clipboard readback while the window is alive; it does not certify cross-application pasting or screenshot-tool integration. Resource GUI cases retain platform/copy diagnostics without publishing their stress-image transcription.

The workflow retains `gui-*.png` and `gui-*.json` records of the fixed public sample, including failed GUI records/screenshots when generated. These are review artifacts, not captures of the user's desktop. Source unit tests can still use the offscreen Qt backend, but new release evidence must identify X11/Wayland or Win32.

## Linux desktop dependencies

The onefile embeds the application, Qt plugins and selected OCR/model runtimes. Linux's loader, display server, graphics drivers, font and X11/Wayland client libraries remain desktop dependencies. On Ubuntu/Debian, the X11 build/test environment includes `libegl1 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxkbcommon-x11-0`; package dependencies provide additional XCB libraries. KDE desktops normally supply many of these already. This does not require an installed Python or Tesseract for a packaged application.

The [Qt platform dependency reference](https://doc.qt.io/qt-6/linux-requirements.html) lists ICCCM and key-symbol libraries separately from cursor support. A generic Qt cursor warning alone does not identify the unresolved library. The builder now checks `ldd` against both the build wheel's X11 plugin and the generated standalone plugin, rejects any unresolved dependency, and retains `qt-source-runtime.json` / `qt-packaged-runtime.json`. This loader check requires no display and complements the subsequent genuine X11/clipboard test; it cannot replace it.

The initial isolated-platform candidate `85835ee` failed and was not published: Linux could not load XCB, while a Windows source test read a UTF-8 report using the default legacy encoding. The Linux compiler inventory did not resolve ICCCM/key-symbol dependencies. Corrective builds install those libraries explicitly and read reports as UTF-8. The failed `v0.1.0-preview.3` tag remains unchanged; subsequent releases require new successful evidence.

Packaged CLI/GUI smoke commands now redirect and retain the final 64 KiB of their stdout/stderr as `cli-*.log` / `gui-*.log`, including failures and timeouts. Explicit handles preserve attach-mode Windows diagnostic output when CI has no usable console. Stored/printed tails remain bounded; the test inputs are the public sample.

The separate `path-diagnostics.yml` workflow compares source classical OCR with ASCII paths, an Arabic temporary directory, an Arabic copied runtime, and both. It retains the native ANSI code page, each exit code and bounded output/error text without compiling another app. This probe investigates a Windows classical failure exposed by the isolated onefile checks; it does not bypass those checks. Upstream [Tesseract Unicode-path tracking](https://github.com/tesseract-ocr/tesseract/issues/3709) identifies a relevant limitation, but does not by itself establish the cause of a particular OCReady failure.

The [actual four-case Windows report](benchmarks/windows-paths-before-utf8.json) subsequently reproduced image/language-data failures specifically under Arabic worker paths at ANSI code page 1252. Windows runtime preparation now updates only its private copied Tesseract executable's manifest to request the [per-process UTF-8 code page](https://learn.microsoft.com/en-us/windows/apps/design/globalizing/use-utf8-code-page), retaining existing manifest settings and other PE resources through the native resource APIs. It leaves the installed executable and system locale untouched. Resulting XML, a modification notice and the modified binary hash enter the runtime inventory. Native source/onefile probes must validate the resulting worker; XML tests alone do not prove path compatibility.

Workflow `43049176735` at clean `e949d48` then passed all four real source-worker cases after manifest preparation ([passing report](benchmarks/windows-paths-after-utf8.json)). The parent/system ANSI code page remained 1252 and every case verified actual Arabic/English output. This confirms the source native worker correction; complete onefile, native GUI and RAM gates still require fresh builds.

Hosted Ubuntu dependencies use task-private indexes and the original Ubuntu signing key. A bounded reachability check selects the official archives or a fixed [Princeton mirror transport used in Canonical's Landscape documentation](https://ubuntu.com/landscape/docs/how-to-guides/repository-mirrors/manage-repositories-with-the-api/); apt must verify the same signed suite metadata/package hashes. Neither transport availability nor a failed package setup counts as an application test result.
