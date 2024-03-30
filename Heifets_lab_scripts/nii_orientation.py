#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from argparse_utils import SM, SuppressMetavar


def parse_args():
    parser = argparse.ArgumentParser(description='Load .nii.gz and print the orientation code and affine matrix', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', action=SM)
    return parser.parse_args()


def main():
    args = parse_args()
    nii = nib.load(args.input)
    current_axcodes_tuple = nib.orientations.aff2axcodes(nii.affine) 
    current_axcodes = ''.join(current_axcodes_tuple) 
    np.set_printoptions(precision=4, suppress=True)
    print(f'\nCurrent affine matrix ({current_axcodes}): \n{nii.affine}\n')


if __name__ == '__main__':
    install()
    main()