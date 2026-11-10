# Third-party components

OCReady is GPL-3.0-or-later. Source and build instructions are public to permit modification and rebuilding.

| Component | Role | License / upstream |
| --- | --- | --- |
| PySide6 / Qt 6 | Native desktop UI and Arabic text shaping | LGPL-3.0 / GPL-3.0, https://code.qt.io/pyside/pyside-setup.git |
| Tesseract | Offline OCR | Apache-2.0, https://github.com/tesseract-ocr/tesseract |
| tessdata_fast / tessdata_best | Arabic and English language data | Apache-2.0, https://github.com/tesseract-ocr/tessdata_fast |
| Leptonica | Image decoding for Tesseract | BSD-2-Clause, http://www.leptonica.org/about-the-license.html |
| Pillow | Bounded image transforms | HPND, https://github.com/python-pillow/Pillow |
| psutil | Process-tree memory monitoring | BSD-3-Clause, https://github.com/giampaolo/psutil |
| Nuitka | C compilation and onefile packaging | Apache-2.0, https://github.com/Nuitka/Nuitka |
| llama.cpp (optional) | Local CPU / CUDA vision-language inference | MIT, https://github.com/ggml-org/llama.cpp |

Model weights have independent licenses and are never assumed to inherit the runner license. User-supplied model packs must retain their model cards and redistribution notices. Runtime preparation preserves package copyright files; distribution must include them in the onefile payload.

Qt is dynamically linked inside the extracted onefile payload. Users can obtain and rebuild all application source from this repository. No Qt code is modified. Linux packages also depend on system C library and display drivers; onefile does not imply a kernel-independent static binary.
