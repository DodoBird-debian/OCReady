"""Offline PP-OCRv5 worker entrypoint, compiled separately from the Qt app.

The protocol returns detected line polygons. It never invents word positions.
Heavy numerical libraries are imported only inside this worker process.
"""
import argparse
import gc
import json
import sys
import unicodedata
from pathlib import Path

from ocready.core.backend_errors import is_cuda_backend_error


def logical_text(text: str, *, decode: str = "visual", direction: str = "auto") -> str:
    if decode == "logical":
        return text.strip()
    from bidi.algorithm import get_display
    # CTC scans physical positions left-to-right. An Arabic-leading paragraph
    # can consequently begin with an English run in the raw sequence. Do not
    # infer its base direction from that raw first character.
    rtl = direction == "rtl" or (direction == "auto" and any(unicodedata.bidirectional(c) in {"AL", "R"} for c in text))
    return get_display(text, base_dir="R" if rtl else "L").strip()


def make_engine(args, cuda: bool):
    from rapidocr import ModelType, OCRVersion, RapidOCR
    from rapidocr.utils.download_file import DownloadFile

    def refuse_download(*_args, **_kwargs):
        raise RuntimeError("Neural OCR is offline. Supply all local model and dictionary files.")

    DownloadFile.run = staticmethod(refuse_download)
    return RapidOCR(params={
        "Global.use_cls": False, "Global.log_level": "error", "Global.max_side_len": 1600,
        "Global.return_word_box": False, "Global.return_single_char_box": False,
        "Det.model_path": str(args.detector.resolve()), "Det.ocr_version": OCRVersion.PPOCRV5,
        "Det.model_type": ModelType.MOBILE, "Det.limit_type": "max", "Det.limit_side_len": 960,
        "Det.mean": [0.485, 0.456, 0.406], "Det.std": [0.229, 0.224, 0.225],
        "Rec.model_path": str(args.recognizer.resolve()), "Rec.rec_keys_path": str(args.dictionary.resolve()),
        # A custom route suppresses RapidOCR's display-oriented bidi pass.
        # Explicit local files still select the actual Arabic model/dictionary.
        "Rec.lang_type": "ocready_raw", "Rec.ocr_version": OCRVersion.PPOCRV5,
        "Rec.model_type": ModelType.MOBILE, "Rec.rec_batch_num": 1,
        "EngineConfig.onnxruntime.intra_op_num_threads": 1,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        "EngineConfig.onnxruntime.enable_cpu_mem_arena": False,
        "EngineConfig.onnxruntime.use_cuda": cuda,
        "EngineConfig.onnxruntime.cuda_ep_cfg.cudnn_conv_algo_search": "HEURISTIC",
    })


def infer(args) -> dict:
    import cv2
    import numpy as np
    import onnxruntime as ort
    ort.disable_telemetry_events()
    cv2.setNumThreads(1)
    image = cv2.imdecode(np.frombuffer(args.image.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The prepared image could not be decoded.")
    height, width = image.shape[:2]
    if width * height > 4_000_000 or max(width, height) > 3000:
        raise ValueError("The prepared neural OCR image exceeds its supported input bounds.")
    want_cuda = args.backend != "cpu" and "CUDAExecutionProvider" in ort.get_available_providers()
    note = ""
    engine = make_engine(args, want_cuda)
    retry = False
    try:
        result = engine(image)
    except Exception as exc:
        if not want_cuda or not is_cuda_backend_error(exc):
            raise
        retry = True
        engine = None
    if retry:
        gc.collect()
        engine = make_engine(args, False)
        result = engine(image)
        note = "CUDA initialization failed; used CPU."
    providers = []
    for component in (engine.text_det, engine.text_rec):
        if component is not None:
            providers.extend(component.session.session.get_providers())
    backend = "CUDA" if "CUDAExecutionProvider" in providers else "CPU"
    if backend == "CPU" and args.backend == "cuda" and not note:
        note = "CUDA is unavailable in this runner/device; used CPU."
    if engine.text_rec is not None:
        classes = engine.text_rec.session.session.get_outputs()[0].shape[-1]
        if isinstance(classes, int) and classes != len(engine.text_rec.postprocess_op.character):
            raise ValueError("The character dictionary does not match the recognition model.")
    lines = []
    if result.txts is not None:
        for text, polygon, score in zip(result.txts, result.boxes, result.scores, strict=True):
            text = logical_text(text, decode=args.decode, direction=args.direction)
            if text:
                lines.append({"text": text, "polygon": polygon.tolist(), "score": float(score)})
    return {"schema": 1, "width": width, "height": height, "backend": backend, "note": note, "lines": lines}


def main() -> int:
    parser = argparse.ArgumentParser(description="OCReady local neural OCR worker")
    for name in ("image", "detector", "recognizer", "dictionary"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--backend", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--direction", choices=("auto", "rtl", "ltr"), default="auto")
    parser.add_argument("--decode", choices=("visual", "logical"), default="visual")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        for name in ("image", "detector", "recognizer", "dictionary"):
            if not getattr(args, name).is_file():
                raise ValueError(f"The local {name} file does not exist.")
        print(json.dumps(infer(args), ensure_ascii=True))
        return 0
    except Exception as exc:
        print(f"Neural OCR failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
