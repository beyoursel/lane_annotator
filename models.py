"""Data models for lane annotation."""

from typing import List, Tuple, Optional

from qt_imports import QtGui


class LanePoint:
    """A single control point of a lane."""

    def __init__(self, x: float, y: float, valid: bool = True):
        self.x = float(x)
        self.y = float(y)
        self.valid = bool(valid)

    def pos(self) -> Tuple[float, float]:
        return self.x, self.y

    def set_pos(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)

    def __repr__(self) -> str:
        return f"LanePoint({self.x:.3f}, {self.y:.3f}, valid={self.valid})"


class Lane:
    """A single lane, represented by an ordered list of control points."""

    COLORS = [
        (0, 255, 0),      # green
        (0, 0, 255),      # red (BGR)
        (255, 0, 0),      # blue (BGR)
        (0, 255, 255),    # yellow
        (255, 0, 255),    # magenta
        (255, 255, 0),    # cyan
        (128, 128, 255),  # pink-ish
        (128, 255, 128),  # light green
    ]

    def __init__(self,
                 points: Optional[List[LanePoint]] = None,
                 color: Optional[Tuple[int, int, int]] = None,
                 lane_id: int = 0):
        self.points: List[LanePoint] = list(points) if points else []
        self.color = color if color is not None else self.COLORS[lane_id %
                                                                 len(
                                                                     self.COLORS)]
        self.visible = True
        self.selected = False

    def clone(self) -> "Lane":
        return Lane(
            points=[LanePoint(p.x, p.y, p.valid) for p in self.points],
            color=self.color,
        )

    def valid_points(self) -> List[LanePoint]:
        return [p for p in self.points if p.valid]

    def __repr__(self) -> str:
        return f"Lane(points={len(self.points)}, color={self.color})"


class LaneImage:
    """An image with its lane annotations."""

    def __init__(self,
                 img_path: str,
                 label_path: str,
                 lanes: Optional[List[Lane]] = None):
        self.img_path = img_path
        self.label_path = label_path
        self.lanes: List[Lane] = list(lanes) if lanes else []
        self.pixmap: Optional[QtGui.QPixmap] = None
        self.dirty = False

    def clone_lanes(self) -> List[Lane]:
        return [lane.clone() for lane in self.lanes]

    def __repr__(self) -> str:
        return f"LaneImage({self.img_path}, lanes={len(self.lanes)})"
