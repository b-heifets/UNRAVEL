#!/usr/bin/env python3

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, load_image_metadata_from_txt, save_as_nii, load_nii_subset
from unravel.core.img_tools import crop
from unravel.core.utils import print_cmd_and_times, print_func_name_args_times, load_text_from_file


def parse_args():
    parser = argparse.ArgumentParser(description='Crop native image based on cluster bounding boxes', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help="Path to the image or it's dir", action=SM)
    parser.add_argument('-ob', '--outer_bbox', help='Path to the text file containing the outer bounding box (outer_bounds.txt)', action=SM)
    parser.add_argument('-ib', '--inner_bbox', help='Path to the text file containing the inner bounding box (bounding_box_sample??_cluster_*.txt)', action=SM)
    parser.add_argument('-s', '--sample', help='Sample number. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-c', '--cluster_ID', help='Cluster ID. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-cn', '--chann_name', help='Channel name. Default: ochann', default='ochann', action=SM)
    parser.add_argument('-x', '--xy_res', help='xy resolution in um', type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='z resolution in um', type=float, action=SM)
    parser.add_argument('-o', '--output', help='path/img.nii.gz.', default=None, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = "Bounding box text files are from native_clusters.py."
    return parser.parse_args()


@print_func_name_args_times()
def calculate_native_bbox(outer_bbox_text, cluster_data_csv, sample, cluster_ID):
    """Calculate native bounding box for cropping. Return: xmin, xmax, ymin, ymax, zmin, zmax"""
    outer_bbox_text = load_text_from_file(outer_bbox_text)

    cluster_data_df = pd.read_csv(args.inner_bbox) # Columns: sample, cluster_ID, _, _, _, xmin, xmax, ymin, ymax, zmin, zmax
    
    if outer_bbox_text is None or cluster_data_df is None:
        return None

    outer_bbox = [list(map(int, dim.split(':'))) for dim in outer_bbox_text.split(', ')]
    inner_bbox = cluster_data_df[(cluster_data_df['sample'] == sample) & (cluster_data_df['cluster_ID'] == cluster_ID)].iloc[0, 5:11].values

    native_bbox = [[outer_start + inner_start, outer_start + inner_end] 
                    for (outer_start, _), (inner_start, inner_end) in zip(outer_bbox, inner_bbox)]

    xmin, xmax = native_bbox[0]
    ymin, ymax = native_bbox[1]
    zmin, zmax = native_bbox[2] 

    return xmin, xmax, ymin, ymax, zmin, zmax

def main():
    args = parse_args()

    # Determine native bounding box for cropping
    xmin, xmax, ymin, ymax, zmin, zmax = calculate_native_bbox(args.outer_bbox, args.inner_bbox, args.sample, args.cluster_ID)

    if xmin is None or xmax is None or ymin is None or ymax is None or zmin is None or zmax is None: 
        print("    [red]Error calculating native bounding box[/]")
        return

    # Load image
    if str(args.input).endswith('.nii.gz'):
        img = load_nii_subset(args.input, xmin, xmax, ymin, ymax, zmin, zmax)
    else:
        img = load_3D_img(args.input, return_res=True)
        
    # Load image metadata from .txt
    xy_res, z_res, _, _, _ = load_image_metadata_from_txt(args.metadata)
    if xy_res is None or z_res is None: 
        print("    [red bold]./sample??/parameters/metadata.txt missing. cd to sample?? dir and run: metadata.py")

    # Save cropped image
    dtype = img.dtype
    if args.output:
        save_as_nii(img, args.output, xy_res, z_res, data_type=dtype)
    else:
        output = Path(Path(args.bbox).resolve().parent.parent, f"{args.chann_name}_cropped")                     
        save_as_nii(img, output, xy_res, z_res, data_type=dtype)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()