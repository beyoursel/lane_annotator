"""CULane dataset format adapter."""

import os
import os.path as osp
from typing import List, Tuple

import cv2
import numpy as np

from models import Lane, LanePoint
from formats.base import BaseFormat
from utils import draw_lanes_on_image


class CULaneFormat(BaseFormat):
    """CULane .lines.txt format.

    Each line in the label file represents one lane as alternating x y values.
    Negative coordinates indicate invalid points.
    """

    def __init__(self, img_root: str, gt_root: str):
        super().__init__(img_root)
        self.gt_root = gt_root

    def _label_path(self, img_path: str) -> str:
        rel = osp.relpath(img_path, self.img_root)
        return osp.join(self.gt_root, rel[:-3] + 'lines.txt')

    def load(self, img_path: str) -> Tuple[np.ndarray, List[Lane]]:
        img = cv2.imread(img_path)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {img_path}")

        label_path = self._label_path(img_path)
        lanes = []
        if osp.exists(label_path):
            with open(label_path, 'r') as f:
                for line in f:
                    nums = list(map(float, line.strip().split()))
                    points = [
                        LanePoint(nums[i], nums[i + 1])
                        for i in range(0, len(nums), 2)
                        if nums[i] >= 0 and nums[i + 1] >= 0
                    ]
                    points = list({(p.x, p.y): p for p in points}.values())
                    points.sort(key=lambda p: p.y, reverse=True)
                    if len(points) >= 2:
                        lanes.append(Lane(points=points))
        return img, lanes

    def save(self, img_path: str, lanes: List[Lane], out_root: str):
        rel = osp.relpath(img_path, self.img_root)
        out_label_path = osp.join(out_root, rel[:-3] + 'lines.txt')
        os.makedirs(osp.dirname(out_label_path), exist_ok=True)

        lines = []
        for lane in lanes:
            points = [p for p in lane.points if p.valid and p.x >= 0 and p.y >= 0]
            points.sort(key=lambda p: p.y, reverse=True)
            if len(points) < 2:
                continue
            line = ' '.join(f"{p.x:.3f} {p.y:.3f}" for p in points)
            lines.append(line)

        with open(out_label_path, 'w') as f:
            f.write('\n'.join(lines))
            if lines:
                f.write('\n')

        # Save visualization image
        self._save_visualization(img_path, lanes, out_root)

    def _save_visualization(self, img_path: str, lanes: List[Lane], out_root: str):
        """Draw lanes on the image and save to out_root/visualization/."""
        img = cv2.imread(img_path)
        if img is None:
            return
        vis = draw_lanes_on_image(img, lanes)
        rel = osp.relpath(img_path, self.img_root)
        vis_path = osp.join(out_root, 'visualization', rel)
        os.makedirs(osp.dirname(vis_path), exist_ok=True)
        cv2.imwrite(vis_path, vis)

    def label_exists(self, img_path: str) -> bool:
        return osp.exists(self._label_path(img_path))
