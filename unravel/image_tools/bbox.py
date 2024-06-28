#!/usr/bin/env python3

"""
Use ``img_bbox`` from UNRAVEL to load an image (.czi, .nii.gz, or tif series) and save bounding boxes as txt files.

Usage:
------
    img_bbox -i path/img -o path/bounding_boxes
"""

import argparse
from pathlib import Path
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.img_tools import find_bounding_box, cluster_IDs
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(description='', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.czi, path/img.nii.gz, or path/tif_dir', action=SM, required=True)
    parser.add_argument('-o', '--output', help='path to output dir. Default: bounding_boxes', action=SM)
    parser.add_argument('-ob', '--outer_bbox', help='path/outer_bbox.txt (bbox for voxels > 0)', action=SM)
    parser.add_argument('-c', '--cluster', help='Cluster intensity to get bbox and crop', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    img = load_3D_img(args.input)

    # Make output dir
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = Path(args.input).parent.resolve() / 'bounding_boxes'
    output_path.mkdir(parents=True, exist_ok=True)

    # Save outer bbox as txt
    if args.outer_bbox:
        xmin, xmax, ymin, ymax, zmin, zmax = find_bounding_box(img)
        output = output_path / Path(args.input.replace('.nii.gz', f'_outer_bbox.txt')).name
        with open(args.outer_bbox, 'w') as f:
            f.write(f"{xmin}:{xmax}, {ymin}:{ymax}, {zmin}:{zmax}")

    # Save cluster bboxes as txt
    if args.cluster:
        clusters = [int(args.cluster)]
    else:
        clusters = cluster_IDs(img, min_extent=1)

    for cluster in clusters: 
        xmin, xmax, ymin, ymax, zmin, zmax = find_bounding_box(img, cluster_ID=cluster)
        output = output_path / Path(args.input.replace('.nii.gz', f'_cluster{cluster}_bbox.txt')).name
        with open(output, 'w') as f:
            f.write(f"{xmin}:{xmax}, {ymin}:{ymax}, {zmin}:{zmax}")

    verbose_end_msg()


if __name__ == '__main__':
    main()