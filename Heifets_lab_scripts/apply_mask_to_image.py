#!/usr/bin/env python3

import argparse
import numpy as np
from argparse import RawTextHelpFormatter
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from unravel_config import Configuration 
from unravel_img_tools import load_3D_img, save_as_tifs, save_as_nii
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Loads image and mask. Zeros out voxels in image based on mask and direction args', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, metavar='')
    parser.add_argument('-i', '--input', help='Image input path relative to ./ or ./sample??/', metavar='')
    parser.add_argument('-m', '--mask', help='Mask image path relative to ./ or ./sample??/. "sample??_" in arg replaced as needed.', metavar='')
    parser.add_argument('-d, --direction', help='"greater" to zero out where mask > 0, "less" (default) to zero out where mask < 0', default='less', choices=['greater', 'less'], metavar='')
    parser.add_argument('-o', '--output', help='Image output path relative to ./ or ./sample??/', metavar='')
    parser.add_argument('-x', '--xyres', help='If output .nii.gz: x/y voxel size in microns. Default: get via metadata', default=None, type=float, metavar='')
    parser.add_argument('-z', '--zres', help='If output .nii.gz: z voxel size in microns. Default: get via metadata', default=None, type=float, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = f"""Example usage: apply_mask_to_image.py -m iba1_seg_ilastik_2/sample??_iba1_seg_ilastik_2.nii.gz -i iba1_rb20 -o iba1_rb20_clusters"""
    return parser.parse_args()


@print_func_name_args_times()
def apply_mask_to_ndarray(ndarray, mask_ndarray, mask_condition):
    """Zero out voxels in ndarray based on mask condition"""
    if mask_ndarray.shape != ndarray.shape:
        raise ValueError("Mask and input image must have the same shape")

    if mask_condition == 'greater':
        ndarray[mask_ndarray > 0] = 0
    elif mask_condition == 'less':
        ndarray[mask_ndarray < 0] = 0

    return ndarray


def main():
    samples = get_samples(args.dirs, args.pattern)

    if samples == ['.']:
        samples[0] = Path.cwd().name
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            # Resolve relative paths
            cwd = Path(".").resolve()
            sample_path = Path(sample).resolve() if sample != cwd.name else cwd
            
            # Load image
            img = load_3D_img(Path(sample_path, args.input).resolve(), return_res=False)

            # Check if "sample??_" is in the mask path and replace it with the actual sample name
            if f"{args.pattern}_" in args.mask:
                dynamic_mask_path = args.mask.replace(f"{args.pattern}_", f"{sample}_")
            else:
                dynamic_mask_path = args.mask

            # Load mask with the updated or original path
            mask = load_3D_img(Path(sample_path, dynamic_mask_path).resolve(), return_res=False)

            # Apply mask to image
            masked_img = apply_mask_to_ndarray(img, mask, args.direction)

            # Define output path
            output = Path(sample_path, args.output).resolve()

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