#!/usr/bin/env python3

""" 
Use ``vstats_apply_mask`` from UNRAVEL to zeros out voxels in image based on a mask and direction args.

Usage to zero out voxels in image where mask > 0 (e.g., to exclude voxels representing artifacts):
--------------------------------------------------------------------------------------------------
    vstats_apply_mask -mas 6e10_seg_ilastik_2/sample??_6e10_seg_ilastik_2.nii.gz -i 6e10_rb20 -o 6e10_rb20_wo_artifacts -di greater -v

Usage to zero out voxels in image where mask < 1 (e.g., to preserve signal from segmented microglia clusters):
--------------------------------------------------------------------------------------------------------------
    vstats_apply_mask -mas iba1_seg_ilastik_2/sample??_iba1_seg_ilastik_2.nii.gz -i iba1_rb20 -o iba1_rb20_clusters -v 

Usage to replace voxels in image with the mean intensity in the brain where mask > 0:
-------------------------------------------------------------------------------------
    vstats_apply_mask -mas FOS_seg_ilastik/FOS_seg_ilastik_2.nii.gz -i FOS -o FOS_wo_halo.zarr -di greater -m -v 

This version allows for dilatation of the full res seg_mask (slow, but precise)
"""

import argparse
import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy.ndimage import binary_dilation, zoom

from unravel.register.reg_prep import reg_prep
from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.img_io import load_3D_img, load_image_metadata_from_txt, resolve_path, save_as_tifs, save_as_nii, save_as_zarr
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? folders', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern (sample??) for dirs to process. Else: use cwd', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='Image input path relative to ./ or ./sample??/', required=True, action=SM)
    parser.add_argument('-mas', '--seg_mask', help='rel_path/mask_to_apply.nii.gz (in full res tissue space)', required=True, action=SM)
    parser.add_argument("-dil", "--dilation", help="Number of dilation iterations to perform on seg_mask. Default: 0", default=0, type=int, action=SM)
    parser.add_argument('-m', '--mean', help='If provided, conditionally replace values w/ the mean intensity in the brain', action='store_true', default=False)
    parser.add_argument('-tmas', '--tissue_mask', help='For the mean itensity. rel_path/brain_mask.nii.gz. Default: reg_inputs/autofl_50um_brain_mask.nii.gz', default="reg_inputs/autofl_50um_brain_mask.nii.gz", action=SM)
    parser.add_argument('-omas', '--other_mask', help='For restricting application of -mas. E.g., reg_inputs/autofl_50um_brain_mask_outline.nii.gz (from ./UNRAVEL/_other/uncommon_scripts/brain_mask_outline.py)', default=None, action=SM)
    parser.add_argument('-di', '--direction', help='"greater" to zero out where mask > 0, "less" (default) to zero out where mask < 1', default='less', choices=['greater', 'less'], action=SM)
    parser.add_argument('-o', '--output', help='Image output path relative to ./ or ./sample??/', action=SM)
    parser.add_argument('-md', '--metadata', help='path/metadata.txt. Default: ./parameters/metadata.txt', default="./parameters/metadata.txt", action=SM)
    parser.add_argument('-r', '--reg_res', help='Resample input to this res in microns for ``reg``. Default: 50', default=50, type=int, action=SM)
    parser.add_argument('-mi', '--miracl', help="Include reorientation step to mimic MIRACL's tif to .nii.gz conversion", action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@print_func_name_args_times()
def load_mask(mask_path):
    """Load .nii.gz and return to an ndarray with a binary dtype"""
    mask_nii = nib.load(mask_path)
    return np.asanyarray(mask_nii.dataobj, dtype=np.bool_).squeeze()

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
def dilate_mask(mask, iterations):
    """Dilate the given mask (ndarray) by a specified number of iterations."""
    dilated_mask = binary_dilation(mask, iterations=iterations)
    return dilated_mask

@print_func_name_args_times()
def scale_bool_to_full_res(ndarray, full_res_dims):
    """Scale ndarray to match x, y, z dimensions provided. Uses nearest-neighbor interpolation by default to preserve a binary data type."""
    zoom_factors = (full_res_dims[0] / ndarray.shape[0], full_res_dims[1] / ndarray.shape[1], full_res_dims[2] / ndarray.shape[2])
    return zoom(ndarray, zoom_factors, order=0).astype(np.bool_)

@print_func_name_args_times()
def apply_mask_to_ndarray(ndarray, mask_ndarray, other_mask=None, mask_condition='less', new_value=0):
    """Replace voxels in the ndarray with a new_value based on mask conditions. Optionally use a second mask to restrict application spatially."""
    if mask_ndarray.shape != ndarray.shape:
        raise ValueError("Primary mask and input image must have the same shape")
    
    if other_mask is not None and other_mask.shape != ndarray.shape:
        raise ValueError("Other mask and input image must have the same shape")
    
    # Combine masks if other_mask is provided, using logical AND (both masks need to be True)
    if other_mask is not None:
        mask_ndarray = np.logical_and(mask_ndarray, other_mask)  # Both masks must be True to remain True
    
    # Apply the combined mask to the ndarray
    if mask_condition == 'greater':
        ndarray[mask_ndarray] = new_value  # mask_ndarray already represents where mask is True
    elif mask_condition == 'less':
        ndarray[~mask_ndarray] = new_value  # Use logical NOT to flip True/False

    return ndarray


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

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
                print("    [red1]./sample??/parameters/metadata.txt is missing. Generate w/ io_metadata")
                import sys ; sys.exit()

            # Resample to registration resolution to get the mean intensity in the brain
            img_resampled = reg_prep(img, xy_res, z_res, args.reg_res, int(1), args.miracl)

            # Load 50 um tissue mask 
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
            mask = load_mask(sample_path / dynamic_mask_path)

            # Dilate the primary mask
            if args.dilation > 0: 
                mask = dilate_mask(mask, args.dilation)

            # Load the other mask and scale to full resolution
            if args.other_mask:
                other_mask_img = load_mask(sample_path / args.other_mask)

                metadata_path = sample_path / args.metadata
                xy_res, z_res, x_dim, y_dim, z_dim = load_image_metadata_from_txt(metadata_path)
                original_dimensions = np.array([x_dim, y_dim, z_dim])
                other_mask_img = scale_bool_to_full_res(other_mask_img, original_dimensions).astype(np.bool_)

            # Apply mask to image
            if args.mean:
                masked_img = apply_mask_to_ndarray(img, mask, other_mask=other_mask_img, mask_condition=args.direction, new_value=mean_intensity)
            else:
                masked_img = apply_mask_to_ndarray(img, mask, other_mask=other_mask_img, mask_condition=args.direction, new_value=0)

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

    verbose_end_msg()


if __name__ == '__main__':
    main()