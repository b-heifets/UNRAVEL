#!/usr/bin/env python3

import argparse
from argparse import RawTextHelpFormatter
import ants
import cv2 
import dask.array as da
import multiprocessing
import nibabel as nib
import numpy as np
import zarr
from dask.distributed import Client
from pathlib import Path
from rich import print
from rich.traceback import install
from scipy.ndimage import rotate, zoom
from unravel_config import Configuration
from unravel_utils import print_cmd_and_times, print_func_name_args_times

def parse_args():
    parser = argparse.ArgumentParser(description='Warp atlas space image to tissue space, reorient, and scale to full resolution', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-m', '--moving_img', help='path/image.nii.gz to warp from atlas space', required=True, metavar='')
    parser.add_argument('-f', '--fixed_img', help='path/fixed_image.nii.gz (e.g., reg_final/clar_downsample_res25um.nii.gz)', required=True, metavar='')
    parser.add_argument('-F', '--full_res_img', help='rel_path/full_res_img.nii.gz or name of tif dir (to get dims for scaling)', required=True, metavar='')
    parser.add_argument('-p', '--reg_o_prefix', help='Registration output prefix. Default: allen_clar_ants', default='allen_clar_ants', metavar='')
    parser.add_argument('-n', '--no_pad_img', help='Reg input mage w/o padding. Default: reg_input/autofl_*um.nii.gz', default='reg_input/autofl_*um.nii.gz', metavar='')
    parser.add_argument('-p', '--pad_img', help='Image w padding. Default: clar_res0.05_pad.nii.gz', default='clar_res0.05_pad.nii.gz', metavar='') ### Could calc padding
    parser.add_argument('-o', '--output', help='Save as path/native_image.zarr (fast) or path/native_image.nii.gz if provided', metavar='')
    parser.add_argument('-t', '--transforms', help="Name of folder w/ transforms from registration. Default: clar_allen_reg", default="clar_allen_reg", metavar='')
    parser.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, metavar='')
    parser.add_argument('-fr', '--fixed_res', help='Resolution of the fixed image. Default: 25', default='25',type=int, metavar='')
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for scaling to full res after warping. Default: 0 (nearest-neighbor)', default='25',type=int, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Run from sample?? folder.

