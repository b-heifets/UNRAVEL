#!/usr/bin/env python3

import argparse
import ants
import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.traceback import install
from scipy.ndimage import zoom

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_img_io import load_image_metadata_from_txt, save_as_zarr, save_as_nii
from unravel_img_tools import reverse_reorient_for_raw_to_nii_conv
from unravel_utils import print_cmd_and_times, print_func_name_args_times

def parse_args():
    parser = argparse.ArgumentParser(description='Warp atlas space image to tissue space, reorient, and scale to full resolution', formatter_class=SuppressMetavar)
    parser.add_argument('-m', '--moving_img', help='path/image.nii.gz to warp from atlas space', required=True, action=SM)
    parser.add_argument('-f', '--fixed_img', help='path/fixed_image.nii.gz (e.g., reg_final/clar_downsample_res25um.nii.gz)', required=True, action=SM)
    parser.add_argument('-i', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor [default], genericLabel, linear)', default="nearestNeighbor", action=SM)
    parser.add_argument('-o', '--output', help='Save as path/native_image.zarr (fast) or path/native_image.nii.gz if provided', default=None, action=SM)
    parser.add_argument('-d', '--dtype', help='Desired dtype for full res output (uint8, uint16). Default: moving_img.dtype', action=SM)
    parser.add_argument('-md', '--metadata', help='path/metadata.txt. Default: ./parameters/metadata.txt', default="./parameters/metadata.txt", action=SM)
    parser.add_argument('-rp', '--reg_o_prefix', help='Registration output prefix. Default: allen_clar_ants', default='allen_clar_ants', action=SM)
    parser.add_argument('-t', '--transforms', help="Name of folder w/ transforms from registration. Default: clar_allen_reg", default="clar_allen_reg", action=SM)
    parser.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    parser.add_argument('-fr', '--fixed_res', help='Resolution of the fixed image. Default: 25', default='25',type=int, action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for scaling to full res. Default: 0 (nearest-neighbor)', default='0',type=int, action=SM)
    parser.add_argument('-l', '--legacy', help='Mode for backward compatibility (accounts for raw to nii reorienting)', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Run from sample?? folder.

Prereq: ./parameters/metadata.txt (prep_reg.py or metadata.py)

Usage: to_native5.py -m <path/image_to_warp_from_atlas_space.nii.gz> -f <path/fixed_image.nii.gz> -o <native>/native_<img>.nii.gz [-l -d uint8]

Next script: native_clusters.py"""
    return parser.parse_args()


@print_func_name_args_times()
def calculate_resampled_padded_dimensions(original_dimensions, xy_res, z_res, target_res=50, pad_fraction=0.15, legacy=False):
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
    
    # Swap axes if legacy mode is True
    if legacy: 
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
def warp_to_native(moving_img_path, fixed_img_path, transforms_dir, reg_output_prefix, reg_input_res, fixed_img_res, interpol, metadata_path, legacy, zoom_order, data_type, output):
    """Warp image from atlas space to full res native space"""
    # Load images for warping
    atlas_space_ants_img = ants.image_read(moving_img_path)
    fixed_ants_img = ants.image_read(fixed_img_path)

    # Warp from atlas to native space
    transforms_dir = Path(transforms_dir).resolve()
    deformation_field = str(Path(f'{transforms_dir}/{reg_output_prefix}1Warp.nii.gz'))
    generic_affine_matrix = str(Path(f'{transforms_dir}/{reg_output_prefix}0GenericAffine.mat'))
    intial_affine_matrix = str(Path(f'{transforms_dir}/init_tform.mat'))
    warped_ants_img = ants.apply_transforms(
        fixed=fixed_ants_img,
        moving=atlas_space_ants_img,
        transformlist=[deformation_field, generic_affine_matrix, intial_affine_matrix],
        interpolator=interpol
    )

    # Lower bit depth if specified
    if data_type: 
        warped_ants_img = warped_ants_img.astype(data_type)

    # Load resolutions and dimensions of full res image or scaling and to calculate how much padding to remove
    xy_res, z_res, x_dim, y_dim, z_dim = load_image_metadata_from_txt(metadata_path)
    if xy_res is None:
        print("    [red1]./sample??/parameters/metadata.txt is missing. Generate w/ metadata.py")
        import sys ; sys.exit()

    original_dimensions = np.array([x_dim, y_dim, z_dim])

    # Calculate resampled and padded dimensions
    resampled_dims, padded_dims = calculate_resampled_padded_dimensions(original_dimensions, xy_res, z_res, reg_input_res, pad_fraction=0.15, legacy=legacy)

    # Calculate zoom factor
    zf = round(reg_input_res / fixed_img_res)

    # Determine where to start cropping ((combined padding size // 2 for padding on one side ) * zoom factor)
    crop_mins = ((padded_dims - resampled_dims) // 2) * zf 

    # Find img dims of warped image lacking padding
    crop_sizes = resampled_dims * zf

    # Lower bit depth
    if data_type: 
        warped_img = warped_ants_img.numpy().astype(data_type)
    else: 
        atlas_space_nib_img = nib.load(moving_img_path) 
        data_type = atlas_space_nib_img.get_data_dtype()
        warped_img = warped_ants_img.numpy().astype(data_type) # convert to ndarray with original dtype

    # Perform cropping to remove padding
    cropped_img = warped_img[
        crop_mins[0]:crop_mins[0] + crop_sizes[0],
        crop_mins[1]:crop_mins[1] + crop_sizes[1],
        crop_mins[2]:crop_mins[2] + crop_sizes[2]
    ]

    if legacy: 
        cropped_img = reverse_reorient_for_raw_to_nii_conv(cropped_img)

    # cropped_img should be oriented like the raw image
    # Scale to full resolution
    native_img = scale_to_full_res(cropped_img, original_dimensions, zoom_order)

    # Save as .nii.gz or .zarr
    if output:
        if str(output).endswith(".zarr"):
            save_as_zarr(native_img, output)
        elif str(output).endswith(".nii.gz"):
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            save_as_nii(native_img, output, xy_res, z_res, native_img.dtype)
        else: 
            print(f"\n    [red bold]Output path does not end with .zarr or .nii.gz\n") 

    return native_img


def main():

    warp_to_native(args.moving_img, args.fixed_img, args.transforms, args.reg_o_prefix, args.reg_res, args.fixed_res, args.interpol, args.metadata, args.legacy, args.zoom_order, args.dtype, args.output)

if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()