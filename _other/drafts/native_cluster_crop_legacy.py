#!/usr/bin/env python3

import argparse
from pathlib import Path
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_nii
from unravel.core.img_tools import crop
from unravel.core.utils import print_cmd_and_times, print_func_name_args_times, load_text_from_file


def parse_args():
    parser = argparse.ArgumentParser(description='Crop native image based on cluster bounding boxes', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help="Path to the image or it's dir", action=SM)
    parser.add_argument('-ob', '--outer_bbox', help='Path to the text file containing the outer bounding box (outer_bounds.txt)', action=SM)
    parser.add_argument('-ib', '--inner_bbox', help='Path to the text file containing the inner bounding box (bounding_box_sample??_cluster_*.txt)', action=SM)
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-cn', '--chann_name', help='Channel name. Default: ochann', default='ochann', action=SM)
    parser.add_argument('-x', '--xy_res', help='xy resolution in um', type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='z resolution in um', type=float, action=SM)
    parser.add_argument('-o', '--output', help='path/img.nii.gz.', default=None, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = "Bounding box text files are from native_clusters.py."
    return parser.parse_args()


@print_func_name_args_times()
def calculate_native_bbox(outer_bbox_text, inner_bbox_text):
    outer_bbox_text = load_text_from_file(args.outer_bbox)
    inner_bbox_text = load_text_from_file(args.inner_bbox)

    if outer_bbox_text is None or inner_bbox_text is None:
        return None

    outer_bbox = [list(map(int, dim.split(':'))) for dim in outer_bbox_text.split(', ')]
    inner_bbox = [list(map(int, dim.split(':'))) for dim in inner_bbox_text.split(', ')]
    
    native_bbox = [[outer_start + inner_start, outer_start + inner_end] 
                    for (outer_start, _), (inner_start, inner_end) in zip(outer_bbox, inner_bbox)]

    # Convert to string
    x_start, x_end = native_bbox[0]
    y_start, y_end = native_bbox[1]
    z_start, z_end = native_bbox[2]
    native_bbox = f"{x_start}:{x_end}, {y_start}:{y_end}, {z_start}:{z_end}"    

    return native_bbox

def main():
    args = parse_args()

    # Determine native bounding box for cropping
    native_bbox = calculate_native_bbox(args.outer_bbox, args.inner_bbox)

    if native_bbox is None: 
        print("    [red]Error calculating native bounding box[/]")
        return

    # Load image
    if args.xy_res is None or args.z_res is None:
        img, xy_res, z_res = load_3D_img(args.input, return_res=True)
    else:
        img = load_3D_img(args.input, return_res=True)
        xy_res, z_res = args.xy_res, args.z_res
    
    # Crop image
    cropped_img = crop(img, native_bbox)

    # Save cropped image
    dtype = img.dtype
    if args.output:
        save_as_nii(cropped_img, args.output, xy_res, z_res, data_type=dtype)
    else:
        output = Path(Path(args.bbox).resolve().parent.parent, f"{args.chann_name}_cropped")                     
        save_as_nii(cropped_img, output, xy_res, z_res, data_type=dtype)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()