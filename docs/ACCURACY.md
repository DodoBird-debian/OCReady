# Arabic and English accuracy evaluation

The committed corpus contains eleven original synthetic screenshots with ground-truth Unicode text and image SHA256 values. It includes English, Arabic, mixed scripts/digits, Naskh/Kufi/UI fonts, diacritics, small Arabic, dark/low-contrast backgrounds, and a corrected quarter-turn rotation. The raster files are committed so Linux and Windows evaluate identical pixels without requiring the rendering fonts at runtime.

Evaluate Fast and Precision sequentially:

```sh
uv run python -m scripts.accuracy evaluate
uv run python -m scripts.accuracy evaluate --layout auto --compare \
  --output test-output/accuracy-layouts.json
```

Character error rate (CER) is character edit distance divided by reference character count. Word error rate (WER) uses whitespace-separated words. Normalization performs Unicode NFC and collapses whitespace; it retains diacritics, Arabic/Western digit differences, punctuation, and directional controls. Rates can exceed 100% when output contains many extra characters. Weighted summaries use reference counts and show completed/skipped/error counts. Unsupported vision-pack languages are skipped explicitly and are not scored as correct output.

Reports include expected/actual text because every fixture is original public test material. They include source state and the corpus digest. This differs from resource benchmarks, which remove recognized document contents. Custom corpora should contain material suitable for the chosen report location.

The first exploratory runs found exact recognition for several clean English/Arabic font cases, but substantial errors on diacritics, small Arabic, and mixed digits. Precision recovered bilingual lines that Fast omitted. Layout comparison improved the small-text case but could also choose an incomplete result with higher OCR confidence. Confidence is therefore a diagnostic, not measured transcription accuracy. These findings motivate visible alternatives and further detection/layout work.

This small synthetic corpus does not establish real-world accuracy. It lacks camera perspective, handwriting, complex tables and many font/print conditions. Adding representative, redistribution-safe examples and auditing reading order remain ongoing work. Do not describe `1 - CER` as a universal product accuracy percentage.

Regeneration requires Qt and the named DejaVu/Noto Arabic font families:

```sh
uv run python -m scripts.accuracy generate
```

Inspect the rendered images after regeneration and review ground truth/image digests together. Never change expected text to match a wrong recognition result.
