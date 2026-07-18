#!/usr/bin/env python
"""Side panels for image list and lane list."""

import os.path as osp
from typing import List, Optional

from models import Lane, LaneImage, LanePoint
from qt_imports import QtCore, QtGui, QtWidgets, Signal


class ImageListPanel(QtWidgets.QWidget):
    """Left panel showing list of images."""

    imageSelected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._images: List[LaneImage] = []
        self._current_index: int = -1

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self._list = QtWidgets.QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        self.setLayout(layout)

    def set_images(self, images: List[LaneImage]):
        self._images = images
        self._list.clear()
        for img in images:
            name = osp.basename(img.img_path)
            item = QtWidgets.QListWidgetItem(name)
            self._list.addItem(item)
        self._current_index = -1

    def set_current_index(self, index: int):
        self._current_index = index
        self._list.setCurrentRow(index)

    def update_image_state(self, index: int):
        if 0 <= index < len(self._images):
            img = self._images[index]
            item = self._list.item(index)
            if item is not None:
                name = osp.basename(img.img_path)
                if img.dirty:
                    item.setText(f"* {name}")
                else:
                    item.setText(name)

    def _on_row_changed(self, row: int):
        if row != self._current_index:
            self._current_index = row
            self.imageSelected.emit(row)


class LaneListPanel(QtWidgets.QWidget):
    """Right panel showing lane list and point properties."""

    laneSelected = Signal(int)
    addLaneRequested = Signal()
    deleteLaneRequested = Signal(int)
    copyLaneRequested = Signal(int)
    laneVisibilityChanged = Signal(int, bool)
    laneColorChanged = Signal(int, QtGui.QColor)
    pointValueChanged = Signal(object, float, float)
    toggleValidityRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lanes: List[Lane] = []
        self._selected_lane: Optional[Lane] = None
        self._selected_point: Optional[LanePoint] = None
        self._lock_y: bool = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Lane list
        layout.addWidget(QtWidgets.QLabel("Lanes"))
        self._list = QtWidgets.QListWidget()
        self._list.currentRowChanged.connect(self._on_lane_row_changed)
        layout.addWidget(self._list)

        # Lane actions
        actions_layout = QtWidgets.QHBoxLayout()
        self._add_btn = QtWidgets.QPushButton("Add")
        self._add_btn.setToolTip("Add new lane (A)")
        self._delete_btn = QtWidgets.QPushButton("Del")
        self._delete_btn.setToolTip("Delete selected lane")
        self._copy_btn = QtWidgets.QPushButton("Copy")
        self._copy_btn.setToolTip("Copy selected lane")
        actions_layout.addWidget(self._add_btn)
        actions_layout.addWidget(self._delete_btn)
        actions_layout.addWidget(self._copy_btn)
        layout.addLayout(actions_layout)

        self._add_btn.clicked.connect(self.addLaneRequested)
        self._delete_btn.clicked.connect(self._on_delete_lane)
        self._copy_btn.clicked.connect(self._on_copy_lane)

        # Visibility & color
        vis_color_layout = QtWidgets.QHBoxLayout()
        self._visible_cb = QtWidgets.QCheckBox("Visible")
        self._visible_cb.setChecked(True)
        self._visible_cb.stateChanged.connect(self._on_visibility_changed)
        self._color_btn = QtWidgets.QPushButton("Color")
        self._color_btn.clicked.connect(self._on_color_changed)
        vis_color_layout.addWidget(self._visible_cb)
        vis_color_layout.addWidget(self._color_btn)
        layout.addLayout(vis_color_layout)

        # Point properties
        layout.addWidget(QtWidgets.QLabel("Point Properties"))
        form_layout = QtWidgets.QFormLayout()
        self._x_spin = QtWidgets.QDoubleSpinBox()
        self._x_spin.setRange(-1e6, 1e6)
        self._x_spin.setDecimals(3)
        self._x_spin.setSingleStep(1.0)
        self._x_spin.valueChanged.connect(self._on_point_value_changed)
        self._y_spin = QtWidgets.QDoubleSpinBox()
        self._y_spin.setRange(-1e6, 1e6)
        self._y_spin.setDecimals(3)
        self._y_spin.setSingleStep(1.0)
        self._y_spin.valueChanged.connect(self._on_point_value_changed)
        form_layout.addRow("X:", self._x_spin)
        form_layout.addRow("Y:", self._y_spin)
        layout.addLayout(form_layout)

        self._valid_btn = QtWidgets.QPushButton("Toggle Validity")
        self._valid_btn.setToolTip("Toggle point validity (TuSimple)")
        self._valid_btn.clicked.connect(self.toggleValidityRequested)
        layout.addWidget(self._valid_btn)

        layout.addStretch()
        self.setLayout(layout)
        self._update_ui()

    def set_lock_y(self, lock: bool):
        self._lock_y = lock
        self._y_spin.setEnabled(not lock)

    def set_lanes(self, lanes: List[Lane]):
        self._lanes = lanes
        self._list.clear()
        for i, lane in enumerate(lanes):
            item = QtWidgets.QListWidgetItem(f"Lane {i + 1}")
            item.setCheckState(QtCore.Qt.Checked
                               if lane.visible else QtCore.Qt.Unchecked)
            self._list.addItem(item)
        self._selected_lane = None
        self._update_ui()

    def set_selection(self, lane: Optional[Lane], point: Optional[LanePoint]):
        self._selected_lane = lane
        self._selected_point = point
        if lane is not None and lane in self._lanes:
            row = self._lanes.index(lane)
            self._list.blockSignals(True)
            self._list.setCurrentRow(row)
            self._list.blockSignals(False)
        self._update_ui()

    def _update_ui(self):
        has_lane = self._selected_lane is not None
        has_point = self._selected_point is not None

        self._delete_btn.setEnabled(has_lane)
        self._copy_btn.setEnabled(has_lane)
        self._visible_cb.setEnabled(has_lane)
        self._color_btn.setEnabled(has_lane)
        self._x_spin.setEnabled(has_point)
        self._y_spin.setEnabled(has_point and not self._lock_y)
        self._valid_btn.setEnabled(has_point)

        if has_lane:
            self._visible_cb.setChecked(self._selected_lane.visible)

        # Block signals while updating values
        self._x_spin.blockSignals(True)
        self._y_spin.blockSignals(True)
        if has_point:
            self._x_spin.setValue(self._selected_point.x)
            self._y_spin.setValue(self._selected_point.y)
        else:
            self._x_spin.setValue(0)
            self._y_spin.setValue(0)
        self._x_spin.blockSignals(False)
        self._y_spin.blockSignals(False)

    def _on_lane_row_changed(self, row: int):
        if 0 <= row < len(self._lanes):
            self.laneSelected.emit(row)

    def _on_delete_lane(self):
        if self._selected_lane is not None and self._selected_lane in self._lanes:
            idx = self._lanes.index(self._selected_lane)
            self.deleteLaneRequested.emit(idx)

    def _on_copy_lane(self):
        if self._selected_lane is not None and self._selected_lane in self._lanes:
            idx = self._lanes.index(self._selected_lane)
            self.copyLaneRequested.emit(idx)

    def _on_visibility_changed(self, state: int):
        if self._selected_lane is not None and self._selected_lane in self._lanes:
            idx = self._lanes.index(self._selected_lane)
            visible = state == QtCore.Qt.Checked
            self.laneVisibilityChanged.emit(idx, visible)

    def _on_color_changed(self):
        if self._selected_lane is None:
            return
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self._selected_lane.color[2],
                         self._selected_lane.color[1],
                         self._selected_lane.color[0]), self)
        if color.isValid() and self._selected_lane in self._lanes:
            idx = self._lanes.index(self._selected_lane)
            self.laneColorChanged.emit(idx, color)

    def _on_point_value_changed(self):
        if self._selected_point is None:
            return
        x = self._x_spin.value()
        y = self._y_spin.value() if not self._lock_y else self._selected_point.y
        self.pointValueChanged.emit(self._selected_point, x, y)
