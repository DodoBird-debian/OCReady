import dataclasses
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ocready.core.cuda_helpers import NEURAL_ADAPTER, cuda_helper, save_cuda_helper
from ocready.core.neural_packs import load_neural_pack, load_neural_packs, save_neural_packs


class NeuralSettings(QWidget):
    def __init__(self, window):
        super().__init__()
        self.setObjectName("SettingsPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.window = window
        self.packs = list(window.neural_packs)
        layout = QVBoxLayout(self)
        intro = QLabel("Local neural OCR reads Arabic and English using a detector and a recognition model. It selects detected lines in the picture; it does not invent individual word boxes.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.list = QListWidget()
        self.list.setMaximumHeight(115)
        self.list.currentRowChanged.connect(self.select_pack)
        layout.addWidget(self.list)
        buttons = QHBoxLayout()
        for title, slot in (("Import local pack", self.import_pack), ("Remove configuration", self.remove_pack)):
            button = QPushButton(title)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(115)
        layout.addWidget(self.details)
        self.options = QWidget()
        form = QFormLayout(self.options)
        form.setContentsMargins(0, 0, 0, 0)
        helper_row = QHBoxLayout()
        self.cuda_runner = QLineEdit()
        self.cuda_runner.setAccessibleName("Optional neural CUDA runner")
        self.cuda_runner.setPlaceholderText("Use the pack's built-in runner")
        self.cuda_runner.setToolTip("Choose a compatible external CUDA worker, or clear to use the built-in runner. The embedded model files are reused.")
        helper_row.addWidget(self.cuda_runner, 1)
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse_cuda)
        helper_row.addWidget(browse)
        form.addRow("CUDA runner (optional)", helper_row)
        self.memory = QSpinBox()
        self.memory.setRange(100, 3800)
        self.memory.setSuffix(" MB")
        self.memory.setToolTip("Conservative complete runner RAM estimate. The app and image reserve are added separately.")
        form.addRow("Runner RAM estimate", self.memory)
        self.pixels = QSpinBox()
        self.pixels.setRange(250, 4000)
        self.pixels.setSuffix(" thousand pixels")
        form.addRow("Image limit", self.pixels)
        self.edge = QSpinBox()
        self.edge.setRange(512, 3000)
        self.edge.setSuffix(" px")
        form.addRow("Longest edge", self.edge)
        self.direction = QComboBox()
        for name, value in (("Automatic · Arabic base when Arabic is present", "auto"), ("Arabic paragraph base", "rtl"), ("English paragraph base", "ltr")):
            self.direction.addItem(name, value)
        self.direction.setToolTip("Controls conversion of visual CTC order into copyable text. For English-led paragraphs with inline Arabic, choose English paragraph base.")
        form.addRow("Mixed-text reading order", self.direction)
        self.decode = QComboBox()
        self.decode.addItem("Visual order · tested Arabic PP-OCRv5 pack", "visual")
        self.decode.addItem("Already logical · advanced compatible models", "logical")
        form.addRow("Model text encoding", self.decode)
        layout.addWidget(self.options)
        self.save_button = QPushButton("Save pack options")
        self.save_button.clicked.connect(self.save_options)
        layout.addWidget(self.save_button)
        self.message = QLabel("Import the pack.json supplied with a compatible local worker and models. Files remain on this device. Estimates are not memory certifications.")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        layout.addStretch()
        self.refresh()

    def refresh(self):
        self.list.blockSignals(True)
        self.list.clear()
        for pack in self.packs:
            self.list.addItem(pack.name)
        self.list.blockSignals(False)
        self.options.setEnabled(bool(self.packs))
        self.save_button.setEnabled(bool(self.packs))
        if self.packs:
            self.list.setCurrentRow(0)
        else:
            self.details.setPlainText("No neural pack configured. Built-in packs appear here automatically.")

    def select_pack(self, row):
        if not 0 <= row < len(self.packs):
            return
        pack = self.packs[row]
        self.details.setPlainText(f"{pack.name}\nLanguages: {pack.languages}\nSource: {pack.source}\nLicense: {pack.license}\nRunner: {pack.runner}")
        self.memory.setValue(pack.memory_mb)
        self.pixels.setValue(pack.max_pixels // 1000)
        self.edge.setValue(pack.max_edge)
        self.direction.setCurrentIndex(self.direction.findData(pack.direction))
        self.decode.setCurrentIndex(self.decode.findData(pack.decode))
        self.cuda_runner.setText(cuda_helper("neural", pack.id, NEURAL_ADAPTER) if pack.bundled else pack.cuda_runner)

    def browse_cuda(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a compatible neural CUDA worker", self.cuda_runner.text(), "All files (*)")
        if path:
            self.cuda_runner.setText(path)

    def persist(self, packs):
        save_neural_packs(packs)
        self.packs = load_neural_packs()
        self.window.neural_packs = list(self.packs)
        self.window.refresh_methods()
        self.refresh()

    def import_pack(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import a neural OCR pack", "", "JSON manifest (*.json)")
        if not path:
            return
        try:
            pack = dataclasses.replace(load_neural_pack(Path(path)), bundled=False)
            pack.validate()
            self.persist([p for p in self.packs if p.id != pack.id] + [pack])
            self.message.setText("Neural pack imported. Choose it from the OCR method list in Everyday or Studio.")
        except Exception as exc:
            self.message.setText(str(exc))

    def remove_pack(self):
        row = self.list.currentRow()
        if not 0 <= row < len(self.packs):
            return
        if self.packs[row].bundled:
            self.message.setText("This pack is built into the application. Its files and configuration are retained.")
            return
        self.persist([p for i, p in enumerate(self.packs) if i != row])
        self.message.setText("Configuration removed. The worker and model files were kept.")

    def save_options(self):
        row = self.list.currentRow()
        if not 0 <= row < len(self.packs):
            return
        try:
            pack = dataclasses.replace(self.packs[row], memory_mb=self.memory.value(), max_pixels=self.pixels.value() * 1000,
                                       max_edge=self.edge.value(), direction=self.direction.currentData(), decode=self.decode.currentData())
            if not pack.bundled:
                pack = dataclasses.replace(pack, cuda_runner=str(Path(self.cuda_runner.text()).expanduser().resolve()) if self.cuda_runner.text().strip() else "")
            pack.validate(require_cuda=not pack.bundled)
            if pack.bundled:
                save_cuda_helper("neural", pack.id, NEURAL_ADAPTER, self.cuda_runner.text())
            self.persist([pack if i == row else p for i, p in enumerate(self.packs)])
            self.list.setCurrentRow(row)
            self.message.setText("Pack options saved. Reading order affects newly recognized text.")
        except Exception as exc:
            self.message.setText(str(exc))
