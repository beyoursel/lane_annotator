#!/usr/bin/env python
"""Interactive image canvas for lane annotation."""

import math
from typing import Dict, Optional

from commands import (AddLaneCommand, AddPointCommand, DeleteLaneCommand,
                       DeletePointCommand, MovePointCommand)
from models import Lane, LaneImage, LanePoint
from qt_imports import QtCore, QtGui, QtWidgets, Signal
from utils import (bgr_to_qcolor, nearest_point_on_lane,
                    nearest_segment_on_lane, numpy_to_qimage,
                    project_point_to_segment)


class LanePathItem(QtWidgets.QGraphicsPathItem):
    """Custom path item storing the associated lane."""

    def __init__(self, lane: Lane, parent=None):
        super().__init__(parent)
        self.lane = lane


class PointItem(QtWidgets.QGraphicsEllipseItem):
    """Custom ellipse item storing the associated point and lane."""

    def __init__(self, point: LanePoint, lane: Lane, radius: float,
                 parent=None):
        super().__init__(-radius, -radius, radius * 2, radius * 2, parent)
        self.point = point
        self.lane = lane
        self.setZValue(10)


class ImageCanvas(QtWidgets.QGraphicsView):
    """Graphics view for displaying and editing lane annotations."""

    pointSelected = Signal(object, object)  # lane, point
    laneSelected = Signal(object)  # lane
    canvasChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QtGui.QPainter.Antialiasing)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)

        self._image: Optional[LaneImage] = None
        self._lock_y: bool = False
        self._pixmap_item: Optional[QtWidgets.QGraphicsPixmapItem] = None
        self._lane_items: Dict[Lane, LanePathItem] = {}
        self._point_items: Dict[LanePoint, PointItem] = {}
        self._selection_item: Optional[QtWidgets.QGraphicsEllipseItem] = None
        self._selected_lane: Optional[Lane] = None
        self._selected_point: Optional[LanePoint] = None
        self._drag_point: Optional[LanePoint] = None
        self._drag_lane: Optional[Lane] = None
        self._drag_start_pos = None
        self._panning: bool = False
        self._last_pan_pos: Optional[QtCore.QPoint] = None
        self._adding_lane: bool = False
        self._new_lane: Optional[Lane] = None
        self._point_radius: float = 5.0
        self._select_radius: float = 8.0
        self._drag_threshold: float = 5.0  # pixels

    def set_lock_y(self, lock: bool):
        """Lock y coordinate for editing (TuSimple mode)."""
        self._lock_y = lock

    def set_image(self, image: Optional[LaneImage]):
        """Set current image and refresh canvas."""
        self._scene.clear()
        self._lane_items.clear()
        self._point_items.clear()
        self._selection_item = None
        self._selected_lane = None
        self._selected_point = None
        self._drag_point = None
        self._drag_lane = None
        self._adding_lane = False
        self._new_lane = None
        self._image = image

        if image is None or image.pixmap is None:
            return

        self._pixmap_item = QtWidgets.QGraphicsPixmapItem(image.pixmap)
        self._scene.addItem(self._pixmap_item)
        rect = image.pixmap.rect()
        self._scene.setSceneRect(QtCore.QRectF(rect))

        for lane in image.lanes:
            self.create_lane_item(lane)
            for point in lane.points:
                self.create_point_item(point, lane)

        self.fitInView(self._scene.sceneRect(), QtCore.Qt.KeepAspectRatio)
        self.canvasChanged.emit()

    def refresh(self):
        """Refresh all graphics items from model data."""
        if self._image is None:
            return
        for lane in self._image.lanes:
            self.update_lane_path(lane)
            for point in lane.points:
                self.update_point_item(point)
        self._update_selection()

    def rebuild(self):
        """Rebuild all graphics items from model data.

        Use this after operations that add/remove points or lanes,
        because refresh() cannot create or destroy items.
        """
        if self._image is None:
            return
        # Remove existing lane and point items
        for item in list(self._lane_items.values()):
            self._scene.removeItem(item)
        for item in list(self._point_items.values()):
            self._scene.removeItem(item)
        self._lane_items.clear()
        self._point_items.clear()

        # Recreate items from model
        for lane in self._image.lanes:
            self.create_lane_item(lane)
            for point in lane.points:
                self.create_point_item(point, lane)

        # Restore selection if still valid
        if self._selected_lane is not None and self._selected_lane in self._image.lanes:
            if self._selected_point is not None and self._selected_point in self._point_items:
                pass
            else:
                self._selected_point = None
        else:
            self._selected_lane = None
            self._selected_point = None
        self._update_selection()

    def selected_lane(self) -> Optional[Lane]:
        return self._selected_lane

    def selected_point(self) -> Optional[LanePoint]:
        return self._selected_point

    def start_add_lane(self):
        """Enter mode for adding a new lane by clicking points."""
        self._adding_lane = True
        self._new_lane = Lane(lane_id=len(self._image.lanes) if self._image else 0)
        # Do not add to model yet; show temporary lane item
        self.create_lane_item(self._new_lane)

    def finish_add_lane(self):
        """Finish adding a new lane."""
        if not self._adding_lane or self._new_lane is None:
            return
        if len(self._new_lane.points) < 2:
            # Discard temporary lane
            self.remove_lane_items(self._new_lane)
        else:
            # Commit to model via undo command
            cmd = AddLaneCommand(self._image, self._new_lane)
            self._push_command(cmd)
            self.rebuild()
        self._adding_lane = False
        self._new_lane = None
        self.canvasChanged.emit()

    def cancel_add_lane(self):
        """Cancel adding a new lane."""
        if self._adding_lane and self._new_lane is not None:
            self.remove_lane_items(self._new_lane)
        self._adding_lane = False
        self._new_lane = None
        self.canvasChanged.emit()

    def delete_selected(self):
        """Delete selected point or lane."""
        if self._selected_point is not None and self._selected_lane is not None:
            index = self._selected_lane.points.index(self._selected_point)
            cmd = DeletePointCommand(self._selected_lane, index)
            self._push_command(cmd)
            self.rebuild()
            self.select_point(None, None)
        elif self._selected_lane is not None:
            index = self._image.lanes.index(self._selected_lane)
            cmd = DeleteLaneCommand(self._image, index)
            self._push_command(cmd)
            self.select_point(None, None)

    def set_selected_lane_color(self, color: QtGui.QColor):
        if self._selected_lane is not None:
            self._selected_lane.color = (color.blue(), color.green(), color.red())
            self.refresh()
            self.canvasChanged.emit()

    def toggle_selected_point_validity(self):
        """Toggle validity of selected point (TuSimple mode)."""
        if self._selected_point is None or self._selected_lane is None:
            return
        # Deferred import to avoid circular reference
        from commands import TogglePointValidityCommand
        cmd = TogglePointValidityCommand(self._selected_point)
        self._push_command(cmd)
        self.rebuild()

    def create_lane_item(self, lane: Lane):
        item = LanePathItem(lane)
        pen = QtGui.QPen(bgr_to_qcolor(lane.color), 3)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        item.setPen(pen)
        self._scene.addItem(item)
        self._lane_items[lane] = item
        self.update_lane_path(lane)

    def create_point_item(self, point: LanePoint, lane: Lane):
        item = PointItem(point, lane, self._point_radius)
        self._scene.addItem(item)
        self._point_items[point] = item
        self.update_point_item(point)

    def remove_lane_items(self, lane: Lane):
        if lane in self._lane_items:
            self._scene.removeItem(self._lane_items[lane])
            del self._lane_items[lane]
        for point in list(lane.points):
            if point in self._point_items:
                self._scene.removeItem(self._point_items[point])
                del self._point_items[point]

    def update_lane_path(self, lane: Lane):
        item = self._lane_items.get(lane)
        if item is None:
            return
        path = QtGui.QPainterPath()
        points = lane.valid_points()
        points.sort(key=lambda p: p.y)
        if len(points) >= 2:
            path.moveTo(points[0].x, points[0].y)
            for p in points[1:]:
                path.lineTo(p.x, p.y)
        item.setPath(path)
        # Highlight selected lane
        pen = item.pen()
        pen.setWidth(5 if lane.selected else 3)
        item.setPen(pen)

    def update_point_item(self, point: LanePoint):
        item = self._point_items.get(point)
        if item is None:
            return
        item.setPos(point.x, point.y)
        color = bgr_to_qcolor(item.lane.color)
        if point.valid:
            brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
            pen = QtGui.QPen(color, 2)
        else:
            brush = QtGui.QBrush(QtGui.QColor(128, 128, 128))
            pen = QtGui.QPen(QtGui.QColor(64, 64, 64), 2)
        item.setBrush(brush)
        item.setPen(pen)

    def _update_selection(self):
        if self._selected_point is not None:
            if self._selection_item is None:
                r = self._point_radius + 4
                self._selection_item = QtWidgets.QGraphicsEllipseItem(
                    -r, -r, r * 2, r * 2)
                self._selection_item.setPen(
                    QtGui.QPen(QtGui.QColor(255, 255, 0), 2))
                self._selection_item.setBrush(QtGui.QBrush())
                self._selection_item.setZValue(5)
                self._scene.addItem(self._selection_item)
            self._selection_item.setPos(self._selected_point.x,
                                        self._selected_point.y)
            self._selection_item.setVisible(True)
        elif self._selection_item is not None:
            self._selection_item.setVisible(False)

    def select_point(self, lane: Optional[Lane], point: Optional[LanePoint]):
        if self._selected_lane is not None:
            self._selected_lane.selected = False
        if self._selected_point is not None and self._selected_point in self._point_items:
            self.update_point_item(self._selected_point)

        self._selected_lane = lane
        self._selected_point = point

        if lane is not None:
            lane.selected = True
        if point is not None:
            self.update_point_item(point)

        self.refresh()
        self.pointSelected.emit(lane, point)
        self.laneSelected.emit(lane)

    def select_lane(self, lane: Lane):
        self.select_point(lane, None)

    def _image_pos(self, event: QtGui.QMouseEvent):
        """Convert mouse event to image coordinates."""
        return self.mapToScene(event.pos())

    def set_undo_stack(self, stack: QtWidgets.QUndoStack):
        """Set the undo stack used by this canvas."""
        self._undo_stack = stack

    def _push_command(self, cmd: QtWidgets.QUndoCommand):
        """Push a command to the undo stack and mark image dirty."""
        if hasattr(self, '_undo_stack') and self._undo_stack is not None:
            self._undo_stack.push(cmd)
        if self._image is not None:
            self._image.dirty = True
        self.canvasChanged.emit()

    def _item_at(self, scene_pos: QtCore.QPointF):
        """Return the nearest point or lane item at scene position."""
        x, y = scene_pos.x(), scene_pos.y()

        # Prefer control points
        best_lane, best_point = self._find_nearest_point(x, y)
        if best_point is not None:
            item = self._point_items.get(best_point)
            if item is not None:
                return item

        # Otherwise nearest lane segment
        best_lane, best_idx, best_foot = self._find_nearest_lane_segment(x, y)
        if best_lane is not None and best_idx >= 0:
            return self._lane_items.get(best_lane)

        return None

    def _find_nearest_point(self, x: float, y: float):
        """Find nearest control point across all lanes."""
        best_lane = None
        best_point = None
        best_dist = float('inf')
        for lane in (self._image.lanes if self._image else []):
            idx, dist = nearest_point_on_lane(x, y, lane)
            if idx >= 0 and dist < best_dist:
                best_dist = dist
                best_lane = lane
                best_point = lane.points[idx]
        if best_dist <= self._select_radius:
            return best_lane, best_point
        return None, None

    def _find_nearest_lane_segment(self, x: float, y: float):
        """Find nearest lane segment across all lanes."""
        best_lane = None
        best_idx = -1
        best_dist = float('inf')
        best_foot = (x, y)
        for lane in (self._image.lanes if self._image else []):
            idx, dist, foot = nearest_segment_on_lane(x, y, lane)
            if idx >= 0 and dist < best_dist:
                best_dist = dist
                best_idx = idx
                best_lane = lane
                best_foot = foot
        if best_dist <= self._select_radius * 1.5:
            return best_lane, best_idx, best_foot
        return None, -1, (x, y)

    def _insert_point(self, lane: Lane, after_index: int, x: float, y: float):
        """Insert a new point after after_index in lane."""
        new_point = LanePoint(x, y)
        insert_index = after_index + 1
        cmd = AddPointCommand(lane, insert_index, new_point)
        self._push_command(cmd)
        self.rebuild()
        self.select_point(lane, new_point)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if self._image is None:
            return

        scene_pos = self.mapToScene(event.pos())
        x, y = scene_pos.x(), scene_pos.y()

        if event.button() == QtCore.Qt.MiddleButton:
            self._panning = True
            self._last_pan_pos = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            return

        if event.button() != QtCore.Qt.LeftButton:
            super().mousePressEvent(event)
            return

        # Adding lane mode
        if self._adding_lane:
            new_point = LanePoint(x, y if not self._lock_y else 0)
            if self._lock_y:
                # For TuSimple, snap to nearest h_samples y
                points = self._new_lane.points if self._new_lane else []
                # Use selected lane's y values or default
                ys = sorted(set(p.y for lane in self._image.lanes
                                for p in lane.points))
                if ys:
                    new_point.y = min(ys, key=lambda vy: abs(vy - y))
                else:
                    new_point.y = y
            self._new_lane.points.append(new_point)
            self.create_point_item(new_point, self._new_lane)
            self.refresh()
            return

        modifiers = event.modifiers()
        item = self._item_at(scene_pos)

        if isinstance(item, PointItem):
            self.select_point(item.lane, item.point)
            self._drag_point = item.point
            self._drag_lane = item.lane
            self._drag_start_pos = (item.point.x, item.point.y)
            return

        if modifiers & QtCore.Qt.ShiftModifier:
            # Insert point on nearest segment
            lane, idx, foot = self._find_nearest_lane_segment(x, y)
            if lane is not None and idx >= 0:
                fx, fy = foot
                if self._lock_y:
                    fy = lane.points[idx].y
                self._insert_point(lane, idx, fx, fy)
                return

        if isinstance(item, LanePathItem):
            self.select_lane(item.lane)
            return

        # Click on empty area: deselect
        self.select_point(None, None)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self._panning:
            delta = event.pos() - self._last_pan_pos
            self._last_pan_pos = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y())
            return

        if self._drag_point is not None and self._drag_lane is not None:
            scene_pos = self.mapToScene(event.pos())
            x = scene_pos.x()
            y = self._drag_point.y if self._lock_y else scene_pos.y()
            old_x, old_y = self._drag_start_pos
            dx = x - old_x
            dy = 0.0 if self._lock_y else (y - old_y)
            # Only update position after exceeding the drag threshold.
            # This prevents tiny jitters from moving the point immediately.
            if math.hypot(dx, dy) > self._drag_threshold:
                self._drag_point.x = old_x + dx
                self._drag_point.y = old_y + dy
                self.update_point_item(self._drag_point)
                self.update_lane_path(self._drag_lane)
                self._update_selection()
            return

        # Update status bar with cursor position
        scene_pos = self.mapToScene(event.pos())
        # Could emit a signal here if needed
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MiddleButton:
            self._panning = False
            self._last_pan_pos = None
            self.unsetCursor()
            return

        if event.button() == QtCore.Qt.LeftButton and self._drag_point is not None:
            scene_pos = self.mapToScene(event.pos())
            new_x = scene_pos.x()
            new_y = self._drag_point.y if self._lock_y else scene_pos.y()
            old_x, old_y = self._drag_start_pos

            # Compute actual displacement in image coordinates
            dx = new_x - old_x
            dy = 0.0 if self._lock_y else (new_y - old_y)
            distance = math.hypot(dx, dy)

            # Restore original position first
            self._drag_point.x = old_x
            if not self._lock_y:
                self._drag_point.y = old_y

            if distance > self._drag_threshold:
                # Commit the move
                cmd = MovePointCommand(self._drag_point, new_x, new_y,
                                       lock_y=self._lock_y)
                self._push_command(cmd)
            else:
                # Treat as a click, ignore tiny jitter
                pass

            self.rebuild()
            self._drag_point = None
            self._drag_lane = None
            self._drag_start_pos = None
            return

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent):
        delta = event.angleDelta().y()
        zoom_factor = 1.15 if delta > 0 else 1.0 / 1.15
        self.scale(zoom_factor, zoom_factor)

    def fit_in_view(self):
        """Fit the entire scene into view."""
        if self._pixmap_item is not None:
            self.fitInView(self._pixmap_item, QtCore.Qt.KeepAspectRatio)

    def zoom_in(self):
        self.scale(1.2, 1.2)

    def zoom_out(self):
        self.scale(1.0 / 1.2, 1.0 / 1.2)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == QtCore.Qt.Key_Delete:
            self.delete_selected()
            return
        if event.key() == QtCore.Qt.Key_Escape:
            if self._adding_lane:
                self.cancel_add_lane()
            else:
                self.select_point(None, None)
            return
        if event.key() == QtCore.Qt.Key_Return or event.key() == QtCore.Qt.Key_Enter:
            if self._adding_lane:
                self.finish_add_lane()
            return
        super().keyPressEvent(event)
