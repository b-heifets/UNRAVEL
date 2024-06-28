#!/usr/bin/env python3

"""
Use ``img_max`` from UNRAVEL to load an image.nii.gz and print its max intensity value.

Usage: 
------
    img_max -i path/image.nii.gz
"""

import argparse
import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/image.nii.gz', default=None, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


def find_max_intensity(file_path):
    """Find the maximum intensity value in the NIfTI image file."""
    # Load the .nii.gz file
    nii_img = nib.load(file_path)
    
    # Get the data from the file
    data = nii_img.get_fdata(dtype=np.float32)
    
    # Find the maximum intensity value in the data
    max_intensity = int(data.max())
    
    return max_intensity


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    
    max_intensity = find_max_intensity(args.input)
    print(max_intensity)

    verbose_end_msg()


if __name__ == '__main__':
    main()