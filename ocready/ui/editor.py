import unicodedata

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QApplication, QTextEdit

from ocready.core.text import codepoint_offset, utf16_offset
from ocready.core.types import OCRResult


class TextEditor(QTextEdit):
    sourceSelection = Signal(object)
    linkChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Your text will appear here.\n\nOpen an image, paste a screenshot, or capture a region.\nThen choose Recognize text.\n\nالعربية والإنجليزية، جاهزتان للنسخ.")
        self.setAccessibleName("Recognized text. Editable, with native Arabic and English support.")
        font = QApplication.font()
        font.setPointSize(13)
        self.setFont(font)
        self.setAcceptRichText(False)
        self.setAutoFormatting(QTextEdit.AutoFormattingFlag.AutoNone)
        self.setTabStopDistance(32)
        self.result: OCRResult | None = None
        self.linked = False
        self._setting = False
        self.direction = "auto"
        self.textChanged.connect(self._on_edit)
        self.selectionChanged.connect(self._on_selection)
        self.set_direction("auto")

    def set_result(self, result: OCRResult) -> None:
        self._setting = True
        self.setExtraSelections([])
        self.result = result
        self.setPlainText(result.text)
        self.set_direction(self.direction)
        self.document().setModified(False)
        self.linked = bool(result.words)
        self._setting = False
        self.linkChanged.emit(self.linked)

    def clear_document(self) -> None:
        self._setting = True
        self.clear()
        self.result = None
        self.linked = False
        self._setting = False
        self.linkChanged.emit(False)

    def invalidate_link(self) -> None:
        self.linked = False
        self.setExtraSelections([])
        self.linkChanged.emit(False)

    def _on_edit(self) -> None:
        if self._setting:
            return
        if self.linked and self.result and self.toPlainText() != self.result.text:
            self.invalidate_link()
        if self.direction == "auto":
            self.set_direction("auto", join_edit=True)

    def _on_selection(self) -> None:
        if not self.linked or not self.result:
            return
        cursor = self.textCursor()
        start = codepoint_offset(self.result.text, cursor.selectionStart())
        end = codepoint_offset(self.result.text, cursor.selectionEnd())
        indices = {i for i, word in enumerate(self.result.words)
                   if (word.start < end and start < word.end) or (start == end and word.start <= start < word.end)}
        self.sourceSelection.emit(indices)

    def highlight_words(self, indices: set[int]) -> None:
        if not self.linked or not self.result:
            return
        selections = []
        for i in sorted(indices):
            word = self.result.words[i]
            cursor = QTextCursor(self.document())
            cursor.setPosition(utf16_offset(self.result.text, word.start))
            cursor.setPosition(utf16_offset(self.result.text, word.end), QTextCursor.MoveMode.KeepAnchor)
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = QTextCharFormat()
            selection.format.setBackground(QColor("#d5e5ff"))
            selection.format.setForeground(QColor("#183d76"))
            selections.append(selection)
        self.setExtraSelections(selections)
        if selections:
            scrollbar = self.verticalScrollBar()
            position = self.cursorRect(selections[0].cursor)
            if not self.viewport().rect().contains(position):
                scrollbar.setValue(scrollbar.value() + position.y() - self.viewport().height() // 2)

    def set_direction(self, value: str, *, join_edit: bool = False) -> None:
        self.direction = value
        direction = {"auto": Qt.LayoutDirection.LayoutDirectionAuto,
                     "rtl": Qt.LayoutDirection.RightToLeft, "ltr": Qt.LayoutDirection.LeftToRight}[value]
        setting, modified = self._setting, self.document().isModified()
        self._setting = True
        option = self.document().defaultTextOption()
        option.setTextDirection(direction)
        self.document().setDefaultTextOption(option)
        cursor = QTextCursor(self.document())
        if join_edit:
            cursor.joinPreviousEditBlock()
        else:
            cursor.beginEditBlock()
        block = self.document().firstBlock()
        while block.isValid():
            strong = next((unicodedata.bidirectional(character) for character in block.text()
                           if unicodedata.bidirectional(character) in {"L", "R", "AL"}), "L")
            rtl = value == "rtl" or (value == "auto" and strong in {"R", "AL"})
            cursor.setPosition(block.position())
            formatting = cursor.blockFormat()
            wanted_direction = Qt.LayoutDirection.RightToLeft if rtl else Qt.LayoutDirection.LeftToRight
            wanted_alignment = ((Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft)
                                | Qt.AlignmentFlag.AlignAbsolute)
            if formatting.layoutDirection() != wanted_direction or formatting.alignment() != wanted_alignment:
                formatting.setLayoutDirection(wanted_direction)
                formatting.setAlignment(wanted_alignment)
                cursor.setBlockFormat(formatting)
            block = block.next()
        cursor.endEditBlock()
        self.document().setModified(modified)
        self._setting = setting
        self.viewport().update()

