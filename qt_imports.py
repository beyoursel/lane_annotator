"""Unified Qt imports for easy migration between PyQt5 and PySide6."""

try:
    from PyQt5 import QtWidgets, QtCore, QtGui
    from PyQt5.QtCore import pyqtSignal as Signal
    from PyQt5.QtCore import pyqtSlot as Slot
    from PyQt5.QtCore import Qt
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "PyQt5 is required. Install it with: pip install PyQt5") from e
