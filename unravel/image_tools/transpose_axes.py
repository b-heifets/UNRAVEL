#!/usr/bin/env python3

"""
Use ``img_transpose`` from UNRAVEL to run ndarray.transpose(axis_1, axis_2, axis_3).

Usage: 
------
    img_transpose -i path/img
"""

import argparse
from pathlib import Path
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_nii
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.czi, path/img.nii.gz, or path/tif_dir', action=SM)
    parser.add_argument('-xa', '-x_axis', help='Enter 0, 1, or 2. Default: 0', default=0, type=int, action=SM)
    parser.add_argument('-ya', '-y_axis', help='Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-za', '-z_axis', help='Default: 2', default=2, type=int, action=SM)
    parser.add_argument('-o', '--output', help='path/img.nii.gz', action=SM)
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, action=SM)
    parser.add_argument('-ao', '--axis_order', help='Axis order for loading image. Default: xyz. (other option: zyx)', default='xyz', action=SM)
    parser.add_argument('-rr', '--return_res', help='Default: True. If false, enter a float for xy_res and z_res (in um) in prompts', action='store_true', default=True)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


# TODO: Test script. Add support for other output formats.

print_func_name_args_times()
def transpose_img(ndarray, axis_1, axis_2, axis_3):
    """Transposes axes of ndarray"""
    return ndarray.transpose(axis_1, axis_2, axis_3)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    
    if args.return_res:
        img, xy_res, z_res = load_3D_img(args.input, args.channel, desired_axis_order=args.axis_order, return_res=args.return_res)
    else:
        img = load_3D_img(args.input, args.channel, desired_axis_order=args.axis_order, return_res=args.return_res)
        xy_res = float(input("Enter xy_res: "))
        z_res = float(input("Enter z_res: "))

    tranposed_img = transpose_img(img, args.x_axis, args.y_axis, args.z_axis)

    if args.output:
        save_as_nii(tranposed_img, args.output, xy_res, z_res)
    else:
        output = str(Path(args.input).resolve()).replace(".nii.gz", f"_transposed.nii.gz")
        save_as_nii(tranposed_img, output, xy_res, z_res)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()