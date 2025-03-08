#!/usr/bin/env python3

"""
Use ``fstat_sig_vx_mask`` (``fsvm``) from UNRAVEL to threshold FSL's f-statistic images and combine them to make a mask for FDR-correction.

Usage:
------
    fstat_sig_vx_mask -i ['<asterisk>vox_p_fstat<asterisk>.nii.gz'] [-t 0.95] [-o fstat_sig_vx_mask.nii.gz] [-v]
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
    opts.add_argument('-i', '--input', help='Glob pattern for ANOVA f statistic 1-p value images. Default: "*vox_p_fstat*.nii.gz"', default='*vox_p_fstat*.nii.gz', action=SM)
    opts.add_argument('-t', '--threshold', help='Threshold for the p-value. Default: 0.95', default=0.95, type=float, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Set voxels outside the mask(s) to zero


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    nii_paths = list(Path.cwd().glob(args.input))
    if not nii_paths:
        print("[red]Error: No files found matching the pattern.[/red]")
        exit(1)

    imgs = [load_nii(path) for path in nii_paths]
    
    # Initialize an empty image to store the sig voxels
    sig_vx_img = np.zeros(imgs[0].shape, dtype=bool)

    # Combine the images to get the sig voxels
    for img in imgs:
        sig_vx_img |= img < args.threshold

    # The dtype for sig_vx_img is bool, so we need to convert it to uint8
    sig_vx_img = sig_vx_img.astype(np.uint8)

    # Save the z-scored image
    output_path = Path("fstat_sig_vx_mask.nii.gz")
    first_nii = nib.load(nii_paths[0])
    sig_vx_nii = nib.Nifti1Image(sig_vx_img, first_nii.affine, first_nii.header)
    sig_vx_nii.header.set_data_dtype(np.uint8)
    nib.save(sig_vx_nii, output_path)

    verbose_end_msg()


if __name__ == '__main__':
    main()