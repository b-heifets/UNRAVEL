#!/usr/bin/env python3

import argparse
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from unravel_config import Configuration 
from unravel_img_tools import load_3D_img, save_as_tifs, save_as_nii
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Loads image and mask. Zeros out voxels in image where voxels are > 0 in mask')
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, metavar='')
    parser.add_argument('-i', '--input', help='Image input path relative to ./ or ./sample??/', metavar='')
    parser.add_argument('-m', '--mask', help='Mask image path relative to ./ or ./sample??/', metavar='')
    parser.add_argument('-o', '--output', help='Image output path relative to ./ or ./sample??/', metavar='')
    parser.add_argument('-x', '--xyres', help='If output .nii.gz: x/y voxel size in microns. Default: get via metadata', default=None, type=float, metavar='')
    parser.add_argument('-z', '--zres', help='If output .nii.gz: z voxel size in microns. Default: get via metadata', default=None, type=float, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


@print_func_name_args_times()
def apply_mask_to_ndarray(ndarray, mask_ndarray):
    """Zero out voxels in ndarray where voxels are > 0 in mask_ndarray"""
    # Ensure mask and tif array are the same shape
    if mask_ndarray.shape != ndarray.shape:
        raise ValueError("Mask and input image must have the same shape")

    # Zero out voxels in tif array where mask is > 0 
    ndarray[mask_ndarray > 0 ] = 0

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

            # Load mask
            mask = load_3D_img(Path(sample_path, args.mask).resolve(), return_res=False)

            # Apply mask to image
            masked_img = apply_mask_to_ndarray(img, mask)

            # Define output path
            output = Path(sample_path, args.output).resolve()

            # Save masked image
            if output.endswith('.nii.gz'):
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