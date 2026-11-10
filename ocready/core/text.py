import csv
import io
import re

from ocready.core.types import Box, OCRResult, Word


def parse_tsv(tsv: str, *, engine: str = "tesseract-fast", language: str = "ara+eng") -> OCRResult:
    words: list[Word] = []
    chunks: list[str] = []
    previous_line: tuple[int, ...] | None = None
    previous_paragraph: tuple[int, ...] | None = None
    offset = 0
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        text = (row.get("text") or "").strip()
        if not text or row.get("level") != "5":
            continue
        try:
            line = tuple(int(row[k]) for k in ("page_num", "block_num", "par_num", "line_num"))
            box = Box(*(int(row[k]) for k in ("left", "top", "width", "height")))
            confidence = float(row["conf"])
        except (KeyError, ValueError, TypeError):
            continue
        if not box.width or not box.height:
            continue
        paragraph = line[:3]
        separator = ""
        if words:
            separator = " " if line == previous_line else ("\n" if paragraph == previous_paragraph else "\n\n")
        chunks.extend((separator, text))
        offset += len(separator)
        words.append(Word(text, box, confidence if 0 <= confidence <= 100 else None,
                          offset, offset + len(text), line))
        offset += len(text)
        previous_line, previous_paragraph = line, paragraph
    return OCRResult("".join(chunks), words, engine, language)


def selected_text(words: list[Word], indices: set[int]) -> str:
    chunks: list[str] = []
    previous_line = None
    for i, word in enumerate(words):
        if i not in indices:
            continue
        if chunks:
            chunks.append(" " if word.line == previous_line else "\n")
        chunks.append(word.text)
        previous_line = word.line
    return "".join(chunks)


def unwrap_lines(text: str) -> str:
    return "\n\n".join(re.sub(r"\s*\n\s*", " ", p) for p in text.split("\n\n"))


def utf16_offset(text: str, codepoint_offset: int) -> int:
    """QTextCursor measures UTF-16 units; Python indexes Unicode code points."""
    return len(text[:codepoint_offset].encode("utf-16-le")) // 2


def codepoint_offset(text: str, utf16: int) -> int:
    raw = text.encode("utf-16-le")[:utf16 * 2]
    return len(raw.decode("utf-16-le", errors="ignore"))
