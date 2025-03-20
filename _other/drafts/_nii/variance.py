#!/usr/bin/env python3

"""
Use ``variance.py`` from UNRAVEL to calculate the variance of .nii.gz images in the current directory.

Usage:
------
    vstats_z_score_cwd -i '<asterisk>.nii.gz' 
"""

import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.img_io import load_nii
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help='Path to the image or images to compute variance. Default: "*.nii.gz"', default='*.nii.gz', action=SM)
    opts.add_argument('-o', '--output', help='Output image path. Default: var.nii.gz', default='var.nii.gz', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    nii_paths = sorted(Path.cwd().glob(args.input))
    if not nii_paths:
        raise ValueError(f"No .nii.gz files found matching pattern {args.input}")

    # Load the images as 3D ndarrays
    imgs = [load_nii(nii_path) for nii_path in nii_paths]

    # Compute variance
    var_img = np.var(imgs, axis=0, ddof=1)  # Sample variance. axis=0 means variance is computed along the 4th dimension (across images)

    # Save the variance image
    ref_nii = nib.load(nii_paths[0])
    var_nii = nib.Nifti1Image(var_img, ref_nii.affine, ref_nii.header)
    var_nii.header.set_data_dtype(np.float32)
    nib.save(var_nii, args.output)

    verbose_end_msg()


if __name__ == '__main__':
    main()