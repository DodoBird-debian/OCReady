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
| RapidOCR (optional worker) | Neural text detection/recognition pipeline | Apache-2.0, https://github.com/RapidAI/RapidOCR |
| PP-OCRv5 models (optional) | Mobile detection and Arabic/English recognition | Apache-2.0, https://huggingface.co/PaddlePaddle |
| ONNX Runtime (optional worker) | Numerical inference | MIT, https://github.com/microsoft/onnxruntime |
| OpenCV (optional worker) | Image geometry and neural preprocessing | Apache-2.0 and bundled notices, https://github.com/opencv/opencv-python |
| NumPy / Shapely / pyclipper (optional worker) | Arrays and detected-region geometry | Retained distribution/vendor licenses in worker notices |
| python-bidi (optional worker) | Visual CTC to logical Unicode order | Retained distribution license, https://github.com/MeirKriheli/python-bidi |
| CPython | Embedded application/worker runtime | PSF and bundled notices, https://www.python.org/ |

Model weights have independent licenses and are never assumed to inherit the runner license. User-supplied model packs must retain their model cards and redistribution notices. Runtime preparation preserves package copyright files; distribution must include them in the onefile payload.

Qt is dynamically linked inside the extracted onefile payload. Users can obtain and rebuild all application source from this repository. No Qt code is modified. Linux packages also depend on system C library and display drivers; onefile does not imply a kernel-independent static binary.
