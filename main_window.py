#!/usr/bin/env python
"""Main window for lane annotation tool."""

import os
import os.path as osp
from typing import List, Optional

from commands import AddLaneCommand, DeleteLaneCommand, MovePointCommand
from formats.base import BaseFormat
from image_canvas import ImageCanvas
from models import Lane, LaneImage, LanePoint
from qt_imports import QtCore, QtGui, QtWidgets
from side_panel import ImageListPanel, LaneListPanel
from utils import bgr_to_qcolor, numpy_to_qimage


class MainWindow(QtWidgets.QMainWindow):
    """Main application window."""

    def __init__(self,
                 fmt: BaseFormat,
                 out_root: str,
                 img_paths: List[str],
                 lock_y: bool = False,
                 parent=None):
        super().__init__(parent)
        self._format = fmt
        self._out_root = out_root
        self._img_paths = img_paths
        self._lock_y = lock_y
        self._images: List[LaneImage] = []
        self._current_index: int = -1
        self._undo_stack = QtWidgets.QUndoStack(self)

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()

        self._load_dataset()
        if self._images:
            self._load_image(0)

    def _setup_ui(self):
        self.setWindowTitle("CLRNet Lane Annotator")
        self.resize(1400, 900)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self._splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_layout.addWidget(self._splitter)

        # Left: image list
        self._image_panel = ImageListPanel()
        self._splitter.addWidget(self._image_panel)

        # Center: canvas
        self._canvas = ImageCanvas()
        self._canvas.set_lock_y(self._lock_y)
        self._canvas.set_undo_stack(self._undo_stack)
        self._splitter.addWidget(self._canvas)

        # Right: lane list
        self._lane_panel = LaneListPanel()
        self._lane_panel.set_lock_y(self._lock_y)
        self._splitter.addWidget(self._lane_panel)

        self._splitter.setSizes([250, 900, 250])

    def _setup_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        file_menu.addAction(
            "&Save Current", self._save_current, QtGui.QKeySequence("Ctrl+S"))
        file_menu.addAction("Save &All", self._save_all,
                            QtGui.QKeySequence("Ctrl+Shift+S"))
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close)

        edit_menu = menubar.addMenu("&Edit")
        undo_action = self._undo_stack.createUndoAction(self, "&Undo")
        undo_action.setShortcut(QtGui.QKeySequence("Ctrl+Z"))
        edit_menu.addAction(undo_action)
        redo_action = self._undo_stack.createRedoAction(self, "&Redo")
        redo_action.setShortcut(QtGui.QKeySequence("Ctrl+Y"))
        edit_menu.addAction(redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction("&Add Lane", self._on_add_lane,
                            QtGui.QKeySequence("A"))
        edit_menu.addAction("&Delete", self._canvas.delete_selected,
                            QtGui.QKeySequence("Delete"))

        view_menu = menubar.addMenu("&View")
        view_menu.addAction("Fit in View", self._canvas.fit_in_view,
                            QtGui.QKeySequence("F"))
        view_menu.addAction("Zoom In", self._canvas.zoom_in,
                            QtGui.QKeySequence("Ctrl++"))
        view_menu.addAction("Zoom Out", self._canvas.zoom_out,
                            QtGui.QKeySequence("Ctrl+-"))

    def _setup_toolbar(self):
        toolbar = self.addToolBar("Main")
        toolbar.addAction("Save", self._save_current)
        toolbar.addAction("Save All", self._save_all)
        toolbar.addSeparator()
        toolbar.addAction("Prev", self._prev_image)
        toolbar.addAction("Next", self._next_image)
        toolbar.addSeparator()
        toolbar.addAction("Add Lane", self._on_add_lane)
        toolbar.addAction("Delete", self._canvas.delete_selected)
        toolbar.addSeparator()
        toolbar.addAction("Fit", self._canvas.fit_in_view)
        toolbar.addAction("Zoom In", self._canvas.zoom_in)
        toolbar.addAction("Zoom Out", self._canvas.zoom_out)

    def _setup_statusbar(self):
        self._status_label = QtWidgets.QLabel("Ready")
        self._coord_label = QtWidgets.QLabel("")
        self.statusBar().addWidget(self._status_label, 1)
        self.statusBar().addWidget(self._coord_label)

    def _connect_signals(self):
        # Image navigation
        self._image_panel.imageSelected.connect(self._on_image_selected)

        # Canvas -> panels
        self._canvas.pointSelected.connect(self._lane_panel.set_selection)
        self._canvas.laneSelected.connect(self._on_lane_selected)
        self._canvas.canvasChanged.connect(self._on_canvas_changed)

        # Lane panel -> actions
        self._lane_panel.laneSelected.connect(self._select_lane_by_index)
        self._lane_panel.addLaneRequested.connect(self._on_add_lane)
        self._lane_panel.deleteLaneRequested.connect(self._on_delete_lane)
        self._lane_panel.copyLaneRequested.connect(self._on_copy_lane)
        self._lane_panel.laneVisibilityChanged.connect(
            self._on_lane_visibility)
        self._lane_panel.laneColorChanged.connect(self._on_lane_color)
        self._lane_panel.pointValueChanged.connect(self._on_point_value_changed)
        self._lane_panel.toggleValidityRequested.connect(
            self._canvas.toggle_selected_point_validity)

        # Undo stack
        self._undo_stack.indexChanged.connect(self._on_undo_index_changed)

    def _load_dataset(self):
        """Load all images and annotations."""
        self._images = []
        for path in self._img_paths:
            try:
                img, lanes = self._format.load(path)
                lane_img = LaneImage(img_path=path,
                                     label_path=path,
                                     lanes=lanes)
                lane_img.pixmap = QtGui.QPixmap(
                    numpy_to_qimage(img))
                self._images.append(lane_img)
            except Exception as e:
                print(f"Failed to load {path}: {e}")
        self._image_panel.set_images(self._images)
        self._status_label.setText(
            f"Loaded {len(self._images)} images")

    def _load_image(self, index: int):
        """Switch to image at index."""
        if index < 0 or index >= len(self._images):
            return
        self._current_index = index
        self._image_panel.set_current_index(index)
        image = self._images[index]
        self._canvas.set_image(image)
        self._lane_panel.set_lanes(image.lanes)
        self._undo_stack.clear()
        self._undo_stack.setClean()
        self._status_label.setText(
            f"[{index + 1}/{len(self._images)}] {image.img_path}")
        self._update_window_title()

    def _update_window_title(self):
        title = "CLRNet Lane Annotator"
        if self._current_index >= 0:
            img = self._images[self._current_index]
            dirty = "* " if img.dirty else ""
            title = f"{dirty}[{self._current_index + 1}/{len(self._images)}] {osp.basename(img.img_path)} - CLRNet Lane Annotator"
        self.setWindowTitle(title)

    def _on_image_selected(self, index: int):
        if index == self._current_index:
            return
        if not self._maybe_save_current():
            # User cancelled, restore selection
            self._image_panel.set_current_index(self._current_index)
            return
        self._load_image(index)

    def _maybe_save_current(self) -> bool:
        """Prompt to save current image if dirty.

        Returns False if user cancelled the operation.
        """
        if self._current_index < 0:
            return True
        image = self._images[self._current_index]
        if not image.dirty:
            return True

        reply = QtWidgets.QMessageBox.question(
            self, "Unsaved Changes",
            f"Save changes to {osp.basename(image.img_path)}?",
            QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard
            | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Save)

        if reply == QtWidgets.QMessageBox.Save:
            self._save_image(image)
            return True
        if reply == QtWidgets.QMessageBox.Discard:
            return True
        return False

    def _save_image(self, image: LaneImage):
        """Save a single image's lanes."""
        self._format.save(image.img_path, image.lanes, self._out_root)
        image.dirty = False
        self._image_panel.update_image_state(
            self._images.index(image))
        self._update_window_title()

    def _save_current(self):
        if self._current_index < 0:
            return
        self._save_image(self._images[self._current_index])
        self._status_label.setText("Saved current image")

    def _save_all(self):
        saved = 0
        for image in self._images:
            if image.dirty:
                self._save_image(image)
                saved += 1
        self._status_label.setText(f"Saved {saved} images")

    def _prev_image(self):
        if self._current_index > 0:
            self._on_image_selected(self._current_index - 1)

    def _next_image(self):
        if self._current_index < len(self._images) - 1:
            self._on_image_selected(self._current_index + 1)

    def _on_canvas_changed(self):
        if self._current_index >= 0:
            self._images[self._current_index].dirty = True
            self._image_panel.update_image_state(self._current_index)
            self._update_window_title()

    def _on_undo_index_changed(self):
        self._canvas.rebuild()
        self._lane_panel.set_selection(self._canvas.selected_lane(),
                                       self._canvas.selected_point())
        self._on_canvas_changed()

    def _on_lane_selected(self, lane: Optional[Lane]):
        self._lane_panel.set_selection(lane, None)

    def _select_lane_by_index(self, index: int):
        if 0 <= index < len(self._images[self._current_index].lanes):
            lane = self._images[self._current_index].lanes[index]
            self._canvas.select_lane(lane)

    def _on_add_lane(self):
        if self._current_index < 0:
            return
        self._canvas.start_add_lane()
        self._status_label.setText(
            "Adding lane: click points, Enter to finish, Esc to cancel")

    def _on_delete_lane(self, index: int):
        if self._current_index < 0:
            return
        image = self._images[self._current_index]
        if 0 <= index < len(image.lanes):
            cmd = DeleteLaneCommand(image, index)
            self._undo_stack.push(cmd)
            self._canvas.rebuild()
            self._canvas.select_point(None, None)
            self._lane_panel.set_lanes(image.lanes)
            self._on_canvas_changed()

    def _on_copy_lane(self, index: int):
        if self._current_index < 0:
            return
        image = self._images[self._current_index]
        if 0 <= index < len(image.lanes):
            src = image.lanes[index]
            new_lane = src.clone()
            new_lane.selected = False
            # Offset slightly so it's visible
            for p in new_lane.points:
                p.x += 20
                p.y += 20
            cmd = AddLaneCommand(image, new_lane)
            self._undo_stack.push(cmd)
            self._canvas.rebuild()
            self._lane_panel.set_lanes(image.lanes)
            self._canvas.select_lane(new_lane)
            self._on_canvas_changed()

    def _on_lane_visibility(self, index: int, visible: bool):
        if self._current_index < 0:
            return
        image = self._images[self._current_index]
        if 0 <= index < len(image.lanes):
            image.lanes[index].visible = visible
            self._canvas._lane_items[image.lanes[index]].setVisible(visible)
            for p in image.lanes[index].points:
                if p in self._canvas._point_items:
                    self._canvas._point_items[p].setVisible(visible)
            self._on_canvas_changed()

    def _on_lane_color(self, index: int, color: QtGui.QColor):
        if self._current_index < 0:
            return
        image = self._images[self._current_index]
        if 0 <= index < len(image.lanes):
            image.lanes[index].color = (color.blue(), color.green(), color.red())
            self._canvas.refresh()
            self._on_canvas_changed()

    def _on_point_value_changed(self, point, x: float, y: float):
        if point is None:
            return
        cmd = MovePointCommand(point, x, y, lock_y=self._lock_y)
        self._undo_stack.push(cmd)
        self._canvas.refresh()
        self._on_canvas_changed()

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """Handle global shortcuts for undo/redo."""
        if event.modifiers() == QtCore.Qt.ControlModifier:
            if event.key() == QtCore.Qt.Key_Z:
                self._undo_stack.undo()
                return
            if event.key() == QtCore.Qt.Key_Y:
                self._undo_stack.redo()
                return
        super().keyPressEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent):
        # Check for unsaved changes
        dirty = [img for img in self._images if img.dirty]
        if dirty:
            reply = QtWidgets.QMessageBox.question(
                self, "Unsaved Changes",
                f"{len(dirty)} images have unsaved changes. Save all before exiting?",
                QtWidgets.QMessageBox.SaveAll | QtWidgets.QMessageBox.Discard
                | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.SaveAll)
            if reply == QtWidgets.QMessageBox.SaveAll:
                self._save_all()
            elif reply == QtWidgets.QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()
