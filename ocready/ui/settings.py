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
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ocready.__main__ import diagnostics
from ocready.core.cuda_helpers import cuda_helper, save_cuda_helper
from ocready.core.models import TRANSCRIPTION_PROMPT, ModelPack, load_pack, load_packs, save_packs
from ocready.engines.vision_adapters import ADAPTERS
from ocready.ui.neural_settings import NeuralSettings


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
        tabs.setObjectName("SettingsTabs")
        outer.addWidget(tabs)
        runtime = QWidget()
        runtime.setObjectName("SettingsPage")
        layout = QVBoxLayout(runtime)
        title = QLabel("Everything stays on your device.")
        title.setObjectName("PaneTitle")
        layout.addWidget(title)
        methods = set(window.profile["methods"])
        method_names = {"tesseract-fast": "Fast OCR", "tesseract-best": "Precision OCR", "vision": "Vision models", "neural": "Neural OCR"}
        available = " · ".join(name for key, name in method_names.items() if key in methods)
        text = QLabel(f"OCR options: {available}\n{window.edition.name} · {window.edition.budget_label} RAM budget, including the app and OCR workers.\nSampling is a guardrail, not an absolute OS limit.")
        text.setWordWrap(True)
        layout.addWidget(text)
        shortcuts = QLabel("Capture a region: Ctrl+Shift+S\nPaste an image: Ctrl+Shift+V\nCopy all text: Ctrl+Shift+C")
        shortcuts.setWordWrap(True)
        layout.addWidget(shortcuts)
        details = QPlainTextEdit()
        details.setReadOnly(True)
        details.setAccessibleName("Technical diagnostics")
        details.setPlainText(json.dumps(diagnostics(), ensure_ascii=False, indent=2))
        details.hide()
        technical = QPushButton("Show technical details")
        technical.setCheckable(True)
        technical.toggled.connect(lambda expanded: (details.setVisible(expanded), technical.setText("Hide technical details" if expanded else "Show technical details")))
        layout.addWidget(technical, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(details, 1)
        layout.addStretch()
        tabs.addTab(runtime, "Offline OCR & diagnostics")
        models = QWidget()
        models.setObjectName("SettingsPage")
        layout = QVBoxLayout(models)
        intro = QLabel("Add or swap local vision models. Everyday admits compact packs; Studio admits larger ones.\nChoose the runner's runtime and compatible model files. llama.cpp uses GGUF weights and a matching projector. Nothing is uploaded.")
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
        self.adapter = QComboBox()
        self.adapter.setAccessibleName("Vision inference runtime")
        for adapter in ADAPTERS.values():
            self.adapter.addItem(adapter.name, adapter.id)
        self.adapter.setToolTip("Match the runner's interface. Existing GGUF packs use llama.cpp. Custom offline workers can implement OCReady JSON v1.")
        form.addRow("Inference runtime", self.adapter)
        self.fields = {}
        self.browse_buttons = {}
        for key, title in (("runner", "CPU runner"), ("model", "Model file"), ("projector", "Vision projector"), ("cuda_runner", "CUDA runner (optional)")):
            row = QHBoxLayout()
            field = QLineEdit()
            field.setAccessibleName(title)
            self.fields[key] = field
            row.addWidget(field, 1)
            browse = QPushButton("Browse")
            self.browse_buttons[key] = browse
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
        row = QHBoxLayout()
        self.pixels = QSpinBox()
        self.pixels.setRange(250, 2560)
        self.pixels.setSingleStep(250)
        self.pixels.setValue(1000)
        self.pixels.setSuffix(" thousand pixels")
        self.pixels.setToolTip("Bounds both the preview and AI input. Smaller values reserve RAM; crop the original to keep small text readable.")
        row.addWidget(self.pixels)
        row.addWidget(QLabel("Longest edge"))
        self.edge = QSpinBox()
        self.edge.setRange(512, 1600)
        self.edge.setValue(1600)
        self.edge.setSuffix(" px")
        row.addWidget(self.edge)
        form.addRow("AI image limit", row)
        self.backend = QComboBox()
        for name, key in (("Automatic · CUDA when usable, otherwise CPU", "auto"), ("CPU", "cpu"), ("Prefer CUDA · fall back to CPU", "cuda")):
            self.backend.addItem(name, key)
        self.backend.setCurrentIndex(max(0, self.backend.findData(window.vision_backend)))
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(models)
        tabs.addTab(scroll, "Vision models")
        neural_scroll = QScrollArea()
        neural_scroll.setWidgetResizable(True)
        neural_scroll.setFrameShape(QFrame.Shape.NoFrame)
        neural_scroll.setWidget(NeuralSettings(window))
        tabs.addTab(neural_scroll, "Neural OCR")
        tabs.setTabVisible(1, "vision" in methods)
        tabs.setTabVisible(2, "neural" in methods)
        model_compute = bool(methods & {"vision", "neural"})
        if not model_compute:
            tabs.tabBar().hide()
        done = QPushButton("Done")
        done.clicked.connect(self.accept)
        shared = QHBoxLayout()
        compute_label = QLabel("Compute")
        shared.addWidget(compute_label)
        shared.addWidget(self.backend, 1)
        if not model_compute:
            shared.addStretch(1)
        shared.addWidget(done)
        outer.addLayout(shared)
        compute_label.setVisible(model_compute)
        self.backend.setVisible(model_compute)
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
            field.setReadOnly(False)
            field.setToolTip("")
            field.setPlaceholderText("")
        for browse in self.browse_buttons.values():
            browse.setEnabled(True)
        self.memory.setValue(2800)
        self.tokens.setValue(512)
        self.pixels.setValue(1000)
        self.edge.setValue(1600)
        self.prompt.setPlainText(TRANSCRIPTION_PROMPT)
        self.adapter.setEnabled(True)
        self.adapter.setCurrentIndex(self.adapter.findData("llama.cpp"))
        self.languages.setCurrentIndex(0)

    def select_pack(self, row: int) -> None:
        if row < 0 or row >= len(self.packs):
            return
        pack = self.packs[row]
        self.pack_id = pack.id
        self.name.setText(pack.name)
        self.adapter.setCurrentIndex(self.adapter.findData(pack.adapter))
        self.adapter.setEnabled(not pack.bundled)
        for key, field in self.fields.items():
            helper = key == "cuda_runner" and pack.bundled
            locked = pack.bundled and not helper
            field.setText(cuda_helper("vision", pack.id, pack.adapter) if helper else getattr(pack, key))
            field.setReadOnly(locked)
            self.browse_buttons[key].setEnabled(not locked)
            field.setPlaceholderText("Use the built-in runner" if helper else "")
            field.setToolTip("Choose a compatible external CUDA runner, or clear to use the built-in runner. CPU fallback keeps the embedded weights." if helper else
                             "Built-in assets are managed by this edition. Use New model for other external files." if locked else "")
        self.memory.setValue(pack.memory_mb)
        self.tokens.setValue(pack.tokens)
        self.pixels.setValue(pack.max_pixels // 1000)
        self.edge.setValue(pack.max_edge)
        self.prompt.setPlainText(pack.prompt)
        self.languages.setCurrentIndex(self.languages.findData(pack.languages))

    def browse(self, key: str) -> None:
        file_filter = "GGUF models (*.gguf);;All files (*)" if key in {"model", "projector"} and self.adapter.currentData() == "llama.cpp" else "All files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Choose a local file", self.fields[key].text(), file_filter)
        if path:
            self.fields[key].setText(path)

    def save_model(self) -> None:
        try:
            existing = next((pack for pack in self.packs if pack.id == self.pack_id), None)
            base = existing or ModelPack(self.pack_id, self.name.text().strip(), "", "", "")
            pack = dataclasses.replace(base, name=self.name.text().strip(),
                                       **({} if base.bundled else {key: str(Path(field.text()).expanduser().resolve()) if field.text().strip() else "" for key, field in self.fields.items()}),
                                       memory_mb=self.memory.value(), tokens=self.tokens.value(), prompt=self.prompt.toPlainText(),
                                       languages=self.languages.currentData(), adapter=base.adapter if base.bundled else self.adapter.currentData())
            pack = dataclasses.replace(pack, max_pixels=self.pixels.value() * 1000, max_edge=self.edge.value())
            pack.validate(require_cuda=not pack.bundled)
            if pack.bundled:
                save_cuda_helper("vision", pack.id, pack.adapter, self.fields["cuda_runner"].text())
            self._persist([p for p in self.packs if p.id != pack.id] + [pack])
            self.window.vision_backend = self.backend.currentData()
            self.list.setCurrentRow(next(i for i, p in enumerate(self.packs) if p.id == pack.id))
            self.message.setText("Model saved. Choose an edition with enough RAM, then select the model in the method list.")
        except Exception as exc:
            self.message.setText(str(exc))

    def _persist(self, packs: list[ModelPack]) -> None:
        save_packs(packs)
        self.packs = load_packs()
        self.window.packs = list(self.packs)
        self.window.refresh_methods()
        self.refresh_list()

    def import_pack(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import a model manifest", "", "JSON manifest (*.json)")
        if path:
            try:
                pack = dataclasses.replace(load_pack(Path(path)), bundled=False)
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
