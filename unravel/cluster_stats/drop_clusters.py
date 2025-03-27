#!/usr/bin/env python3

"""
Use ``cstats_drop_clusters`` (``drop_clusters``) from UNRAVEL to replace voxel values in a NIfTI image with new labels.

Usage: 
------
    cstats_drop_clusters -i path/old_image.nii.gz -o path/new_image.nii.gz -ci path/input.csv [-vols] [-odt uint16] [-v]
"""

import numpy as np
import nibabel as nib
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/old_image.nii.gz', required=True, action=SM)
    reqs.add_argument('-dc', '--drop_clusters', help='Space-separated list of cluster IDs to drop.', required=True, nargs='*', type=int)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the NIfTI image
    nii = nib.load(args.input)

    # Make sure values in the image are integers
    img = nii.get_fdata().astype(int)

    # Drop the specified clusters
    for cluster in args.drop_clusters:
        img[img == cluster] = 0

    # Save the new image
    new_nii = nib.Nifti1Image(img, nii.affine, nii.header)
    nib.save(new_nii, args.input.replace('.nii.gz', '_dropped.nii.gz'))

    verbose_end_msg()


if __name__ == '__main__':
    main()