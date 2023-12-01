#!/usr/bin/env python3

import argparse
from pathlib import Path
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_tools import load_3D_img, save_as_nii
from unravel_utils import print_cmd_and_times, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(description='Run ndarray.transpose(axis_1, axis_2, axis_3)')
    parser.add_argument('-i', '--input', help='path/img.czi, path/img.nii.gz, or path/tif_dir', metavar='')
    parser.add_argument('-xa', '-x_axis', help='Enter 0, 1, or 2. Default: 0', default=0, type=int, metavar='')
    parser.add_argument('-ya', '-y_axis', help='Default: 1', default=1, type=int, metavar='')
    parser.add_argument('-za', '-z_axis', help='Default: 2', default=2, type=int, metavar='')
    parser.add_argument('-o', '--output', help='path/img.nii.gz', metavar='')
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, metavar='')
    parser.add_argument('-ao', '--axis_order', help='Axit order for loading image. Default: xyz. (other option: zyx)', default='xyz', metavar='')
    parser.add_argument('-rr', '--return_res', help='Default: True. If false, enter a float for xy_res and z_res (in um) in prompts', action='store_true', default=True)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


print_func_name_args_times()
def transpose_img(ndarray, axis_1, axis_2, axis_3):
    """Transposes axes of ndarray"""
    return ndarray.transpose(axis_1, axis_2, axis_3)

def main():    
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

if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()