"""Utility functions for lane annotation."""

import math
from typing import List, Tuple

import cv2
import numpy as np

from models import Lane
from qt_imports import QtGui


def bgr_to_qcolor(bgr: Tuple[int, int, int]) -> QtGui.QColor:
    """Convert OpenCV BGR tuple to QColor."""
    return QtGui.QColor(bgr[2], bgr[1], bgr[0])


def qcolor_to_bgr(color: QtGui.QColor) -> Tuple[int, int, int]:
    """Convert QColor to OpenCV BGR tuple."""
    return (color.blue(), color.green(), color.red())


def numpy_to_qimage(img: np.ndarray) -> QtGui.QImage:
    """Convert BGR numpy image to QImage."""
    if img is None or img.size == 0:
        return QtGui.QImage()
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    height, width, channels = rgb.shape
    bytes_per_line = channels * width
    return QtGui.QImage(rgb.data, width, height, bytes_per_line,
                        QtGui.QImage.Format_RGB888).copy()


def draw_lanes_on_image(img: np.ndarray, lanes: List[Lane],
                        line_width: int = 3) -> np.ndarray:
    """Draw lanes on a BGR image and return the annotated image."""
    vis = img.copy()
    for lane in lanes:
        points = [
            p for p in lane.points if p.valid and p.x >= 0 and p.y >= 0
        ]
        if len(points) < 2:
            continue
        points.sort(key=lambda p: p.y, reverse=True)
        pts = [(int(p.x), int(p.y)) for p in points]
        for i in range(1, len(pts)):
            cv2.line(vis, pts[i - 1], pts[i], lane.color, thickness=line_width)
        # Draw control points
        for px, py in pts:
            cv2.circle(vis, (px, py), 4, (255, 255, 255), -1)
            cv2.circle(vis, (px, py), 4, lane.color, 2)
    return vis


def point_to_segment_distance(px: float, py: float, x1: float, y1: float,
                              x2: float, y2: float) -> float:
    """Return distance from point P to segment AB."""

    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0,
                      ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def project_point_to_segment(px: float, py: float, x1: float, y1: float,
                             x2: float, y2: float) -> Tuple[float, float]:
    """Return the foot of perpendicular from P to segment AB,
    clamped to the segment."""
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return x1, y1
    t = max(0.0, min(1.0,
                      ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return x1 + t * dx, y1 + t * dy


def nearest_point_on_lane(px: float, py: float, lane: Lane) -> Tuple[int, float]:
    """Find nearest control point on lane.

    Returns:
        index: index of nearest point, or -1 if no valid point.
        distance: distance to that point.
    """
    points = lane.valid_points()
    if not points:
        return -1, float('inf')
    best_idx = -1
    best_dist = float('inf')
    for i, p in enumerate(points):
        d = math.hypot(px - p.x, py - p.y)
        if d < best_dist:
            best_dist = d
            best_idx = i
    # Map back to original index
    if best_idx >= 0:
        original_idx = lane.points.index(points[best_idx])
        return original_idx, best_dist
    return -1, float('inf')


def nearest_segment_on_lane(px: float, py: float,
                            lane: Lane) -> Tuple[int, float, Tuple[float, float]]:
    """Find nearest segment on lane.

    Returns:
        index: index of the start point of the nearest segment.
        distance: distance to the segment.
        foot: projected point on the segment.
    """
    points = lane.valid_points()
    if len(points) < 2:
        return -1, float('inf'), (px, py)
    best_idx = -1
    best_dist = float('inf')
    best_foot = (px, py)
    for i in range(len(points) - 1):
        x1, y1 = points[i].pos()
        x2, y2 = points[i + 1].pos()
        d = point_to_segment_distance(px, py, x1, y1, x2, y2)
        if d < best_dist:
            best_dist = d
            best_idx = lane.points.index(points[i])
            best_foot = project_point_to_segment(px, py, x1, y1, x2, y2)
    return best_idx, best_dist, best_foot
