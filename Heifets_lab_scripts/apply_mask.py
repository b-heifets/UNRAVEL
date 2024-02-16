#!/usr/bin/env python3

import argparse
import numpy as np
from argparse_utils import SuppressMetavar, SM
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from unravel_config import Configuration 
from unravel_img_io import load_3D_img, resolve_path, save_as_tifs, save_as_nii
from unravel_img_tools import cluster_IDs
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Loads image and mask. Zeros out voxels in image based on mask and direction args', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? folders', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern (sample??) for dirs to process. Else: use cwd', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='Image input path relative to ./ or ./sample??/', action=SM)
    parser.add_argument('-m', '--mask', help='Mask image path relative to ./ or ./sample??/. "sample??_" in arg replaced as needed.', action=SM)
    parser.add_argument('-d', '--direction', help='"greater" to zero out where mask > 0, "less" (default) to zero out where mask < 1', default='less', choices=['greater', 'less'], action=SM)
    parser.add_argument('-o', '--output', help='Image output path relative to ./ or ./sample??/', action=SM)
    parser.add_argument('-x', '--xyres', help='If output .nii.gz: x/y voxel size in microns. Default: get via metadata', default=None, type=float, action=SM)
    parser.add_argument('-z', '--zres', help='If output .nii.gz: z voxel size in microns. Default: get via metadata', default=None, type=float, action=SM)
    parser.add_argument('-v', '--verbose', help='sIncrease verbosity. Default: False', action='store_true', default=False)
    parser.epilog = f"""Example usage: apply_mask.py -m iba1_seg_ilastik_2/sample??_iba1_seg_ilastik_2.nii.gz -i iba1_rb20 -o iba1_rb20_clusters"""
    return parser.parse_args()


@print_func_name_args_times()
def apply_mask_to_ndarray(ndarray, mask_ndarray, mask_condition):
    """Zero out voxels in ndarray based on mask condition"""
    if mask_ndarray.shape != ndarray.shape:
        raise ValueError("Mask and input image must have the same shape")

    if mask_condition == 'greater':
        ndarray[mask_ndarray > 0] = 0
    elif mask_condition == 'less':
        ndarray[mask_ndarray < 1] = 0

    return ndarray


def main():

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample_path in samples:
            
            # Load image
            img = load_3D_img(resolve_path(sample_path, args.input), return_res=False)

            # Check if "sample??_" is in the mask path and replace it with the actual sample name
            if f"{args.pattern}_" in args.mask:
                dynamic_mask_path = args.mask.replace(f"{args.pattern}_", f"{sample_path.name}_")
            else:
                dynamic_mask_path = args.mask

            # Load mask with the updated or original path
            mask = load_3D_img(resolve_path(sample_path, dynamic_mask_path), return_res=False)

            # Apply mask to image
            masked_img = apply_mask_to_ndarray(img, mask, args.direction)

            # Define output path
            output = resolve_path(sample_path, args.output)

            # Save masked image
            if str(output).endswith('.nii.gz'):
                output.parent.mkdir(parents=True, exist_ok=True)
                save_as_nii(masked_img, output, args.xyres, args.zres, img.dtype)
            else:
                output.mkdir(parents=True, exist_ok=True)
                save_as_tifs(masked_img, output, "xyz")

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()