Usage: to_native3.py -i <path/warped_image.nii.gz> -o <path/native_image.nii.gz> [-s path/seg_img.nii.gz or -t ochann]
"""
    return parser.parse_args()


@print_func_name_args_times()
def nii_to_ndarray(img_path):
    """Loads path/img.nii.gz as nib object and returns ndarray (same dtype)"""
    nii_img = nib.load(img_path)    
    return np.asanyarray(nii_img.dataobj) # Preserves dtype

@print_func_name_args_times()
def reorient_to_tissue_space(ndarray):
    """After warping to native space, reorients image to match tissue"""
    rotated_img = rotate(ndarray, -90, reshape=True, axes=(0, 1)) # Rotate 90 degrees to the right
    flipped_img = np.fliplr(rotated_img) # Flip horizontally
    return flipped_img

@print_func_name_args_times()
def scale_to_full_res(ndarray, new_width, new_height, new_depth, zoom_order=0):
    """Scale ndarray to match provided dimensions (order=0 is nearest-neighbor). Returns scaled ndarray."""
    zoom_factors = (new_width / ndarray.shape[0], new_height / ndarray.shape[1], new_depth / ndarray.shape[2])
    scaled_data = zoom(ndarray, zoom_factors, order=zoom_order) 
    return scaled_data

@print_func_name_args_times()
def save_nii(ndarray, output_path):
    """Save ndarray to specified path (RAS; no scaling info)"""
    nifti_img = nib.Nifti1Image(ndarray, affine=np.eye(4))
    nib.save(nifti_img, output_path)

@print_func_name_args_times()
def save_as_zarr(ndarray, output_path):
    """Save ndarray to specified path"""
    num_cores = multiprocessing.cpu_count()
    print(f'    Number of CPU cores: {num_cores}')
    client = Client(n_workers=num_cores)
    dask_array = da.from_array(ndarray, chunks='auto')
    compressor = zarr.Blosc(cname='lz4', clevel=9, shuffle=zarr.Blosc.BITSHUFFLE)
    dask_array.to_zarr(output_path, compressor=compressor, overwrite=True)
    client.close()

@print_func_name_args_times()
def warp_to_native(moving_img_path, fixed_img_path, transforms_dir, reg_output_prefix, img_pre_padding, img_post_padding, reg_input_res, fixed_img_res, full_res_img):
    """Warp image from atlas space to full res native space"""
    # Load images for warping
    atlas_space_ants_img = ants.image_read(moving_img_path)
    fixed_ants_img = ants.image_read(fixed_img_path)

    # Warp from atlas to native space
    transforms_dir = Path(transforms_dir).resolve()
    warped_ants_img = ants.apply_transforms(
        fixed=fixed_ants_img,
        moving=atlas_space_ants_img,
        transformlist=[
            f'{transforms_dir}/{reg_output_prefix}1Warp.nii.gz', 
            f'{transforms_dir}/{reg_output_prefix}0GenericAffine.mat',
            f'{transforms_dir}/init_tform.mat'
        ]
    )

    # Load images for calculating how much padding to remove
    reg_file_pre_padding = nii_to_ndarray(img_pre_padding)
    reg_file_post_padding = nii_to_ndarray(f'{transforms_dir}/{img_post_padding}')

    # Get shapes 
    reg_file_pre_padding_shape = np.array(reg_file_pre_padding.shape)
    reg_file_post_padding_shape = np.array(reg_file_post_padding.shape)

    # Calculate zoom factor
    zf = round(reg_input_res / fixed_img_res)

    # Determine where to start cropping ((combined padding size // 2 for padding on one side ) * zoom factor)
    crop_mins = ((reg_file_post_padding_shape - reg_file_pre_padding_shape) // 2) * zf 

    # Find img dims of warped image lacking padding
    crop_sizes = reg_file_pre_padding_shape * zf

    # Perform cropping to remove padding
    atlas_space_nib_img = nib.load(moving_img_path) 
    data_type = atlas_space_nib_img.get_data_dtype()
    warped_img = warped_ants_img.numpy().astype(data_type) # convert to ndarray with original dtype
    cropped_img = warped_img[
        crop_mins[0]:crop_mins[0] + crop_sizes[0],
        crop_mins[1]:crop_mins[1] + crop_sizes[1],
        crop_mins[2]:crop_mins[2] + crop_sizes[2]
    ]

    # Reorient image
    reoriented_img = reorient_to_tissue_space(cropped_img)

    # Get full res dimensions
    if str(full_res_img).endswith(".nii.gz"): 
        nii_seg_img = nib.load(full_res_img)
        x_dim = nii_seg_img.shape[0]
        y_dim = nii_seg_img.shape[1]
        z_dim = nii_seg_img.shape[2]
    else: 
        # Get dims from tifs (Using a generator without converting to a list to be memory efficient)
        tifs = Path(full_res_img).resolve().glob("*.tif") # Generator
        tif_file = next(tifs, None) # First item in generator
        tif_img = cv2.imread(str(tif_file), cv2.IMREAD_UNCHANGED) # Load first tif
        x_dim = tif_img.shape[1]
        y_dim = tif_img.shape[0]
        z_dim = sum(1 for _ in tifs) + 1 # Count tifs. Added 1 to account for missing item in the generator after next()

    # Scale to full resolution
    native_img = scale_to_full_res(reoriented_img, x_dim, y_dim, z_dim, zoom_order=args.zoom_order)
    return native_img


def main():

    native_img = warp_to_native(args.moving_img, args.fixed_img, args.transforms, args.reg_o_prefix, args.no_pad_img, args.pad_img, args.reg_res, args.fixed_res, args.full_res_img)

    # Save as .nii.gz or .zarr
    if args.output:
        if str(args.output).endswith(".zarr"):
            save_as_zarr(native_img, args.output)
        elif str(args.output).endswith(".nii.gz"):
            save_nii(native_img, args.output)
        else: 
            print(f"    [red1]Output path does not end with .zarr or .nii.gz") 

    


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()