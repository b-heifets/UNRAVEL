#!/usr/bin/env python3

import argparse
import numpy as np
from rich.traceback import install
from scipy.ndimage import uniform_filter

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_img_io import load_3D_img, save_as_nii, save_as_tifs, save_as_zarr
from unravel_utils import print_cmd_and_times, print_func_name_args_times

def parse_args():
    parser = argparse.ArgumentParser(description='Load image and apply 3D spatial averaging', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/image .czi, path/img.nii.gz, or path/tif_dir', required=True, action=SM)
    parser.add_argument('-o', '--output', help='Output path. Default: None', required=True, action=SM)
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, action=SM)
    parser.add_argument('-x', '--xy_res', help='xy resolution in um', default=None, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='z resolution in um', default=None, type=float, action=SM)
    parser.add_argument('-d', '--dtype', help='Data type for .nii.gz. Default: uint16', default='uint16', action=SM)
    parser.add_argument('-r', '--reference', help='Reference image for .nii.gz metadata. Default: None', default=None, action=SM)
    parser.add_argument('-ao', '--axis_order', help='Default: xyz. (other option: zyx)', default='xyz', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Usage:     3D_spatial_average.py -i img.nii.gz -o img_spatial_avg.nii.gz -v
    
Input image types: .czi, .nii.gz, .ome.tif series, .tif series, .h5, .zarr

3D spatial averaging:
    - Apply a 3D spatial averaging filter to a 3D numpy array.
    - Default kernel size is 3x3x3, for the current voxel and its 26 neighbors.
    - The output array is the same size as the input array.
    - The edges of the output array are padded with zeros.
    - The output array is the same data type as the input array.
    - The input array must be 3D.
    - The xy and z resolutions are required for saving the output as .nii.gz.
    - The output is saved as .nii.gz, .tif series, or .zarr.
"""
    return parser.parse_args()

@print_func_name_args_times()
def spatial_average_3d(arr, size=3):
    """
    Apply a 3D spatial averaging filter to a 3D numpy array.

    Parameters:
    - arr (np.ndarray): The input 3D array.
    - size (int): The size of the cubic kernel. Default is 3, for the current voxel and its 26 neighbors.

    Returns:
    - np.ndarray: The array after applying the spatial averaging.
    """
    if arr.ndim != 3:
        raise ValueError("Input array must be 3D.")
    
    return uniform_filter(arr, size=size, mode='constant', cval=0.0)

def main():    
    # Load image and metadata
    if args.xy_res is None or args.z_res is None:
        img, xy_res, z_res = load_3D_img(args.input, return_res=True)
    else:
        img = load_3D_img(args.input)
        xy_res, z_res = args.xy_res, args.z_res

    # Apply spatial averaging
    img = spatial_average_3d(img)

    # Save image    
    if args.output.endswith('.nii.gz'):
        save_as_nii(img, args.output, xy_res, z_res, data_type=args.dtype, reference=args.reference)
    elif args.output.endswith('.tif'):
        save_as_tifs(img, args.output, ndarray_axis_order=args.axis_order)
    elif args.output.endswith('.zarr'):
        save_as_zarr(img, args.output, ndarray_axis_order=args.axis_order)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
