#!/usr/bin/env python3

"""
Use ``io_img_to_npy`` from UNRAVEL to convert a 3D image to an ndarray and save it as a .npy file.

Usage: 
------
    io_img_to_npy -i path/to/image.czi -o path/to/image.npy
"""

import argparse
import numpy as np
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', required=True, help='Input image file path (.czi, .nii.gz, .tif)', action=SM)
    parser.add_argument('-o', '--output', required=True, help='Output HDF5 file path', action=SM)
    parser.add_argument('-ao', '--axis_order', help='Axis order for the image (default: zyx)', default='zyx', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

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

    verbose_end_msg()


if __name__ == '__main__':
    main()