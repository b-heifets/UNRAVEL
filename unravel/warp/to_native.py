#!/usr/bin/env python3

"""
Use ``warp_to_native`` from UNRAVEL to warp an atlas space image to tissue space and scale to full resolution.

CLI usage:
----------
    warp_to_native -m <path/image_to_warp_from_atlas_space.nii.gz> -o <native>/native_<img>.zarr

Python usage:
-------------
    >>> import unravel.warp.to_native as to_native
    >>> native_img = to_native(sample_path, reg_outputs, fixed_reg_in, moving_img_path, metadata_rel_path, reg_res, miracl, zoom_order, interpol, output=None)
    >>> # native_img is an np.ndarray

Prereq:
    ./parameters/metadata.txt (from io_metadata)
"""

import argparse
import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy.ndimage import zoom

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_image_metadata_from_txt, save_as_zarr, save_as_nii
from unravel.core.img_tools import reverse_reorient_for_raw_to_nii_conv
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples, initialize_progress_bar, print_func_name_args_times
from unravel.warp.warp import warp


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-m', '--moving_img', help='path/image.nii.gz to warp from atlas space', required=True, action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Fixed input for registration (``reg``). Default: autofl_50um_masked_fixed_reg_input.nii.gz', default="autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-i', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor, multiLabel [default], linear, bSpline)', default="multiLabel", action=SM)
    parser.add_argument('-o', '--output', help='Save as rel_path/native_image.zarr (fast) or rel_path/native_image.nii.gz if provided', default=None, action=SM)
    parser.add_argument('-md', '--metadata', help='path/metadata.txt. Default: ./parameters/metadata.txt', default="./parameters/metadata.txt", action=SM)
    parser.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from registration. Default: reg_outputs", default="reg_outputs", action=SM)
    parser.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for scaling to full res. Default: 0 (nearest-neighbor)', default='0',type=int, action=SM)
    parser.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@print_func_name_args_times()
def calculate_resampled_padded_dimensions(original_dimensions, xy_res, z_res, target_res=50, pad_fraction=0.15, miracl=False):
    # Calculate zoom factors for xy and z dimensions
    zf_xy = xy_res / target_res
    zf_z = z_res / target_res
    
    # Calculate expected dimensions of the resampled image (reg input is typically 50um)
    resampled_dimensions = [
        round(dim * zf) for dim, zf in zip(original_dimensions, (zf_xy, zf_xy, zf_z))
    ]
    
    # Calculate padding for the resampled image (15% of the resampled dimensions)
    padded_dimensions = []
    for dim in resampled_dimensions:
        # Calculate pad width for one side, then round to the nearest integer
        pad_width_one_side = np.round(pad_fraction * dim)
        # Calculate total padding for the dimension (both sides)
        total_pad = 2 * pad_width_one_side
        # Calculate new dimension after padding
        new_dim = dim + total_pad
        padded_dimensions.append(int(new_dim))
    
    # Swap axes if miracl compatibility mode is True
    if miracl: 
        resampled_dimensions[0], resampled_dimensions[1] = resampled_dimensions[1], resampled_dimensions[0]
        padded_dimensions[0], padded_dimensions[1] = padded_dimensions[1], padded_dimensions[0]
    
    return np.array(resampled_dimensions), np.array(padded_dimensions)

@print_func_name_args_times()
def scale_to_full_res(ndarray, full_res_dims, zoom_order=0):
    """Scale ndarray to match x, y, z dimensions provided as ndarray (order=0 is nearest-neighbor). Returns scaled ndarray."""
    zoom_factors = (full_res_dims[0] / ndarray.shape[0], full_res_dims[1] / ndarray.shape[1], full_res_dims[2] / ndarray.shape[2])
    scaled_img = zoom(ndarray, zoom_factors, order=zoom_order) 
    return scaled_img

@print_func_name_args_times()
def to_native(sample_path, reg_outputs, fixed_reg_in, moving_img_path, metadata_rel_path, reg_res, miracl, zoom_order, interpol, output=None):
    """Warp image from atlas space to tissue space and scale to full resolution"""

    # Warp the moving image to tissue space
    reg_outputs_path = sample_path / reg_outputs
    warp_outputs_dir = reg_outputs_path / "warp_outputs" 
    warp_outputs_dir.mkdir(exist_ok=True, parents=True)
    warped_nii_path = str(warp_outputs_dir / str(Path(moving_img_path).name).replace(".nii.gz", "_in_tissue_space.nii.gz"))
    if not Path(warped_nii_path).exists():
        print(f'\n    Warping the moving image to tissue space\n')
        fixed_img_for_reg_path = str(reg_outputs_path / fixed_reg_in)
        warp(reg_outputs_path, moving_img_path, fixed_img_for_reg_path, warped_nii_path, inverse=False, interpol=interpol)

    # Lower bit depth to match atlas space image
    warped_nii = nib.load(warped_nii_path)
    moving_nii = nib.load(moving_img_path)
    warped_img = np.asanyarray(warped_nii.dataobj, dtype=moving_nii.header.get_data_dtype()).squeeze()

    # Load resolutions and dimensions of full res image for scaling 
    metadata_path = sample_path / metadata_rel_path
    xy_res, z_res, x_dim, y_dim, z_dim = load_image_metadata_from_txt(metadata_path)
    if xy_res is None:
        print("    [red1]./sample??/parameters/metadata.txt is missing. Generate w/ ``io_metadata``")
        import sys ; sys.exit()
    original_dimensions = np.array([x_dim, y_dim, z_dim])

    # Calculate resampled and padded dimensions
    resampled_dims, padded_dims = calculate_resampled_padded_dimensions(original_dimensions, xy_res, z_res, reg_res, pad_fraction=0.15, miracl=miracl)

    # Determine where to start cropping (combined padding size) // 2 for padding on one side
    crop_mins = (padded_dims - resampled_dims) // 2

    # Find img dims of warped image lacking padding
    crop_sizes = resampled_dims

    # Perform cropping to remove padding
    warped_img = warped_img[
        crop_mins[0]:crop_mins[0] + crop_sizes[0],
        crop_mins[1]:crop_mins[1] + crop_sizes[1],
        crop_mins[2]:crop_mins[2] + crop_sizes[2]
    ]

    # Reorient if needed
    if miracl: 
        warped_img = reverse_reorient_for_raw_to_nii_conv(warped_img)

    # Scale to full resolution
    native_img = scale_to_full_res(warped_img, original_dimensions, zoom_order=zoom_order)
    
    # Save as .nii.gz or .zarr
    if output is not None:
        if str(output).endswith(".zarr"):
            save_as_zarr(native_img, output)
        elif str(output).endswith(".nii.gz"):
            save_as_nii(native_img, output, xy_res, z_res, native_img.dtype)

    return native_img


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
            
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            if args.output is not None:
                output = sample_path / args.output
            else:
                output = None
            
            to_native(sample_path, args.reg_outputs, args.fixed_reg_in, args.moving_img, args.metadata, args.reg_res, args.miracl, args.zoom_order, args.interpol, output=output)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()