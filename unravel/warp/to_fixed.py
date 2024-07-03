#!/usr/bin/env python3

"""
Use ``warp_to_fixed`` from UNRAVEL to forward warp a moving image (e.g., from atlas space) to fixed image space (e.g., tissue space). The input/output do not need padding.

Usage:
------
    warp_to_fixed -f reg_inputs/autofl_50um_masked.nii.gz -m path/moving_img.nii.gz -o path/warped_img.nii.gz -ro reg_outputs -fri autofl_50um_masked_fixed_reg_input.nii.gz [-i multiLabel] [-r 50] [-v]

Note: 
    Run this from the folder containing reg_outputs.

    This script is for warping between different atlas spaces. For warping from atlas space to tissue space, use ``to_native``.
"""

import argparse
import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import save_as_nii
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times
from unravel.warp.warp import warp


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-f', '--fixed_img', help='path/fixed_img.nii.gz used as input for ``reg`` (no padding; e.g., reg_inputs/autofl_50um_masked.nii.gz)', required=True, action=SM)
    parser.add_argument('-m', '--moving_img', help='path/moving_image.nii.gz to warp (e.g., from atlas space)', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/native_image.nii.gz', required=True, action=SM)
    parser.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from registration. Default: reg_outputs", default="reg_outputs", action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Fixed input for registration (``reg``) w/ padding in <reg_outputs>. E.g., autofl_50um_masked_fixed_reg_input.nii.gz', required=True, action=SM)
    parser.add_argument('-i', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor, multiLabel [default], linear, bSpline)', default="multiLabel", action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@print_func_name_args_times()
def calculate_padded_dimensions(original_dimensions, pad_fraction=0.15):
    # Calculate padding for the original dimensions (15% of the original dimensions)
    padded_dimensions = []
    for dim in original_dimensions:
        # Calculate pad width for one side, then round to the nearest integer
        pad_width_one_side = np.round(pad_fraction * dim)
        # Calculate total padding for the dimension (both sides)
        total_pad = 2 * pad_width_one_side
        # Calculate new dimension after padding
        new_dim = dim + total_pad
        padded_dimensions.append(int(new_dim))

    return np.array(original_dimensions), np.array(padded_dimensions)

@print_func_name_args_times()
def forward_warp(fixed_img_path, reg_outputs_path, fixed_reg_in, moving_img_path, interpol, output=None):
    """Warp image from atlas space to tissue space and scale to full resolution"""

    # Warp the moving image to tissue space
    warp_outputs_dir = Path(reg_outputs_path) / "warp_outputs" 
    warp_outputs_dir.mkdir(exist_ok=True, parents=True)
    warped_nii_path = str(warp_outputs_dir / str(Path(moving_img_path).name).replace(".nii.gz", "_in_fixed_img_space.nii.gz"))
    if not Path(warped_nii_path).exists():
        print(f'\n    Warping the moving image to fixed image space\n')
        fixed_img_for_reg_path = str(Path(reg_outputs_path) / fixed_reg_in)
        warp(Path(reg_outputs_path), moving_img_path, fixed_img_for_reg_path, warped_nii_path, inverse=False, interpol=interpol)

    # Lower bit depth to match atlas space image
    warped_nii = nib.load(warped_nii_path)
    moving_nii = nib.load(moving_img_path)
    warped_img = np.asanyarray(warped_nii.dataobj, dtype=moving_nii.header.get_data_dtype()).squeeze()

    # Load unpadded fixed image for determining original dimensions
    fixed_img_nii = nib.load(fixed_img_path)
    x_dim, y_dim, z_dim = fixed_img_nii.shape
    original_dimensions = np.array([x_dim, y_dim, z_dim])

    # Calculate resampled and padded dimensions
    dims, padded_dims = calculate_padded_dimensions(original_dimensions, pad_fraction=0.15)

    # Determine where to start cropping (combined padding size) // 2 for padding on one side
    crop_mins = (padded_dims - dims) // 2

    # Perform cropping to remove padding
    warped_img = warped_img[
        crop_mins[0]:crop_mins[0] + dims[0],
        crop_mins[1]:crop_mins[1] + dims[1],
        crop_mins[2]:crop_mins[2] + dims[2]
    ]

    # Save as .nii.gz
    Path(output).parent.mkdir(exist_ok=True, parents=True)
    fixed_img_for_reg_path = str(Path(reg_outputs_path) / fixed_reg_in)
    save_as_nii(warped_img, output, None, None, moving_nii.header.get_data_dtype(), reference=fixed_img_for_reg_path)

    return warped_img


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    forward_warp(args.fixed_img, args.reg_outputs, args.fixed_reg_in, args.moving_img, args.interpol, output=args.output)

    verbose_end_msg()


if __name__ == '__main__':
    main()