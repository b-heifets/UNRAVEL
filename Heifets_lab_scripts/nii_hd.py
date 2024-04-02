#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install
from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_utils import print_cmd_and_times

def parse_args():
    parser = argparse.ArgumentParser(description='.nii.gz and print header using nibabel.', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', required=True, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


def main():
    np.set_printoptions(precision=4, suppress=True)

    nii = nib.load(args.input)
    print(nii.header)

    current_axcodes_tuple = nib.orientations.aff2axcodes(nii.affine) 
    current_axcodes = ''.join(current_axcodes_tuple) 
    np.set_printoptions(precision=4, suppress=True)
    print(f'\nOrientation: [default bold]{current_axcodes}[/]+\n')


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()