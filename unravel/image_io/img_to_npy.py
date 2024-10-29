#!/usr/bin/env python3

"""
Use ``io_img_to_npy`` (``i2np``) from UNRAVEL to convert a 3D image to an ndarray and save it as a .npy file.

Usage: 
------
    io_img_to_npy -i path/to/image.czi -o path/to/image.npy [-ao zyx] [-v]
"""

import numpy as np
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', required=True, help='Input image file path (.czi, .nii.gz, .tif)', action=SM)
    reqs.add_argument('-o', '--output', required=True, help='Output HDF5 file path', action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-ao', '--axis_order', help='Axis order for the image (default: zyx)', default='zyx', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    img = load_3D_img(args.input, desired_axis_order=args.axis_order, verbose=args.verbose)

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