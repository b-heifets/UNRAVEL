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


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/image.nii.gz', default=None, action=SM)
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


def main():
    args = parse_args()
    max_intensity = find_max_intensity(args.input)
    print(max_intensity)


if __name__ == '__main__':
    install()
    main()