#!/usr/bin/env python3

import argparse
import numpy as np
from argparse_utils import SuppressMetavar, SM
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from prep_reg import prep_reg
from unravel_config import Configuration 
from unravel_img_io import load_3D_img, load_image_metadata_from_txt, resolve_path, save_as_tifs, save_as_nii, save_as_zarr
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Loads image and mask. Zeros out voxels in image based on mask and direction args', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? folders', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern (sample??) for dirs to process. Else: use cwd', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='Image input path relative to ./ or ./sample??/', required=True, action=SM)
    parser.add_argument('-mas', '--seg_mask', help='path/mask_to_apply.nii.gz (in tissue space)', required=True, action=SM)
    parser.add_argument('-m', '--mean', help='If provided, conditionally replace values w/ the mean intensity in the brain', action='store_true', default=False)
    parser.add_argument('-tmas', '--tissue_mask', help='rel_path/brain_mask.nii.gz. Default: reg_inputs/autofl_50um_brain_mask.nii.gz', default="reg_inputs/autofl_50um_brain_mask.nii.gz", action=SM)
    parser.add_argument('-di', '--direction', help='"greater" to zero out where mask > 0, "less" (default) to zero out where mask < 1', default='less', choices=['greater', 'less'], action=SM)
    parser.add_argument('-o', '--output', help='Image output path relative to ./ or ./sample??/', action=SM)
    parser.add_argument('-md', '--metadata', help='path/metadata.txt. Default: ./parameters/metadata.txt', default="./parameters/metadata.txt", action=SM)
    parser.add_argument('-r', '--reg_res', help='Resample input to this res in um for reg.py. Default: 50', default=50, type=int, action=SM)
    parser.add_argument('-mi', '--miracl', help="Include reorientation step to mimic MIRACL's tif to .nii.gz conversion", action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = f""" 
Example use cases:
    - Zero out voxels in image where mask > 0 (e.g., to exclude voxels representing artifacts):
        apply_mask.py -mas 6e10_seg_ilastik_2/sample??_6e10_seg_ilastik_2.nii.gz -i 6e10_rb20 -o 6e10_rb20_wo_artifacts -di greater -v
    - Zero out voxels in image where mask < 1 (e.g., to preserve signal from segmented microglia clusters):
        apply_mask.py -mas iba1_seg_ilastik_2/sample??_iba1_seg_ilastik_2.nii.gz -i iba1_rb20 -o iba1_rb20_clusters -v 
    - Replace voxels in image with the mean intensity in the brain where mask > 0:
        apply_mask.py -mas FOS_seg_ilastik/FOS_seg_ilastik_2.nii.gz -i FOS -o FOS_wo_halo.zarr -di greater -m -v 
"""
    return parser.parse_args()

@print_func_name_args_times()
def mean_intensity_in_brain(img, tissue_mask):
    """Z-score the image using the mask.
    
    Args:
        - img (str): the ndarray to be z-scored.
        - mask (str): the brain mask ndarray"""

    # Zero out voxels outside the mask
    masked_data = img * tissue_mask

    # Calculate mean for masked data
    masked_nonzero = masked_data[masked_data != 0] # Exclude zero voxels and flatten the array (1D)
    mean_intensity = masked_nonzero.mean()

    return mean_intensity    

@print_func_name_args_times()
def apply_mask_to_ndarray(ndarray, mask_ndarray, mask_condition, new_value=0):
    """Zero out voxels in ndarray based on mask condition"""
    if mask_ndarray.shape != ndarray.shape:
        raise ValueError("Mask and input image must have the same shape")

    if mask_condition == 'greater':
        ndarray[mask_ndarray > 0] = new_value
    elif mask_condition == 'less':
        ndarray[mask_ndarray < 1] = new_value

    return ndarray


def main():

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            # Resolve path to sample folder
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            # Define output
            output = resolve_path(sample_path, args.output, make_parents=True)
            if output.exists():
                print(f"\n\n    {output.name} already exists. Skipping.\n")
                continue
            
            # Load image
            img = load_3D_img(sample_path / args.input, return_res=False)

            # Load metadata
            metadata_path = sample_path / args.metadata
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            if xy_res is None:
                print("    [red1]./sample??/parameters/metadata.txt is missing. Generate w/ metadata.py")
                import sys ; sys.exit()

            # Resample to registration resolution
            img_resampled = prep_reg(img, xy_res, z_res, args.reg_res, int(1), args.miracl)

            # Load 50 um tissue mask and scale to full resolution
            tissue_mask_img = load_3D_img(sample_path / args.tissue_mask)

            # Calculate mean intensity in brain
            if args.mean:
                mean_intensity = mean_intensity_in_brain(img_resampled, tissue_mask_img)

            # Check if "sample??_" is in the mask path and replace it with the actual sample name
            if f"{args.pattern}_" in args.seg_mask:
                dynamic_mask_path = args.seg_mask.replace(f"{args.pattern}_", f"{sample_path.name}_")
            else:
                dynamic_mask_path = args.seg_mask

            # Load full res mask with the updated or original path
            mask = load_3D_img(sample_path / dynamic_mask_path, return_res=False)

            # Apply mask to image
            if args.mean:
                masked_img = apply_mask_to_ndarray(img, mask, args.direction, new_value=mean_intensity)
            else:
                masked_img = apply_mask_to_ndarray(img, mask, args.direction, new_value=0)

            # Save masked image
            
            output.parent.mkdir(parents=True, exist_ok=True)
            if str(output).endswith(".zarr"):
                save_as_zarr(masked_img, output)
            elif str(output).endswith('.nii.gz'):
                save_as_nii(masked_img, output, xy_res, z_res, img.dtype)
            else:
                output.mkdir(parents=True, exist_ok=True)
                save_as_tifs(masked_img, output, "xyz")

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()