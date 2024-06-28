#!/usr/bin/env python3

"""
Use ``img_spatial_avg`` from UNRAVEL to load an image and apply 3D spatial averaging.

Usage:
------
    img_spatial_avg -i <tif_dir> -o spatial_avg.zarr -d 2 -v 
    
Input image types:
    - .czi, .nii.gz, .ome.tif series, .tif series, .h5, .zarr

3D spatial averaging:
    - Apply a 3D spatial averaging filter to a 3D numpy array.
    - Default kernel size is 3x3x3, for the current voxel and its 26 neighbors.
    - The output array is the same size as the input array.
    - The edges of the output array are padded with zeros.
    - The output array is the same data type as the input array.
    - The input array must be 3D.
    - The xy and z resolutions are required for saving the output as .nii.gz.
    - The output is saved as .nii.gz, .tif series, or .zarr.

2D spatial averaging:
    - Apply a 2D spatial averaging filter to each slice of a 3D numpy array.
    - Default kernel size is 3x3, for the current pixel and its 8 neighbors.
    - The output array is the same size as the input array.
    - The edges of the output array are padded with zeros.
    - The output array is the same data type as the input array.
    - The input array must be 3D.
    - The xy and z resolutions are required for saving the output as .nii.gz.
    - The output is saved as .nii.gz, .tif series, or .zarr.

Outputs: 
    - .nii.gz, .tif series, or .zarr depending on the output path extension.
"""

import argparse
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from rich.traceback import install
from scipy.ndimage import uniform_filter

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_nii, save_as_tifs, save_as_zarr
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/image .czi, path/img.nii.gz, or path/tif_dir', required=True, action=SM)
    parser.add_argument('-o', '--output', help='Output path. Default: None', required=True, action=SM)
    parser.add_argument('-d', '--dimensions', help='2D or 3D spatial averaging. (2 or 3)', required=True, type=int, action=SM)
    parser.add_argument('-k', '--kernel_size', help='Size of the kernel for spatial averaging. Default: 3', default=3, type=int, action=SM)
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, action=SM)
    parser.add_argument('-x', '--xy_res', help='xy resolution in um', default=None, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='z resolution in um', default=None, type=float, action=SM)
    parser.add_argument('-dt', '--dtype', help='Output data type. Default: uint16', default='uint16', action=SM)
    parser.add_argument('-r', '--reference', help='Reference image for .nii.gz metadata. Default: None', default=None, action=SM)
    parser.add_argument('-ao', '--axis_order', help='Default: xyz. (other option: zyx)', default='xyz', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@print_func_name_args_times()
def spatial_average_3D(arr, kernel_size=3):
    """
    Apply a 3D spatial averaging filter to a 3D numpy array.

    Parameters:
    - arr (np.ndarray): The input 3D array.
    - kernel_size (int): The size of the cubic kernel. Default is 3, for the current voxel and its 26 neighbors.

    Returns:
    - np.ndarray: The array after applying the spatial averaging.
    """
    if arr.ndim != 3:
        raise ValueError("Input array must be 3D.")
    
    return uniform_filter(arr, size=kernel_size, mode='constant', cval=0.0)

def apply_2D_mean_filter(slice, kernel_size=(3, 3)):
    """Apply a 2D mean filter to a single slice."""
    kernel = np.ones(kernel_size, np.float32) / (kernel_size[0] * kernel_size[1])
    return cv2.filter2D(slice, -1, kernel)

@print_func_name_args_times()
def spatial_average_2D(volume, filter_func, kernel_size=(3, 3), threads=8):
    """
    Apply a specified 2D filter function to each slice of a 3D volume in parallel.

    Parameters:
    - volume (np.ndarray): The input 3D array.
    - filter_func (callable): The filter function to apply to each slice.
    - kernel_size (tuple): The dimensions of the kernel to be used in the filter.
    - threads (int): The number of parallel threads to use.

    Returns:
    - np.ndarray: The volume processed with the filter applied to each slice.
    """
    processed_volume = np.empty_like(volume)
    num_cores = min(len(volume), threads)  # Limit the number of cores to the number of slices or specified threads

    with ThreadPoolExecutor(max_workers=num_cores) as executor:
        # Each slice is processed independently and the result is stored in the corresponding index
        results = executor.map(filter_func, volume, [kernel_size] * len(volume))
        for i, processed_slice in enumerate(results):
            processed_volume[i] = processed_slice

    return processed_volume


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    
    # Load image and metadata
    if args.xy_res is None or args.z_res is None:
        img, xy_res, z_res = load_3D_img(args.input, return_res=True)
    else:
        img = load_3D_img(args.input)
        xy_res, z_res = args.xy_res, args.z_res

    # Apply spatial averaging
    if args.dimensions == 3:
        img = spatial_average_3D(img, kernel_size=args.kernel_size)
    elif args.dimensions == 2:
        img = spatial_average_2D(img, apply_2D_mean_filter, kernel_size=(args.kernel_size, args.kernel_size))
    else:
        raise ValueError("Dimensions must be 2 or 3.")

    # Set the data type for the output
    if args.dtype == 'uint8':
        img = img.astype(np.uint8)
    elif args.dtype == 'uint16':
        img = img.astype(np.uint16)
    elif args.dtype == 'float32':
        img = img.astype(np.float32)
    else:
        raise ValueError("Data type must be uint8, uint16, or float32.")

    # Save image    
    if args.output.endswith('.nii.gz'):
        save_as_nii(img, args.output, xy_res, z_res, data_type=args.dtype, reference=args.reference)
    elif args.output.endswith('.tif'):
        save_as_tifs(img, args.output, ndarray_axis_order=args.axis_order)
    elif args.output.endswith('.zarr'):
        save_as_zarr(img, args.output, ndarray_axis_order=args.axis_order)

    verbose_end_msg()


if __name__ == '__main__':
    main()