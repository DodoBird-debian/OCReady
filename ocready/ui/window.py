import dataclasses
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice, QSize, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ocready.core.editions import EDITIONS, edition_for
from ocready.core.geometry import words_on_source
from ocready.core.images import load_image
from ocready.core.memory import tree_rss
from ocready.core.models import load_packs
from ocready.core.paths import build_profile, resource_root
from ocready.core.pipeline import Request, image_policy
from ocready.core.preprocess import Recipe, preprocess
from ocready.core.settings import load_settings, save_settings
from ocready.core.text import selected_text, unwrap_lines
from ocready.core.types import Box, OCRResult
from ocready.core.worker import RecognitionWorker
from ocready.engines.tesseract import LANGUAGES, LAYOUTS
from ocready.ui.canvas import ImageCanvas
from ocready.ui.editor import TextEditor
from ocready.ui.theme import app_icon


def label(text: str, style: str = "Subtle") -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(style)
    return widget


def button(text: str, slot, *, primary=False, quiet=False, tooltip="") -> QPushButton:
    widget = QPushButton(text)
    widget.clicked.connect(slot)
    if primary:
        widget.setObjectName("Primary")
    elif quiet:
        widget.setObjectName("Quiet")
    if tooltip:
        widget.setToolTip(tooltip)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def divider() -> QFrame:
    widget = QFrame()
    widget.setObjectName("Divider")
    widget.setFixedHeight(1)
    return widget


