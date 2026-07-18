"""QUndoCommand implementations for lane editing."""

from models import Lane, LaneImage, LanePoint
from qt_imports import QtWidgets


class MovePointCommand(QtWidgets.QUndoCommand):
    """Move a single control point to a new position."""

    def __init__(self, point: LanePoint, new_x: float, new_y: float,
                 lock_y: bool = False):
        super().__init__("Move point")
        self.point = point
        self.old_x = point.x
        self.old_y = point.y
        self.new_x = float(new_x)
        self.new_y = float(new_y)
        self.lock_y = lock_y

    def undo(self):
        self.point.x = self.old_x
        if not self.lock_y:
            self.point.y = self.old_y

    def redo(self):
        self.point.x = self.new_x
        if not self.lock_y:
            self.point.y = self.new_y


class AddPointCommand(QtWidgets.QUndoCommand):
    """Insert a control point into a lane."""

    def __init__(self, lane: Lane, index: int, point: LanePoint):
        super().__init__("Add point")
        self.lane = lane
        self.index = index
        self.point = point

    def undo(self):
        self.lane.points.pop(self.index)

    def redo(self):
        self.lane.points.insert(self.index, self.point)


class DeletePointCommand(QtWidgets.QUndoCommand):
    """Remove a control point from a lane."""

    def __init__(self, lane: Lane, index: int):
        super().__init__("Delete point")
        self.lane = lane
        self.index = index
        self.point = lane.points[index]

    def undo(self):
        self.lane.points.insert(self.index, self.point)

    def redo(self):
        self.lane.points.pop(self.index)


class AddLaneCommand(QtWidgets.QUndoCommand):
    """Add a new lane to the image."""

    def __init__(self, image: LaneImage, lane: Lane):
        super().__init__("Add lane")
        self.image = image
        self.lane = lane
        self.index = len(image.lanes)

    def undo(self):
        self.image.lanes.pop(self.index)

    def redo(self):
        self.image.lanes.insert(self.index, self.lane)


class DeleteLaneCommand(QtWidgets.QUndoCommand):
    """Remove a lane from the image."""

    def __init__(self, image: LaneImage, index: int):
        super().__init__("Delete lane")
        self.image = image
        self.index = index
        self.lane = image.lanes[index]

    def undo(self):
        self.image.lanes.insert(self.index, self.lane)

    def redo(self):
        self.image.lanes.pop(self.index)


class TogglePointValidityCommand(QtWidgets.QUndoCommand):
    """Toggle validity of a TuSimple control point."""

    def __init__(self, point: LanePoint):
        super().__init__("Toggle point validity")
        self.point = point

    def undo(self):
        self.point.valid = not self.point.valid

    def redo(self):
        self.point.valid = not self.point.valid
