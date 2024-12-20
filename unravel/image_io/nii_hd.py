#!/usr/bin/env python3

"""
Use ``io_nii_hd`` (``hd``) from UNRAVEL to load a .nii.gz and print its header using nibabel.

Usage:
------
    io_nii_hd -i path/img.nii.gz [-v]
"""

import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/img.nii.gz', required=True, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    np.set_printoptions(precision=4, suppress=True)

    nii = nib.load(args.input)
    print(nii.header)

    current_axcodes_tuple = nib.orientations.aff2axcodes(nii.affine) 
    current_axcodes = ''.join(current_axcodes_tuple) 
    np.set_printoptions(precision=4, suppress=True)
    print(f'\nOrientation: [default bold]{current_axcodes}[/]+\n')

    verbose_end_msg()


if __name__ == '__main__':
    main()