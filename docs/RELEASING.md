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
