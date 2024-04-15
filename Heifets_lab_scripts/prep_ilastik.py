#!/usr/bin/env python3

import argparse
import numpy as np
import h5py
from rich import print
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_img_io import load_3D_img
from unravel_utils import print_cmd_and_times

def parse_args():
    parser = argparse.ArgumentParser(description='Convert images to HDF5 format for ilastik processing.')
    parser.add_argument('-i', '--input', required=True, help='Input image file path (.czi, .nii.gz, .tif)', action=SM)
    parser.add_argument('-o', '--output', required=True, help='Output HDF5 file path', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    return parser.parse_args()


# def save_image_as_hdf5(image_data, output_path, compression_type='gzip', compression_opts=None):
#     with h5py.File(output_path, 'w') as f:
#         # Here you can customize the compression based on your choice
#         if compression_type == 'gzip':
#             compression_opts = 9  # Max compression for gzip
#         f.create_dataset('data', data=image_data, compression=compression_type, compression_opts=compression_opts)
#         print(f"Image saved to HDF5 with {compression_type} compression at {output_path}")

def main(args):

    img = load_3D_img(args.input, desired_axis_order="zyx") # Ensure the image is in the correct axis order for ilastik

    if args.output: 
        output = args.output
    elif args.input.endswith('.czi'):
        output = args.input.replace('.czi', '.h5')
    elif args.input.endswith('.nii.gz'):
        output = args.input.replace('.nii.gz', '.h5')
    elif args.input.endswith('.tif'):
        output = args.input.replace('.tif', '.h5')
    elif args.input.endswith('.zarr'):
        output = args.input.replace('.zarr', '.h5')

    # if args.verbose:
    #     print("    Image loaded, converting to HDF5...")
    # with h5py.File(output, 'w') as f:
    #     ds = f.create_dataset('data', data=img, compression="gzip") # Use gzip compression for space efficiency
    #     if args.verbose:
    #         print(f"    Image saved to HDF5 dataset: {args.output}")

    # Example usage
    # save_image_as_hdf5(img, output, 'gzip')  # Using maximum compression with gzip

    if args.verbose:
        print("Image loaded, converting to HDF5 with LZF compression...")
    with h5py.File(output, 'w') as f:
        f.create_dataset('data', data=img, compression="lzf")
        if args.verbose:
            print(f"Image saved to HDF5 dataset: {output}")

if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()