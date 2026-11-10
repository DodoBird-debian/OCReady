from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

LIGHT = """
QWidget { color: #25344c; font-family: 'Inter', 'Segoe UI', 'Noto Sans', sans-serif; font-size: 13px; }
QMainWindow, QDialog { background: #f5f7fb; }
QLabel#Brand { font-size: 22px; font-weight: 750; letter-spacing: -0.8px; }
QLabel#Eyebrow { color: #57708f; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
QLabel#Hero { font-size: 28px; font-weight: 700; letter-spacing: -0.7px; }
QLabel#Subtle { color: #728097; }
QLabel#PaneTitle { font-size: 15px; font-weight: 650; }
QLabel#Badge { color: #276754; background: #e9f5ef; padding: 6px 10px; border-radius: 7px; font-size: 11px; }
QFrame#Card { background: #ffffff; border: 1px solid #e1e6ef; border-radius: 12px; }
QFrame#Divider { background: #e6eaf1; max-height: 1px; border: none; }
QPushButton, QToolButton { background: #ffffff; border: 1px solid #dce3ed; border-radius: 7px; padding: 9px 14px; font-weight: 550; }
QPushButton:hover, QToolButton:hover { background: #edf2fa; border-color: #bacbe2; }
QPushButton:pressed, QToolButton:pressed { background: #e2eaf6; }
QPushButton:focus, QToolButton:focus, QComboBox:focus { border: 1px solid #497de8; }
QPushButton:disabled, QToolButton:disabled { color: #9aa6b8; background: #f5f7fa; border-color: #e5eaf1; }
QPushButton#Primary { background: #386bdf; border-color: #386bdf; color: #ffffff; padding: 11px 20px; font-weight: 650; }
QPushButton#Primary:hover { background: #295bce; }
QPushButton#Primary:disabled { background: #b4c7ed; border-color: #b4c7ed; color: #ffffff; }
QPushButton#Quiet { background: transparent; border-color: transparent; color: #57708f; padding: 6px 8px; }
QPushButton#Quiet:hover { background: #eaf0f9; color: #386bdf; }
QPushButton#Danger { background: #fff2f0; color: #b34a40; border-color: #f1cbc5; }
QComboBox { background: #ffffff; border: 1px solid #dce3ed; border-radius: 7px; padding: 8px 28px 8px 11px; min-height: 18px; }
QComboBox:hover { border-color: #bacbe2; }
QComboBox:disabled { color: #9aa6b8; background: #f5f7fa; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #dce3ed; selection-background-color: #e6efff; selection-color: #25344c; padding: 5px; }
QPlainTextEdit { background: #ffffff; border: none; padding: 15px; selection-background-color: #d5e5ff; selection-color: #183d76; font-size: 16px; }
QLineEdit, QSpinBox, QDoubleSpinBox { background: #ffffff; border: 1px solid #dce3ed; border-radius: 6px; padding: 7px; }
QCheckBox { spacing: 7px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #b7c5d8; border-radius: 4px; background: white; }
QCheckBox::indicator:checked { background: #386bdf; border-color: #386bdf; }
QSplitter::handle { background: transparent; width: 14px; }
QSplitter::handle:hover { background: #e6ecf6; border-radius: 5px; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 3px; }
QScrollBar::handle:vertical { background: #cbd5e3; border-radius: 3px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { background: transparent; height: 9px; margin: 3px; }
QScrollBar::handle:horizontal { background: #cbd5e3; border-radius: 3px; min-width: 25px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QProgressBar { background: #e7eefb; border: none; border-radius: 2px; max-height: 3px; color: transparent; }
QProgressBar::chunk { background: #5d88e6; border-radius: 2px; }
QStatusBar { background: #f5f7fb; color: #728097; border-top: 1px solid #e5eaf1; }
QToolTip { background: #26364d; color: white; border: none; border-radius: 5px; padding: 7px; }
QGroupBox { border: 1px solid #dce3ed; border-radius: 9px; margin-top: 15px; padding: 15px 12px 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(LIGHT)
    app.setFont(QFont("Noto Sans", 10))


def app_icon() -> QIcon:
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#386bdf"))
    painter.drawRoundedRect(4, 4, 120, 120, 30, 30)
    painter.setPen(QColor("white"))
    painter.setFont(QFont("DejaVu Sans", 48, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "O")
    painter.setBrush(QColor("#92e2c2"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(83, 82, 25, 25)
    painter.end()
    return QIcon(pixmap)
