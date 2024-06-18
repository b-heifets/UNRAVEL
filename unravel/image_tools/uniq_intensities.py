#!/usr/bin/env python3

"""
Use ``img_unique`` from UNRAVEL to print a list of unique intensities greater than 0.

Usage for printing all non-zero intensities:
--------------------------------------------
    img_unique -i path/input_img.nii.gz

Usage for printing the number of voxels for each intensity that is present:
---------------------------------------------------------------------------
    img_unique -i path/input_img.nii.gz

Usage for checking which clusters are present if the min cluster size was 100 voxels:
-------------------------------------------------------------------------------------
    img_unique -i path/input_img.nii.gz -m 100
"""

import argparse
import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
# from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.img_tools import cluster_IDs
from unravel.core.utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/input_img.nii.gz', required=True, action=SM)
    parser.add_argument('-m', '--minextent', help='Min cluster size in voxels (Default: 1)', default=1, action=SM, type=int)
    parser.add_argument('-s', '--print_sizes', help='Print cluster IDs and sizes. Default: False', default=False, action='store_true')
    # parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

def main():
    args = parse_args()

    if str(args.input).endswith(".nii.gz"):
        nii = nib.load(args.input)
        img = np.asanyarray(nii.dataobj, dtype=np.uint16).squeeze()
    else: 
        img = load_3D_img(args.input)

    cluster_IDs(img, min_extent=args.minextent, print_IDs=True, print_sizes=args.print_sizes)

if __name__ == '__main__': 
    install()
    args = parse_args()
    # Configuration.verbose = args.verbose
    # print_cmd_and_times(main)()
    main()