#!/usr/bin/env python3

import argparse
import os
from argparse import RawTextHelpFormatter
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_tools import load_3D_img
from unravel_utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Load image (.czi, .nii.gz, or tif series) to get metadata and save to ./parameters/metadata.txt', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-i', '--input', help='path/img.czi, path/img.nii.gz, or path/tif_dir', metavar='')
    parser.add_argument('-x', '--xy_res', help='xy resolution in microns', default=None, type=float, metavar='')
    parser.add_argument('-z', '--z_res', help='z resolution in microns', default=None, type=float, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Run this from a sample?? folder. 
Loading a full image automatically gets the metadata and saves it to ./parameters/metadata.txt if it does not already exist. 
Pass in xy_res and z_res if they are not obtainable from the metadata."""    
    return parser.parse_args()


def main(): 

    load_3D_img(args.input, desired_axis_order="xyz", xy_res=args.xy_res, z_res=args.z_res, return_metadata=True, save_metadata=True)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()