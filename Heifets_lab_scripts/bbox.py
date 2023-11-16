#!/usr/bin/env python3

import argparse
from argparse import RawTextHelpFormatter
from pathlib import Path
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_tools import load_3D_img, find_bounding_box, cluster_IDs
from unravel_utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Load image (.czi, .nii.gz, or tif series) and ', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-i', '--input', help='path/img.czi, path/img.nii.gz, or path/tif_dir', metavar='')
    parser.add_argument('-o', '--output', help='path to output dir. Default: bounding_boxes', metavar='')
    parser.add_argument('-ob', '--outer_bbox', help='path/outer_bbox.txt (bbox for voxels > 0)', metavar='')
    parser.add_argument('-c', '--cluster', help='Cluster intensity to get bbox and crop', metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()

def main():    

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

    

if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()