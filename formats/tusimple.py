"""TuSimple dataset format adapter."""

import json
import os
import os.path as osp
from typing import Dict, List, Tuple

import cv2
import numpy as np

from models import Lane, LanePoint
from formats.base import BaseFormat
from utils import draw_lanes_on_image


class TuSimpleFormat(BaseFormat):
    """TuSimple JSON Lines format.

    Each line is a JSON object with keys: raw_file, h_samples, lanes, run_time.
    h_samples are fixed y coordinates; lanes are lists of x values per lane.
    x == -2 indicates an invalid point.
    """

    def __init__(self, img_root: str, json_path: str):
        super().__init__(img_root)
        self.json_path = json_path
        self.records: Dict[str, dict] = {}
        self._load_json()

    def _load_json(self):
        if not osp.exists(self.json_path):
            return
        with open(self.json_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                self.records[record['raw_file']] = record

    def load(self, img_path: str) -> Tuple[np.ndarray, List[Lane]]:
        img = cv2.imread(img_path)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {img_path}")

        rel = osp.relpath(img_path, self.img_root)
        record = self.records.get(rel)
        lanes = []
        if record is not None:
            h_samples = record['h_samples']
            for lane_id, xs in enumerate(record['lanes']):
                points = [
                    LanePoint(float(x), float(y), valid=(x >= 0))
                    for x, y in zip(xs, h_samples)
                ]
                valid_points = [p for p in points if p.valid]
                if valid_points:
                    lanes.append(Lane(points=points, lane_id=lane_id))
        return img, lanes

    def save(self, img_path: str, lanes: List[Lane], out_root: str):
        rel = osp.relpath(img_path, self.img_root)
        record = self.records.get(rel)
        if record is None:
            # Create a minimal record if not present
            record = {
                'raw_file': rel,
                'h_samples': [],
                'lanes': [],
                'run_time': 0.0,
            }
            self.records[rel] = record

        h_samples = record.setdefault('h_samples', [])
        if not h_samples:
            # Fallback: infer from lanes or use empty
            h_samples = sorted(
                set(p.y for lane in lanes for p in lane.points))
            record['h_samples'] = h_samples

        out_lanes = []
        for lane in lanes:
            xs = []
            for y in h_samples:
                point = next((p for p in lane.points if abs(p.y - y) < 1e-3),
                             None)
                if point is not None and point.valid and point.x >= 0:
                    xs.append(int(round(point.x)))
                else:
                    xs.append(-2)
            out_lanes.append(xs)
        record['lanes'] = out_lanes

        os.makedirs(out_root, exist_ok=True)
        out_json_name = osp.basename(self.json_path)
        out_json_path = osp.join(out_root, out_json_name)
        with open(out_json_path, 'w') as f:
            for rec in self.records.values():
                f.write(json.dumps(rec, separators=(',', ':')) + '\n')

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
        rel = osp.relpath(img_path, self.img_root)
        return rel in self.records
