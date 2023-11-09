#!/usr/bin/env python3

import argparse
import numpy as np
from rich import print
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_tools import load_3D_img
from unravel_utils import print_cmd_and_times, print_func_name_args_times

def parse_args():
    parser = argparse.ArgumentParser(description='Load spatial subset of .nii.gz')
    parser.add_argument('-i', '--input', help='Path to the NIFTI image (e.g., path/img.nii.gz)', metavar='')
    parser.add_argument('-ob', '--outer_bbox', help='Path to the text file containing the outer bounding box (outer_bounds.txt)', metavar='')
    parser.add_argument('-ib', '--inner_bbox', help='Path to the text file containing the inner bounding box (bounding_box_sample??_cluster_*.txt)', metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = "Bounding box text files are from native_clusters.py."
    return parser.parse_args()

@print_func_name_args_times()
def load_text_from_file(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except Exception as e:
        print(f"[red]Error reading file: {e}[/]")
        return None

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
    
    return native_bbox

def bbox_string_to_slices(bbox_string):
    slices = []
    for dim in bbox_string.split(", "):
        start, end = map(int, dim.split(":"))
        slices.append(slice(start, end))
    return tuple(slices)

def bbox_to_slice(bbox):
    return tuple(slice(start, end) for start, end in bbox)

def main():
    args = parse_args()

    native_bbox = calculate_native_bbox(outer_bbox_text, inner_bbox_text)

    if native_bbox is None: 
        return

    # native_bbox = get_native_bbox(args.outer_bbox, args.inner_bbox)


    print(f"native_bbox: {native_bbox}")

    # img, _, _ = load_3D_img(args.input)

    # img_cropped = img[bbox_string_to_slices(native_bbox)]

    # print(f"{img.shape=}")

    # bbox_slice = bbox_to_slice(native_bbox)

    # img = load_nifti_image(args.input)
    # if img is not None:
    #     img_cropped = img[bbox_slice]
    #     print(f"Cropped image shape: {img_cropped.shape}")


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()