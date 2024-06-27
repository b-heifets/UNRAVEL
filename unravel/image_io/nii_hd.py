#!/usr/bin/env python3

"""
Use ``io_nii_hd`` from UNRAVEL to load a .nii.gz and print its header using nibabel.

Usage:
------
    io_nii_hd -i path/img.nii.gz
"""

import argparse
import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import print_cmd_and_times

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', required=True, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@print_cmd_and_times
def main():
    args = parse_args()

    np.set_printoptions(precision=4, suppress=True)

    nii = nib.load(args.input)
    print(nii.header)

    current_axcodes_tuple = nib.orientations.aff2axcodes(nii.affine) 
    current_axcodes = ''.join(current_axcodes_tuple) 
    np.set_printoptions(precision=4, suppress=True)
    print(f'\nOrientation: [default bold]{current_axcodes}[/]+\n')


if __name__ == '__main__' or __name__ == 'unravel.image_io.nii_hd':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose

if __name__ == '__main__':
    main()