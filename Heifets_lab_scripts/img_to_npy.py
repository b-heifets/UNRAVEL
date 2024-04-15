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
    parser = argparse.ArgumentParser(description='Convert images to HDF5 format for ilastik processing.', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', required=True, help='Input image file path (.czi, .nii.gz, .tif)', action=SM)
    parser.add_argument('-o', '--output', required=True, help='Output HDF5 file path', action=SM)
    parser.add_argument('-ao', '--axis_order', help='Axis order for the image (default: zyx)', default='zyx', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    return parser.parse_args()

def main(args):

    img = load_3D_img(args.input, desired_axis_order=args.axis_order)

    if args.output: 
        output = args.output
    elif args.input.endswith('.czi'):
        output = args.input.replace('.czi', '.npy')
    elif args.input.endswith('.nii.gz'):
        output = args.input.replace('.nii.gz', '.npy')
    elif args.input.endswith('.tif'):
        output = args.input.replace('.tif', '.npy')
    elif args.input.endswith('.zarr'):
        output = args.input.replace('.zarr', '.npy')

    # Save the ndarray to a binary file in NumPy `.npy` format
    np.save(output, img)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()