#!/usr/bin/env python3

"""
Use ``img_bbox`` (``bbox``) from UNRAVEL to load an image (.czi, .nii.gz, or tif series) and save bounding boxes as txt files.

Usage:
------
    img_bbox -i path/img [-o path/outer_bbox.txt] [-c cluster_ID] [-v]
"""

from pathlib import Path
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.img_tools import find_bounding_box, label_IDs
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/img.czi, path/img.nii.gz, or path/tif_dir', action=SM, required=True)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-o', '--output', help='path to output dir. Default: bounding_boxes', action=SM)
    opts.add_argument('-ob', '--outer_bbox', help='path/outer_bbox.txt (bbox for voxels > 0)', action=SM)
    opts.add_argument('-c', '--cluster', help='Cluster intensity to get bbox and crop', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    img = load_3D_img(args.input, verbose=args.verbose)

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
        clusters = label_IDs(img, min_voxel_count=1)

    for cluster in clusters: 
        xmin, xmax, ymin, ymax, zmin, zmax = find_bounding_box(img, cluster_ID=cluster)
        output = output_path / Path(args.input.replace('.nii.gz', f'_cluster{cluster}_bbox.txt')).name
        with open(output, 'w') as f:
            f.write(f"{xmin}:{xmax}, {ymin}:{ymax}, {zmin}:{zmax}")

    verbose_end_msg()


if __name__ == '__main__':
    main()