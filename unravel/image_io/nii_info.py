#!/usr/bin/env python3

"""
Use ``io_nii_info`` from UNRAVEL to load an .nii.gz image and print its data type, shape, voxel sizes, and affine matrix using nibabel.

Usage:
------
    io_nii_info -i path/img.nii.gz
"""

import argparse
import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

def nii_axis_codes(nii):
    """Get and return axes codes (three letter orientation like RAS) from an nibabel NIfTI image"""
    axcodes_tuple = nib.orientations.aff2axcodes(nii.affine) 
    axcodes = ''.join(axcodes_tuple) 
    return axcodes


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    
    nii = nib.load(args.input)
    
    np.set_printoptions(precision=2, suppress=True)

    # Print data type
    data_type = nii.get_data_dtype()
    print(f'\nData type:\n[default bold]{data_type}')

    # Print dimensions
    print(f'\nShape (x, y, z):\n{nii.shape}')

    # Print the voxel sizes
    voxel_sizes = nii.header.get_zooms()
    voxel_sizes = tuple(np.array(voxel_sizes) * 1000)
    print(f'\nVoxel sizes (in microns):\n{voxel_sizes}')

    # Print orientation and affine
    axcodes = nii_axis_codes(nii)
    np.set_printoptions(precision=4, suppress=True)
    print(f'\nAffine matrix ([default bold]{axcodes}[/]):\n{nii.affine}\n')

    verbose_end_msg()


if __name__ == '__main__':
    main()