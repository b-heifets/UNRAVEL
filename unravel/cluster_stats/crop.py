#!/usr/bin/env python3

"""
Use ``cluster_crop`` from UNRAVEL to load image, load bounding box, crop cluster, and save as .nii.gz.

Usage
-----
    cluster_crop -i path/img.nii.gz -b path/bbox.txt -o path/output_img.nii.gz -a -x $XY -z $Z -v
"""

import argparse
from rich.traceback import install
from rich import print

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_nii
from unravel.core.img_tools import find_bounding_box, cluster_IDs, crop
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, load_text_from_file


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.czi, path/img.nii.gz, or path/tif_dir', action=SM)
    parser.add_argument('-o', '--output', help='path/output_img.nii.gz', action=SM)
    parser.add_argument('-b', '--bbox', help='path/bbox.txt', action=SM)
    parser.add_argument('-c', '--cluster', help='Cluster intensity to get bbox and crop', action=SM)
    parser.add_argument('-a', '--all_clusters', help='Crop each cluster. Default: False', action='store_true', default=False)
    parser.add_argument('-x', '--xy_res', help='xy voxel size in microns for the raw data', type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='z voxel size in microns for the raw data', type=float, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def save_cropped_img(img_cropped, xy_res, z_res, args, cluster=None):
    if args.output:
        save_path = args.output
    elif args.bbox:
        save_path = args.input.replace('.nii.gz', f'_cropped.nii.gz')
    elif cluster is not None:
        save_path = args.input.replace('.nii.gz', f'_cluster{cluster}_cropped.nii.gz')
    else:
        print("    [red1]No output specified. Exiting.")
        exit()

    if max(img_cropped.flatten()) < 255:
        save_as_nii(img_cropped, save_path, xy_res, z_res, data_type='uint8')
    else:
        save_as_nii(img_cropped, save_path, xy_res, z_res, data_type='uint16')


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
   
    if args.xy_res is None or args.z_res is None:
        img, xy_res, z_res = load_3D_img(args.input, return_res=True)
    else:
        img = load_3D_img(args.input, return_res=True)
        xy_res, z_res = args.xy_res, args.z_res

    # Crop image
    if args.bbox:
        bbox = load_text_from_file(args.bbox)
        img_cropped = crop(img, bbox)
        save_cropped_img(img_cropped, xy_res, z_res, args)
    elif args.cluster:
        xmin, xmax, ymin, ymax, zmin, zmax = find_bounding_box(img, cluster_ID=args.cluster)
        bbox_str = f"{xmin}:{xmax}, {ymin}:{ymax}, {zmin}:{zmax}"
        img_cropped = crop(img, bbox_str)
        save_cropped_img(img_cropped, xy_res, z_res, args, cluster=args.cluster)
    elif args.all_clusters:
        clusters = cluster_IDs(img, min_extent=1, print_IDs=False, print_sizes=False)
        for cluster in clusters: 
            xmin, xmax, ymin, ymax, zmin, zmax = find_bounding_box(img, cluster_ID=cluster)
            bbox_str = f"{xmin}:{xmax}, {ymin}:{ymax}, {zmin}:{zmax}"
            img_cropped = crop(img, bbox_str)
            save_cropped_img(img_cropped, xy_res, z_res, args, cluster=cluster)
    else:
        print("    [red1]No bbox or cluster specified. Exiting.")
        exit()

    verbose_end_msg()


if __name__ == '__main__':
    main()