class MainWindow(QMainWindow):
    def __init__(self, *, edition: str = "pocket"):
        super().__init__()
        self.setWindowTitle("OCReady — Arabic + English OCR")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(960, 700)
        self.resize(1320, 900)
        self.setAcceptDrops(True)
        self.preferences = load_settings()
        self.profile = build_profile()
        self.packs = load_packs()
        self.vision_backend = self.preferences.get("vision_backend", "auto")
        self.source: Image.Image | None = None
        self.preview: Image.Image | None = None
        self._preview_limits: tuple[int, int] | None = None
        self.recipe = Recipe()
        self.result: OCRResult | None = None
        self.alternatives: list[OCRResult] = []
        self.worker: RecognitionWorker | None = None
        self.job = 0
        self._closing = False
        self._loading_controls = False
        self._source_name = "No image yet"
        self._build_ui(edition)
        self._shortcuts()
        self.memory_timer = QTimer(self)
        self.memory_timer.timeout.connect(self._update_memory)
        self.memory_timer.start(2000)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._apply_recipe)
        self._update_memory()
        self._set_busy(False)

    @property
    def edition(self):
        return edition_for(self.edition_combo.currentData())

    def _build_ui(self, edition: str) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(26, 21, 26, 14)
        layout.setSpacing(14)

        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(QSize(35, 35)))
        brand.addWidget(logo)
        brand.addWidget(label("OCReady", "Brand"))
        brand.addSpacing(10)
        brand.addWidget(label("YOUR WORDS, FREED.", "Eyebrow"))
        brand.addStretch()
        brand.addWidget(label("Edition"))
        self.edition_combo = QComboBox()
        self.edition_combo.setAccessibleName("Memory edition")
        for key, value in EDITIONS.items():
            if key in self.profile["available_editions"]:
                self.edition_combo.addItem(f"{value.name} · {value.budget_label}", key)
        self.edition_combo.setCurrentIndex(self.edition_combo.findData(edition))
        self.edition_combo.setToolTip("RAM budget for the application and its OCR children. Sampled guardrail, not a hard OS limit.")
        self.edition_combo.currentIndexChanged.connect(self._edition_changed)
        brand.addWidget(self.edition_combo)
        brand.addSpacing(8)
        brand.addWidget(button("Help", self.show_help, quiet=True))
        self.settings_button = button("Settings", self.show_settings, quiet=True)
        brand.addWidget(self.settings_button)
        layout.addLayout(brand)

        title = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(5)
        titles.addWidget(label("Your screenshots. Ready to copy.", "Hero"))
        titles.addWidget(label("Capture a moment, keep the words. Arabic and English, entirely on your device."))
        title.addLayout(titles)
        title.addStretch()
        title.addWidget(label("LOCAL & PRIVATE", "Badge"))
        layout.addLayout(title)

        actions_card = QFrame()
        actions_card.setObjectName("Card")
        actions = QVBoxLayout(actions_card)
        actions.setContentsMargins(14, 14, 14, 12)
        actions.setSpacing(12)
        primary = QHBoxLayout()
        primary.setSpacing(9)
        self.open_button = button("Open image", self.open_dialog, tooltip="Open a local image · Ctrl+O")
        self.paste_button = button("Paste image", self.paste_image, tooltip="Paste an image from your clipboard · Ctrl+Shift+V")
        self.capture_button = button("Capture region", self.capture_region, tooltip="Use your desktop's screenshot tool · Ctrl+Shift+S")
        primary.addWidget(self.open_button)
        primary.addWidget(self.paste_button)
        primary.addWidget(self.capture_button)
        primary.addStretch()
        self.recognize_button = button("Recognize text", self.recognize, primary=True, tooltip="Read the current image · Ctrl+Return")
        self.cancel_button = button("Cancel", self.cancel_recognition)
        self.cancel_button.setObjectName("Danger")
        primary.addWidget(self.cancel_button)
        primary.addWidget(self.recognize_button)
        actions.addLayout(primary)
        actions.addWidget(divider())
        options = QHBoxLayout()
        options.setSpacing(9)
        options.addWidget(label("Read"))
        self.language_combo = QComboBox()
        self.language_combo.setAccessibleName("Recognition language")
        for key, name in LANGUAGES.items():
            self.language_combo.addItem(name, key)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self.preferences.get("language", "ara+eng"))))
        options.addWidget(self.language_combo)
        options.addSpacing(5)
        options.addWidget(label("with"))
        self.method_combo = QComboBox()
        self.method_combo.setAccessibleName("OCR method")
        self.method_combo.addItem("Fast OCR", "tesseract-fast")
        self.method_combo.addItem("Precision OCR", "tesseract-best")
        self.method_combo.setToolTip("Fast: compact offline models. Precision: larger language data in Everyday or Studio.")
        self.method_combo.currentIndexChanged.connect(self._method_changed)
        options.addWidget(self.method_combo)
        self.layout_combo = QComboBox()
        self.layout_combo.setAccessibleName("Page layout")
        for key, (_, name) in LAYOUTS.items():
            self.layout_combo.addItem(name, key)
        self.layout_combo.setCurrentIndex(2)
        options.addWidget(self.layout_combo)
        options.addStretch()
        self.compare_check = QCheckBox("Compare layouts")
        self.compare_check.setToolTip("Try two layouts one after another and choose the stronger OCR confidence. Uses more time, not parallel models.")
        options.addWidget(self.compare_check)
        self.cleanup_button = button("Image cleanup", self._toggle_cleanup, quiet=True)
        self.cleanup_button.setCheckable(True)
        options.addWidget(self.cleanup_button)
        actions.addLayout(options)
        layout.addWidget(actions_card)

        self.cleanup = self._build_cleanup()
        self.cleanup.hide()
        layout.addWidget(self.cleanup)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(14)
        self.splitter.addWidget(self._build_image_pane())
        self.splitter.addWidget(self._build_text_pane())
        self.splitter.setSizes([620, 620])
        layout.addWidget(self.splitter, 1)

        footer = QHBoxLayout()
        self.status = label("Start with an image. The words are yours to keep.")
        self.status.setWordWrap(True)
        self.status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        footer.addWidget(self.status, 1)
        self.memory = label("")
        footer.addWidget(self.memory)
        layout.addLayout(footer)
        self._edition_changed()

    def _build_cleanup(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Card")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(14, 10, 14, 10)
        row = QHBoxLayout()
        row.addWidget(label("A clearer image, a better read.", "PaneTitle"))
        row.addStretch()
        row.addWidget(button("Reset all", self.reset_recipe, quiet=True))
        outer.addLayout(row)
        row = QHBoxLayout()
        self.invert = QCheckBox("Invert colors")
        self.gray = QCheckBox("Grayscale")
        self.auto_contrast = QCheckBox("Auto contrast")
        self.threshold = QCheckBox("Black & white")
        for control in (self.invert, self.gray, self.auto_contrast, self.threshold):
            control.toggled.connect(self._recipe_controls_changed)
            row.addWidget(control)
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(30, 230)
        self.threshold_slider.setValue(145)
        self.threshold_slider.setMaximumWidth(100)
        self.threshold_slider.setToolTip("Black-and-white threshold")
        self.threshold_slider.valueChanged.connect(self._recipe_controls_changed)
        row.addWidget(self.threshold_slider)
        row.addStretch()
        row.addWidget(button("Rotate", self.rotate_image, tooltip="Rotate 90° clockwise"))
        row.addWidget(button("Mirror", self.mirror_image, tooltip="Flip horizontally"))
        self.crop_button = button("Crop", self.toggle_crop, tooltip="Draw a crop on the image. Reset all restores the original.")
        self.crop_button.setCheckable(True)
        row.addWidget(self.crop_button)
        outer.addLayout(row)
        return frame

    def _build_image_pane(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Card")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        row = QHBoxLayout()
        row.setContentsMargins(16, 10, 12, 10)
        row.addWidget(label("Source image", "PaneTitle"))
        row.addStretch()
        self.view_original = button("Show original", self.toggle_original, quiet=True)
        self.view_original.setCheckable(True)
        self.view_original.setEnabled(False)
        row.addWidget(self.view_original)
        row.addWidget(button("−", lambda: self.canvas.zoom(1 / 1.2), quiet=True, tooltip="Zoom out"))
        self.zoom_label = label("Fit")
        row.addWidget(self.zoom_label)
        row.addWidget(button("+", lambda: self.canvas.zoom(1.2), quiet=True, tooltip="Zoom in"))
        row.addWidget(button("Fit", lambda: self.canvas.fit_image(), quiet=True))
        outer.addLayout(row)
        outer.addWidget(divider())
        self.image_stack = QStackedWidget()
        self.empty = QWidget()
        self.empty.setStyleSheet("background: #f8fafd;")
        empty_layout = QVBoxLayout(self.empty)
        empty_layout.addStretch()
        symbol = label("[  +  ]", "Hero")
        symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        symbol.setStyleSheet("color: #8ba6d0; font-size: 44px; font-weight: 400;")
        empty_layout.addWidget(symbol)
        heading = label("A picture is worth a thousand words.", "PaneTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(heading)
        hint = label("Drop an image here, or paste a screenshot.\nWe’ll help you get the words out.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        empty_layout.addWidget(hint)
        empty_layout.addSpacing(15)
        example = button("Try a bilingual example", self.load_example)
        example.setMaximumWidth(250)
        empty_layout.addWidget(example, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch()
        self.canvas = ImageCanvas()
        self.canvas.wordsSelected.connect(self._image_selected)
        self.canvas.cropSelected.connect(self._crop_selected)
        self.canvas.zoomChanged.connect(lambda percent: self.zoom_label.setText(f"{percent}%"))
        self.image_stack.addWidget(self.empty)
        self.image_stack.addWidget(self.canvas)
        outer.addWidget(self.image_stack, 1)
        outer.addWidget(divider())
        row = QHBoxLayout()
        row.setContentsMargins(14, 8, 12, 8)
        self.image_info = label("PNG, JPEG, WebP, BMP, TIFF")
        self.image_info.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.image_info, 1)
        self.boxes = QCheckBox("Word boxes")
        self.boxes.setEnabled(False)
        self.boxes.toggled.connect(self._boxes_toggled)
        row.addWidget(self.boxes)
        self.copy_selection = button("Copy selection", self.copy_image_selection, quiet=True)
        self.copy_selection.setEnabled(False)
        row.addWidget(self.copy_selection)
        outer.addLayout(row)
        return frame

    def _build_text_pane(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Card")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        row = QHBoxLayout()
        row.setContentsMargins(16, 10, 12, 10)
        row.addWidget(label("Recognized text", "PaneTitle"))
        row.addStretch()
        self.direction = QComboBox()
        self.direction.addItem("Auto direction", "auto")
        self.direction.addItem("Right to left", "rtl")
        self.direction.addItem("Left to right", "ltr")
        self.direction.setToolTip("Paragraph direction. Arabic shapes automatically.")
        self.direction.currentIndexChanged.connect(lambda: self.editor.set_direction(self.direction.currentData()))
        row.addWidget(self.direction)
        self.copy_all_button = button("Copy all", self.copy_all, tooltip="Copy the complete text · Ctrl+Shift+C")
        row.addWidget(self.copy_all_button)
        outer.addLayout(row)
        outer.addWidget(divider())
        self.editor = TextEditor()
        self.editor.sourceSelection.connect(self._editor_selected)
        self.editor.linkChanged.connect(self._link_changed)
        self.editor.textChanged.connect(self._update_text_stats)
        outer.addWidget(self.editor, 1)
        outer.addWidget(divider())
        row = QHBoxLayout()
        row.setContentsMargins(14, 8, 12, 8)
        self.text_stats = label("0 words · 0 characters")
        row.addWidget(self.text_stats)
        row.addStretch()
        self.link_status = label("")
        row.addWidget(self.link_status)
        self.join_lines_button = button("Join lines", self.join_lines, quiet=True, tooltip="Join wrapped lines while keeping paragraphs. Undo is available.")
        row.addWidget(self.join_lines_button)
        self.save_button = button("Save text", self.save_text, quiet=True)
        row.addWidget(self.save_button)
        outer.addLayout(row)
        return frame

    def _shortcuts(self) -> None:
        bindings = {"Ctrl+O": self.open_dialog, "Ctrl+Shift+V": self.paste_image,
                    "Ctrl+Shift+S": self.capture_region, "Ctrl+Return": self.recognize,
                    "Ctrl+Shift+C": self.copy_all, "Escape": self.escape,
                    "Ctrl+S": self.save_text, "F1": self.show_help}
        self.shortcuts = []
        for key, slot in bindings.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(slot)
            self.shortcuts.append(shortcut)
        source_copy = QShortcut(QKeySequence.StandardKey.Copy, self.canvas)
        source_copy.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        source_copy.activated.connect(self.copy_image_selection)
        self.shortcuts.append(source_copy)

    def _set_status(self, text: str, error=False) -> None:
        self.status.setText(text)
        self.status.setStyleSheet("color: #b34a40;" if error else "color: #728097;")

    def _set_busy(self, busy: bool) -> None:
        self.cancel_button.setVisible(busy)
        self.progress.setVisible(busy)
        for control in (self.open_button, self.paste_button, self.capture_button, self.edition_combo,
                        self.method_combo, self.language_combo, self.layout_combo, self.cleanup,
                        self.compare_check, self.settings_button, self.join_lines_button):
            control.setEnabled(not busy)
        self.view_original.setEnabled(not busy and self.source is not None and self.preview is not None and
                                      (self.recipe != Recipe() or self.preview.size != self.source.size))
        if busy:
            self.crop_button.setChecked(False)
            self.canvas.crop_mode = False
        self.recognize_button.setEnabled(self.source is not None and not busy)
        self.editor.setReadOnly(busy)
        if not busy:
            self._method_changed()
        self._update_text_stats()

    def _confirm_replace(self) -> bool:
        if not self.editor.document().isModified():
            return True
        choice = QMessageBox.question(self, "Keep your edits?", "This will replace your edited text. Copy or save it first if you want to keep it.",
                                      QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                      QMessageBox.StandardButton.Cancel)
        return choice == QMessageBox.StandardButton.Discard

    def open_dialog(self) -> None:
        if self.worker:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open an image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff);;All files (*)")
        if path:
            self.open_path(path)

    def open_path(self, path: str, *, replace_confirmed: bool = False) -> bool:
        if self.worker or (not replace_confirmed and not self._confirm_replace()):
            return False
        try:
            image = load_image(path, self.edition)
            self._set_source(image, Path(path).name)
            return True
        except Exception as exc:
            self._set_status(str(exc), error=True)
            return False

    def _set_source(self, image: Image.Image, name: str) -> None:
        self.job += 1
        self.source = image
        self.result, self.alternatives = None, []
        self._source_name = name
        self.editor.clear_document()
        self.reset_recipe()
        self.image_stack.setCurrentWidget(self.canvas)
        self._set_busy(False)
        self._set_status("Image ready. Choose Recognize text, or clean up the image first.")

    def paste_image(self, *, replace_confirmed: bool = False) -> bool:
        if self.worker:
            return False
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime and mime.hasUrls():
            path = next((u.toLocalFile() for u in mime.urls() if u.isLocalFile()), None)
            if path:
                return self.open_path(path, replace_confirmed=replace_confirmed)
        image = clipboard.image()
        if image.isNull():
            self._set_status("No image on your clipboard. Copy a screenshot or image, then choose Paste image.")
            return False
        if image.width() * image.height() > self.edition.max_pixels * 2:
            self._set_status(f"This clipboard image is too large for {self.edition.name}. Capture a smaller region or choose a larger edition.", error=True)
            return False
        if not replace_confirmed and not self._confirm_replace():
            return False
        try:
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            image.save(buffer, "PNG")
            source = load_image(bytes(buffer.data()), self.edition)
            self._set_source(source, "Clipboard image")
            return True
        except Exception as exc:
            self._set_status(str(exc), error=True)
            return False

    def load_example(self) -> None:
        self.open_path(str(resource_root() / "assets" / "sample-bilingual.png"))

    def _toggle_cleanup(self) -> None:
        self.cleanup.setVisible(self.cleanup_button.isChecked())

    def _recipe_controls_changed(self, *_args) -> None:
        if self._loading_controls:
            return
        self.recipe = dataclasses.replace(self.recipe, invert=self.invert.isChecked(), grayscale=self.gray.isChecked(),
                                          autocontrast=self.auto_contrast.isChecked(),
                                          threshold=self.threshold_slider.value() if self.threshold.isChecked() else None)
        self.preview_timer.start(140)

    def reset_recipe(self) -> None:
        self.recipe = Recipe()
        self._loading_controls = True
        for control in (self.invert, self.gray, self.auto_contrast, self.threshold):
            control.setChecked(False)
        self.crop_button.setChecked(False)
        self.canvas.crop_mode = False
        self._loading_controls = False
        self.view_original.setChecked(False)
        self._apply_recipe()

    def _apply_recipe(self) -> None:
        if self.source is None:
            return
        try:
            policy = self._image_policy()
            self.preview = preprocess(self.source, self.recipe, policy)
            self._preview_limits = (policy.max_pixels, policy.max_edge)
            self.view_original.setEnabled(self.recipe != Recipe() or self.preview.size != self.source.size)
            self.view_original.setChecked(False)
            self.view_original.setText("Show original")
            self.canvas.set_image(self.preview)
            self.image_info.setText(f"{self.preview.width} × {self.preview.height} · {self._source_name}")
            self.image_info.setToolTip(self.recipe.label + (" · AI preview is reduced to reserve model memory. Crop the original for small text." if str(self.method_combo.currentData()).startswith("vision:") else ""))
            if self.result:
                self.editor.invalidate_link()
                self.result = None
                self._set_status("Image changed. Recognize again to refresh the source-linked text.")
            self.copy_selection.setEnabled(False)
        except Exception as exc:
            self._set_status(str(exc), error=True)

    def rotate_image(self) -> None:
        self.recipe = dataclasses.replace(self.recipe, rotation=(self.recipe.rotation + 90) % 360)
        self._apply_recipe()

    def mirror_image(self) -> None:
        self.recipe = dataclasses.replace(self.recipe, mirror=not self.recipe.mirror)
        self._apply_recipe()

    def toggle_crop(self) -> None:
        self.canvas.crop_mode = self.crop_button.isChecked()
        if self.canvas.crop_mode:
            self.view_original.setChecked(True)
            self.toggle_original()
            self._set_status("Drag a rectangle on the original image to crop. Reset all restores the full image.")

    def _crop_selected(self, box: Box) -> None:
        if self.worker:
            return
        self.recipe = dataclasses.replace(self.recipe, crop=box)
        self.crop_button.setChecked(False)
        self.canvas.crop_mode = False
        self._apply_recipe()

    def toggle_original(self) -> None:
        if self.source is None or self.worker:
            return
        original = self.view_original.isChecked()
        self.canvas.set_image(self.source if original else self.preview)
        self.view_original.setText("Show processed" if original else "Show original")
        if self.result and self.editor.linked:
            words = words_on_source(self.result.words, self.source.size, self.preview.size, self.recipe) if original else self.result.words
            self.canvas.set_words(words)
        if original and self.recipe != Recipe():
            message = "Original image. Recognized words stay linked through cleanup, crop, and rotation." if self.result and self.editor.linked else "Original image. Cleanup settings are retained for recognition."
            self._set_status(message)

    def _edition_changed(self, *_args) -> None:
        if not hasattr(self, "method_combo"):
            return
        self.refresh_methods()
        if hasattr(self, "memory"):
            self._update_memory()

    def refresh_methods(self) -> None:
        selected = self.method_combo.currentData()
        self.method_combo.blockSignals(True)
        self.method_combo.clear()
        for name, method in (("Fast OCR", "tesseract-fast"), ("Precision OCR", "tesseract-best")):
            if method in self.profile["methods"]:
                self.method_combo.addItem(name, method)
                self.method_combo.model().item(self.method_combo.count() - 1).setEnabled(method != "tesseract-best" or self.edition.best_data)
        for pack in self.packs if "vision" in self.profile["methods"] else []:
            self.method_combo.addItem(f"{pack.name} · AI", f"vision:{pack.id}")
            allowed, reason = pack.admission(self.edition)
            item = self.method_combo.model().item(self.method_combo.count() - 1)
            item.setEnabled(allowed)
            item.setToolTip(reason)
        if not self.method_combo.count():
            self.method_combo.addItem("Configure a vision model in Settings", None)
            self.method_combo.model().item(0).setEnabled(False)
        index = self.method_combo.findData(selected)
        if index < 0 or not self.method_combo.model().item(index).isEnabled():
            index = next((i for i in range(self.method_combo.count()) if self.method_combo.model().item(i).isEnabled()), 0)
        self.method_combo.setCurrentIndex(index)
        self.method_combo.blockSignals(False)
        self._method_changed()

    def _method_changed(self, *_args) -> None:
        if not hasattr(self, "compare_check"):
            return
        vision = str(self.method_combo.currentData()).startswith("vision:")
        self.compare_check.setEnabled(not vision and not self.worker)
        self.layout_combo.setEnabled(not vision and not self.worker)
        if vision:
            pack = next((p for p in self.packs if self.method_combo.currentData() == f"vision:{p.id}"), None)
            if pack and self.language_combo.currentData() != pack.languages and pack.languages != "ara+eng":
                self.language_combo.setCurrentIndex(self.language_combo.findData(pack.languages))
        item = self.method_combo.model().item(self.method_combo.currentIndex())
        self.recognize_button.setEnabled(self.source is not None and not self.worker and item is not None and item.isEnabled())
        policy = self._image_policy()
        if self.source is not None and self._preview_limits != (policy.max_pixels, policy.max_edge):
            self._apply_recipe()

    def _image_policy(self):
        method = str(self.method_combo.currentData())
        pack = next((p for p in self.packs if method == f"vision:{p.id}"), None)
        return image_policy(self.edition, method, pack)

    def recognize(self) -> None:
        if self.source is None or self.worker or not self._confirm_replace():
            return
        method = self.method_combo.currentData()
        if not method:
            self._set_status("Add a local model in Settings before recognizing text.")
            return
        preview_pending = self.preview_timer.isActive()
        self.preview_timer.stop()
        if preview_pending:
            self._apply_recipe()
        # Restore the exact inference preview before locking the workspace.
        # This also releases a larger original-view pixmap in vision mode.
        if self.view_original.isChecked():
            self.view_original.setChecked(False)
            self.toggle_original()
        self.job += 1
        method = self.method_combo.currentData()
        pack = next((p for p in self.packs if method == f"vision:{p.id}"), None)
        request = Request(self.edition, self.language_combo.currentData(), method,
                          self.layout_combo.currentData(), self.recipe, self.compare_check.isChecked(),
                          model_pack=pack, backend=self.vision_backend)
        self.worker = RecognitionWorker(self.job, self.source, request, self)
        self.worker.resultReady.connect(self._recognized)
        self.worker.failed.connect(self._recognition_failed)
        self.worker.progress.connect(self._set_status)
        self.worker.finished.connect(self._worker_finished)
        self._set_busy(True)
        self._set_status("Preparing image…")
        self.worker.start()

    def _recognized(self, job: int, result: OCRResult, alternatives: list[OCRResult]) -> None:
        if job != self.job:
            return
        self.result, self.alternatives = result, alternatives
        self.editor.set_result(result)
        self.view_original.setChecked(False)
        self.view_original.setText("Show original")
        if self.preview is not None:
            self.canvas.set_image(self.preview)
        self.canvas.set_words(result.words)
        if result.text:
            confidence = f" · {result.confidence:.0f}% OCR confidence" if result.confidence is not None else ""
            suffix = " · AI transcription; verify against the image" if result.engine.startswith("vision:") else ""
            self._set_status(f"Ready to copy · {result.elapsed:.1f}s · {result.backend}{confidence}{suffix}")
        else:
            self._set_status(result.note or "No text found. Try a tighter crop or another layout.")

    def _recognition_failed(self, job: int, message: str) -> None:
        if job == self.job:
            self._set_status(message, error="cancelled" not in message.lower())

    def _worker_finished(self) -> None:
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        self._set_busy(False)
        self._update_memory()
        if self._closing:
            self.close()

    def cancel_recognition(self) -> None:
        if self.worker:
            self.worker.cancel.set()
            self._set_status("Stopping recognition…")

    def escape(self) -> None:
        capture = getattr(self, "capture_controller", None)
        if capture:
            capture.cancel()
            return
        if self.worker:
            self.cancel_recognition()
        else:
            self.canvas.set_selection(set())
            self.editor.setExtraSelections([])
            self.copy_selection.setEnabled(False)
            self.crop_button.setChecked(False)
            self.canvas.crop_mode = False

    def _image_selected(self, indices: set[int]) -> None:
        self.editor.highlight_words(indices)
        self.copy_selection.setEnabled(bool(indices) and self.editor.linked)
        if indices:
            self._set_status(f"{len(indices)} source words selected. Choose Copy selection to keep just these words.")

    def _editor_selected(self, indices: set[int]) -> None:
        self.canvas.set_selection(indices)
        self.copy_selection.setEnabled(bool(indices) and self.editor.linked)

    def _link_changed(self, linked: bool) -> None:
        text = self.editor.toPlainText()
        if linked:
            status = "Linked to image"
        elif not text:
            status = ""
        elif self.editor.document().isModified():
            status = "Edited text"
        elif self.result and self.result.engine.startswith("vision"):
            status = "AI transcription"
        else:
            status = "Source unlinked"
        self.link_status.setText(status)
        self.boxes.setEnabled(linked)
        self.boxes.setToolTip("Show located words from Fast or Precision OCR. AI transcription has no word coordinates.")
        if not linked:
            self.canvas.set_words([])
            self.copy_selection.setEnabled(False)

    def _boxes_toggled(self, checked: bool) -> None:
        self.canvas.show_boxes = checked
        self.canvas.viewport().update()

    def copy_image_selection(self) -> None:
        if self.result and self.editor.linked and self.canvas.selected:
            text = selected_text(self.result.words, self.canvas.selected)
            QApplication.clipboard().setText(text)
            self._set_status(f"Copied {len(self.canvas.selected)} selected words.")

    def copy_all(self) -> None:
        text = self.editor.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self._set_status("Copied. Paste your text wherever you need it.")

    def save_text(self) -> None:
        text = self.editor.toPlainText()
        if not text:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save recognized text", "ocready.txt", "Text files (*.txt)")
        if path:
            try:
                Path(path).write_text(text, encoding="utf-8")
                self.editor.document().setModified(False)
                self._set_status("Text saved as UTF-8.")
            except OSError as exc:
                self._set_status(f"Could not save text: {exc}", error=True)

    def join_lines(self) -> None:
        if self.worker:
            return
        text = self.editor.toPlainText()
        joined = unwrap_lines(text)
        if joined != text:
            cursor = self.editor.textCursor()
            cursor.beginEditBlock()
            cursor.select(cursor.SelectionType.Document)
            cursor.insertText(joined)
            cursor.endEditBlock()
            self._set_status("Wrapped lines joined. Ctrl+Z restores the original line breaks.")

    def _update_text_stats(self) -> None:
        text = self.editor.toPlainText()
        self.text_stats.setText(f"{len(text.split())} words · {len(text)} characters")
        self.copy_all_button.setEnabled(bool(text))
        self.save_button.setEnabled(bool(text))

    def _update_memory(self) -> None:
        self.memory.setText(f"{tree_rss() / 1_000_000:.0f} / {self.edition.budget_label}")
        self.memory.setToolTip("Current app, onefile launcher, and OCR process-tree RSS. Sampled; GPU VRAM is separate.")

    def capture_region(self) -> None:
        # The platform adapter is isolated so native capture can evolve independently.
        from ocready.ui.capture import start_capture
        start_capture(self)

    def show_help(self) -> None:
        QMessageBox.information(self, "A few shortcuts to your words", "1. Open, paste, or capture an image.\n2. Choose Recognize text.\n3. Edit, select, and copy.\n\nClick a word in the picture, or drag over a sentence.\nSelecting text also highlights its source. Manual edits turn off source linking until you recognize again.\n\nCtrl+O  Open image\nCtrl+Shift+V  Paste image\nCtrl+Shift+S  Capture region\nCtrl+Enter  Recognize\nCtrl+Shift+C  Copy all\nCtrl+S  Save text\nEscape  Cancel or clear selection\n\nMouse wheel  Zoom image\nMiddle mouse drag  Pan image\n\nPocket: fast OCR, 350 MB budget\nEveryday: fast + precision OCR, 1 GB budget\nStudio: OCR + optional local vision models, 4 GB budget\n\nRAM is sampled, not an OS-enforced hard ceiling. Nothing is uploaded.")

    def show_settings(self) -> None:
        if self.worker:
            return
        from ocready.ui.settings import SettingsDialog
        SettingsDialog(self).exec()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and not self.worker:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if not self.worker:
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    self.open_path(url.toLocalFile())
                    event.acceptProposedAction()
                    break

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker and self.worker.isRunning():
            self._closing = True
            self.cancel_recognition()
            event.ignore()
            return
        capture = getattr(self, "capture_controller", None)
        if capture:
            capture.finish("Capture stopped.")
        if not self._closing and not self._confirm_replace():
            event.ignore()
            return
        try:
            save_settings({"edition": self.edition.id, "language": self.language_combo.currentData(),
                           "vision_backend": self.vision_backend})
        except OSError:
            pass
        event.accept()
