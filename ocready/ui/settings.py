import dataclasses
import json
import uuid
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ocready.__main__ import diagnostics
from ocready.core.models import TRANSCRIPTION_PROMPT, ModelPack, load_pack, save_packs


class SettingsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.packs = list(window.packs)
        self.pack_id = ""
        self.setWindowTitle("OCReady settings")
        self.resize(790, 700)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        tabs = QTabWidget()
        outer.addWidget(tabs)
        runtime = QWidget()
        layout = QVBoxLayout(runtime)
        title = QLabel("Everything stays on your device.")
        title.setObjectName("PaneTitle")
        layout.addWidget(title)
        text = QLabel("Fast and Precision OCR work offline with Arabic and English.\nRAM budgets include the app and its OCR children. Sampling is a guardrail, not an absolute OS limit.")
        text.setWordWrap(True)
        layout.addWidget(text)
        details = QPlainTextEdit()
        details.setReadOnly(True)
        details.setPlainText(json.dumps(diagnostics(), ensure_ascii=False, indent=2))
        layout.addWidget(details)
        tabs.addTab(runtime, "Offline OCR & diagnostics")
        models = QWidget()
        layout = QVBoxLayout(models)
        intro = QLabel("Add a local vision model for difficult images. Everyday admits compact packs; Studio admits larger ones.\nSelect a llama-mtmd-cli runner, GGUF model, and matching vision projector. Nothing is uploaded.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        row = QHBoxLayout()
        self.list = QListWidget()
        self.list.setMaximumHeight(85)
        self.list.currentRowChanged.connect(self.select_pack)
        row.addWidget(self.list, 1)
        actions = QVBoxLayout()
        for name, slot in (("New model", self.new_pack), ("Import manifest", self.import_pack), ("Remove", self.remove_pack)):
            item = QPushButton(name)
            item.clicked.connect(slot)
            actions.addWidget(item)
        row.addLayout(actions)
        layout.addLayout(row)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. GLM-OCR · local")
        form.addRow("Display name", self.name)
        self.fields = {}
        for key, title in (("runner", "CPU runner"), ("model", "Model GGUF"), ("projector", "Vision projector"), ("cuda_runner", "CUDA runner (optional)")):
            row = QHBoxLayout()
            field = QLineEdit()
            field.setAccessibleName(title)
            self.fields[key] = field
            row.addWidget(field, 1)
            browse = QPushButton("Browse")
            browse.clicked.connect(lambda _checked=False, k=key: self.browse(k))
            row.addWidget(browse)
            form.addRow(title, row)
        row = QHBoxLayout()
        self.memory = QSpinBox()
        self.memory.setRange(100, 3800)
        self.memory.setValue(2800)
        self.memory.setSuffix(" MB")
        self.memory.setToolTip("Estimate the runner's CPU RAM including weights, visual encoder, KV cache and workspace. App memory is added separately.")
        row.addWidget(self.memory)
        row.addWidget(QLabel("Output limit"))
        self.tokens = QSpinBox()
        self.tokens.setRange(64, 2048)
        self.tokens.setValue(512)
        self.tokens.setSuffix(" tokens")
        row.addWidget(self.tokens)
        form.addRow("Runner RAM estimate", row)
        self.backend = QComboBox()
        for name, key in (("Automatic · CUDA when usable, otherwise CPU", "auto"), ("CPU", "cpu"), ("Prefer CUDA · fall back to CPU", "cuda")):
            self.backend.addItem(name, key)
        self.backend.setCurrentIndex(max(0, self.backend.findData(window.vision_backend)))
        form.addRow("Compute", self.backend)
        self.languages = QComboBox()
        for name, key in (("Arabic + English", "ara+eng"), ("English only", "eng"), ("Arabic only", "ara")):
            self.languages.addItem(name, key)
        form.addRow("Model languages", self.languages)
        self.prompt = QPlainTextEdit()
        self.prompt.setMaximumHeight(80)
        self.prompt.setPlainText(TRANSCRIPTION_PROMPT)
        self.languages.setCurrentIndex(0)
        form.addRow("Recognition prompt", self.prompt)
        layout.addLayout(form)
        self.message = QLabel("Estimates are not certified memory measurements. AI transcription can omit or invent text.")
        self.message.setWordWrap(True)
        self.message.setObjectName("Subtle")
        layout.addWidget(self.message)
        save = QPushButton("Save model")
        save.setObjectName("Primary")
        save.clicked.connect(self.save_model)
        layout.addWidget(save, 0, Qt.AlignmentFlag.AlignRight)
        tabs.addTab(models, "Vision models")
        done = QPushButton("Done")
        done.clicked.connect(self.accept)
        outer.addWidget(done, 0, Qt.AlignmentFlag.AlignRight)
        self.refresh_list()

    def refresh_list(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for pack in self.packs:
            self.list.addItem(pack.name)
        self.list.blockSignals(False)
        if self.packs:
            self.list.setCurrentRow(0)
        else:
            self.new_pack()

    def new_pack(self) -> None:
        self.pack_id = uuid.uuid4().hex[:12]
        self.list.setCurrentRow(-1)
        self.name.clear()
        for field in self.fields.values():
            field.clear()
        self.memory.setValue(2800)
        self.tokens.setValue(512)
        self.prompt.setPlainText(TRANSCRIPTION_PROMPT)

    def select_pack(self, row: int) -> None:
        if row < 0 or row >= len(self.packs):
            return
        pack = self.packs[row]
        self.pack_id = pack.id
        self.name.setText(pack.name)
        for key, field in self.fields.items():
            field.setText(getattr(pack, key))
        self.memory.setValue(pack.memory_mb)
        self.tokens.setValue(pack.tokens)
        self.prompt.setPlainText(pack.prompt)
        self.languages.setCurrentIndex(self.languages.findData(pack.languages))

    def browse(self, key: str) -> None:
        file_filter = "GGUF models (*.gguf);;All files (*)" if key in {"model", "projector"} else "All files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Choose a local file", self.fields[key].text(), file_filter)
        if path:
            self.fields[key].setText(path)

    def save_model(self) -> None:
        try:
            existing = next((pack for pack in self.packs if pack.id == self.pack_id), None)
            base = existing or ModelPack(self.pack_id, self.name.text().strip(), "", "", "")
            pack = dataclasses.replace(base, name=self.name.text().strip(),
                                       **{key: str(Path(field.text()).expanduser().resolve()) if field.text().strip() else "" for key, field in self.fields.items()},
                                       memory_mb=self.memory.value(), tokens=self.tokens.value(), prompt=self.prompt.toPlainText(),
                                       languages=self.languages.currentData())
            pack.validate()
            self._persist([p for p in self.packs if p.id != pack.id] + [pack])
            self.window.vision_backend = self.backend.currentData()
            self.list.setCurrentRow(next(i for i, p in enumerate(self.packs) if p.id == pack.id))
            self.message.setText("Model saved. Choose an edition with enough RAM, then select the model in the method list.")
        except Exception as exc:
            self.message.setText(str(exc))

    def _persist(self, packs: list[ModelPack]) -> None:
        save_packs(packs)
        self.packs = packs
        self.window.packs = list(packs)
        self.window.refresh_methods()
        self.refresh_list()

    def import_pack(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import a model manifest", "", "JSON manifest (*.json)")
        if path:
            try:
                pack = load_pack(Path(path))
                pack.validate()
                self._persist([p for p in self.packs if p.id != pack.id] + [pack])
                self.message.setText("Local model imported. Its files were not moved or copied.")
            except Exception as exc:
                self.message.setText(str(exc))

    def remove_pack(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            if self.packs[row].bundled:
                self.message.setText("This model is built into this edition. Its configuration and files are kept with the application.")
                return
            self._persist([p for i, p in enumerate(self.packs) if i != row])
            self.message.setText("Configuration removed. Your model files were kept.")

    def accept(self) -> None:
        self.window.vision_backend = self.backend.currentData()
        super().accept()
