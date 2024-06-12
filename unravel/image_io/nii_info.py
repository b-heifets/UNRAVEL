#!/usr/bin/env python3

"""
Load .nii.gz and print its data type, shape, voxel sizes, and affine matrix using nibabel.
"""

import argparse
import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SM, SuppressMetavar


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', action=SM)
    parser.epilog = __doc__
    return parser.parse_args()

def nii_axis_codes(nii):
    """Get and return axes codes (three letter orientation like RAS) from an nibabel NIfTI image"""
    axcodes_tuple = nib.orientations.aff2axcodes(nii.affine) 
    axcodes = ''.join(axcodes_tuple) 
    return axcodes

def main():
    args = parse_args()
    
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


if __name__ == '__main__':
    install()
    main()