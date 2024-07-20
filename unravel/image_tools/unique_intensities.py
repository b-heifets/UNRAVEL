#!/usr/bin/env python3

"""
Use ``img_unique`` from UNRAVEL to print a list of unique intensities greater than 0.

Usage for printing all non-zero intensities:
--------------------------------------------
    img_unique -i path/input_img.nii.gz

Usage for printing the number of voxels for each intensity that is present:
---------------------------------------------------------------------------
    img_unique -i path/input_img.nii.gz -s

Usage for printing unique intensities w/ a min cluster size > 100 voxels:
-------------------------------------------------------------------------
    img_unique -i path/input_img.nii.gz -m 100
"""

import argparse
import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.img_tools import cluster_IDs
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/input_img.nii.gz', required=True, action=SM)
    parser.add_argument('-m', '--min_extent', help='Min cluster size in voxels (Default: 1)', default=1, action=SM, type=int)
    parser.add_argument('-s', '--print_sizes', help='Print cluster IDs and sizes. Default: False', default=False, action='store_true')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def uniq_intensities(input, min_extent=1, print_sizes=False):
    """Loads a 3D image and prints non-zero unique intensity values in a space-separated list.

    Args:
        input (_type_): _description_
        min_extent (int, optional): _description_. Defaults to 1.
        print_sizes (bool, optional): _description_. Defaults to False.

    Returns:
        list of ints: list of unique intensities
    """
    if str(input).endswith(".nii.gz"):
        nii = nib.load(input)
        img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()
    else: 
        img = load_3D_img(input)

    uniq_intensities = cluster_IDs(img, min_extent=min_extent, print_IDs=True, print_sizes=print_sizes)

    return uniq_intensities


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Print unique intensities in image
    uniq_intensities(args.input, args.min_extent, args.print_sizes)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()