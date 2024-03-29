#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from argparse_utils import SM, SuppressMetavar


def parse_args():
    parser = argparse.ArgumentParser(description='Load .nii.gz and print orientation', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', action=SM)
    return parser.parse_args()

def affine_to_orientation_code(affine):
    """Convert the given affine matrix to the 3-letter orientation code (e.g. RAS+)"""
    orientation = ''
    axis_labels = ['R', 'L', 'A', 'P', 'S', 'I']



    # Iterate through the first three columns
    for i in range(3):
        column = [affine[0][i], affine[1][i], affine[2][i]] # Get the column values
        max_val_index = column.index(max(column, key=abs))  # Find the index of the non-zero value
        if column[max_val_index] > 0:
            orientation += axis_labels[max_val_index * 2]  # Positive value. Add the letter of the axis
        else:
            orientation += axis_labels[max_val_index * 2 + 1]  # Negative value.
    return orientation


def main():
    args = parse_args()
    nii = nib.load(args.input)

    np.set_printoptions(precision=4, suppress=True)
    print(f'\nAffine matrix: \n{nii.affine}\n')
    
    orientation_code = affine_to_orientation_code(nii.affine)
    print(f"Orientation code: {orientation_code}")


if __name__ == '__main__':
    install()
    main()