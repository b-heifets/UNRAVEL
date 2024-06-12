#!/usr/bin/env python3

"""
Print list of IDs for clusters > X voxels

Usage:
    uniq_intensities.py -i path/input_img.nii.gz -m 100 -id -s
    uniq_intensities.py -i path/input_img.nii.gz -m 100 -id
"""

import argparse
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.img_tools import cluster_IDs
from unravel.core.utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/input_img.nii.gz', required=True, action=SM)
    parser.add_argument('-m', '--minextent', help='Min cluster size in voxels (Default: 100)', default=100, action=SM, type=int)
    parser.add_argument('-id', '--print_IDs', help='Print cluster IDs. Default: True', default=True, action='store_true')
    parser.add_argument('-s', '--print_sizes', help='Print cluster IDs and sizes. Default: False', default=False, action='store_true')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

def main():
    args = parse_args()

    img = load_3D_img(args.input)

    cluster_IDs(img, min_extent=args.minextent, print_IDs=args.print_IDs, print_sizes=args.print_sizes)

if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()