#!/usr/bin/env python3

"""
Use ``img_unique`` from UNRAVEL to print a list of unique intensities greater than 0.

Usage for printing all non-zero intensities:
--------------------------------------------
    img_unique -i path/image [-v]

Usage for printing the number of voxels for each intensity that is present:
---------------------------------------------------------------------------
    img_unique -i path/image -s [-v]

Usage for printing unique intensities w/ a min cluster size > 100 voxels:
-------------------------------------------------------------------------
    img_unique -i path/image -min 100 [-v]
"""

import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.img_tools import label_IDs
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/image', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-min', '--min_size', help='Min label size in voxels (Default: 1)', default=1, action=SM, type=int)
    opts.add_argument('-s', '--print_sizes', help='Print label IDs and sizes. Default: False', default=False, action='store_true')

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Print unique intensities in image
    img = load_3D_img(args.input)
    uniq_intensities = label_IDs(img, min_voxel_count=args.min_size, print_IDs=True, print_sizes=args.print_sizes)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()