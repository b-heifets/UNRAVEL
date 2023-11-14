#!/usr/bin/env python3

import argparse
from argparse import RawTextHelpFormatter
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_tools import load_3D_img
from unravel_utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Load image (.czi, .nii.gz, or tif series)  and get metadata', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-i', '--input', help='path/img.czi, path/img.nii.gz, or path/tif_dir', metavar='')
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, metavar='')
    parser.add_argument('-ao', '--axis_order', help='Default: xyz. (other option: zyx)', default='xyz', metavar='')
    parser.add_argument('-rr', '--return_res', help='Default: True.', action='store_true', default=True)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()

def main():    
    if args.return_res:
        img, xy_res, z_res = load_3D_img(args.input, args.channel, desired_axis_order=args.axis_order, return_res=args.return_res)
    else:
        img = load_3D_img(args.input, args.channel, desired_axis_order=args.axis_order, return_res=args.return_res)

if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()