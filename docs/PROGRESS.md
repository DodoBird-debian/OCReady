# Implementation record

## Iteration 0 — architecture and delivery contract

- Created the empty repository and a modular plan with more than 1,000 lines.
- Chose native Qt for Arabic shaping, bidirectional editing, accessibility, and clipboard images.
- Chose Tesseract fast/best for offline OCR, plus an isolated llama.cpp adapter for optional vision-language inference.
- Defined decimal memory budgets over the application and its child processes.
- Chose Nuitka onefile distribution for Linux and Windows, with explicitly bundled runtime data.
- Established that model-size estimates do not certify runtime memory or Arabic accuracy.

The plan describes both the implementation sequence and release gates. Pending items are not claims of completed functionality.
