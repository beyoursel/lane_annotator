#!/usr/bin/env python
"""Standalone entry point for lane annotator.

Run from inside the lane_annotator directory:
    python main.py --help
"""

import argparse
import os.path as osp
import sys

from app import run
from formats.culane import CULaneFormat
from formats.tusimple import TuSimpleFormat


def parse_args():
    parser = argparse.ArgumentParser(
        description='CLRNet interactive lane annotator')
    parser.add_argument('--format',
                        choices=['culane', 'tusimple'],
                        required=True,
                        help='Dataset format')
    parser.add_argument('--out',
                        required=True,
                        help='Output directory for saved annotations')

    # CULane arguments
    parser.add_argument('--list', help='Image list txt file')
    parser.add_argument('--img-root', help='Root directory of images')
    parser.add_argument('--gt-root',
                        help='Root directory of GT labels (default: img-root)')

    # Single image arguments
    parser.add_argument('--img', help='Single image path')
    parser.add_argument('--label',
                        help='Single label path (CULane only, optional)')

    # TuSimple arguments
    parser.add_argument('--json', help='TuSimple JSON label file')

    return parser.parse_args()


def collect_culane_paths(args):
    if args.img:
        img_paths = [args.img]
        img_root = args.img_root if args.img_root else osp.dirname(args.img)
        gt_root = args.gt_root if args.gt_root else img_root
        fmt = CULaneFormat(img_root, gt_root)
        return fmt, img_root, img_paths

    if not args.list or not args.img_root:
        raise ValueError(
            'CULane batch mode requires --list and --img-root')
    gt_root = args.gt_root if args.gt_root else args.img_root
    fmt = CULaneFormat(args.img_root, gt_root)
    img_paths = []
    with open(args.list, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rel = line.split()[0]
            if rel.startswith('/'):
                rel = rel[1:]
            img_paths.append(osp.join(args.img_root, rel))
    return fmt, args.img_root, img_paths


def collect_tusimple_paths(args):
    if not args.json or not args.img_root:
        raise ValueError('TuSimple mode requires --json and --img-root')
    fmt = TuSimpleFormat(args.img_root, args.json)

    if args.img:
        rel = osp.relpath(args.img, args.img_root)
        if rel not in fmt.records:
            raise ValueError(
                f'Image {args.img} not found in {args.json}')
        img_paths = [args.img]
    else:
        img_paths = [
            osp.join(args.img_root, raw_file)
            for raw_file in sorted(fmt.records.keys())
        ]
        if args.list:
            allowed = set()
            with open(args.list, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    allowed.add(line.split()[0].lstrip('/'))
            img_paths = [
                p for p in img_paths
                if osp.relpath(p, args.img_root) in allowed
            ]
    return fmt, args.img_root, img_paths


def main():
    args = parse_args()

    if args.format == 'culane':
        fmt, img_root, img_paths = collect_culane_paths(args)
        lock_y = False
    elif args.format == 'tusimple':
        fmt, img_root, img_paths = collect_tusimple_paths(args)
        lock_y = True
    else:
        raise ValueError(f'Unsupported format: {args.format}')

    # Filter out non-existent images
    existing_paths = [p for p in img_paths if osp.exists(p)]
    missing = len(img_paths) - len(existing_paths)
    if missing:
        print(f'Warning: {missing} images not found, skipping')
    img_paths = existing_paths

    if not img_paths:
        print('No images to annotate.')
        sys.exit(1)

    print(f'Loading {len(img_paths)} images from {img_root}')
    run(fmt, args.out, img_paths, lock_y=lock_y)


if __name__ == '__main__':
    main()
