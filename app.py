#!/usr/bin/env python
"""Application launcher."""

import sys

from main_window import MainWindow
from qt_imports import QtWidgets


def run(fmt, out_root, img_paths, lock_y=False):
    """Run the annotation application.

    Args:
        fmt: BaseFormat instance.
        out_root: Output directory for saved annotations.
        img_paths: List of image paths to edit.
        lock_y: If True, y coordinate is locked (TuSimple mode).
    """
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(fmt, out_root, img_paths, lock_y=lock_y)
    window.show()
    sys.exit(app.exec_())
