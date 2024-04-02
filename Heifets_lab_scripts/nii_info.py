#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from argparse_utils import SM, SuppressMetavar


def parse_args():
    parser = argparse.ArgumentParser(description='Load .nii.gz and print its info', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', action=SM)
    return parser.parse_args()


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
    current_axcodes_tuple = nib.orientations.aff2axcodes(nii.affine) 
    current_axcodes = ''.join(current_axcodes_tuple) 
    np.set_printoptions(precision=4, suppress=True)
    print(f'\nAffine matrix ({current_axcodes}):\n{nii.affine}\n')


if __name__ == '__main__':
    install()
    main()