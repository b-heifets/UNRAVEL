#!/usr/bin/env python3

"""
Use ``vstats_whole_to_avg`` (``lr_avg``) from UNRAVEL to average an image with its mirrored version for voxel-wise stats. This can also smooth the image with a kernel and apply a mask.

Prereqs:
    - Input images from ``vstats_prep``.
        - These may be z-scored with ``vstats_z_score``.

Inputs:
    - `*`.nii.gz images in the current directory.
    
Output:
    - input_img_LRavg.nii.gz for each input image.

Next steps:
    - Run ``vstats`` to perform voxel-wise stats.

Next commands for voxel-wise stats: 
    - Prepend condition names with ``utils_prepend``.
    - Check images in FSLeyes and run ``vstats`` to perform voxel-wise stats.

Next commands for voxel-wise stats:
        Preprocess atlas space IF images ``vstats_z_score``, prepend condition names with ``utils_prepend``, and perform voxel-wise stats with ``vstats``.

Usage:
------
    vstats_whole_to_avg [-i '<asterisk>.nii.gz'] [--kernel 0] [--axis 2] [--shift 0] [--parallel] [--atlas_mask path/atlas_mask.nii.gz] [-v]
"""

import numpy as np
import nibabel as nib
from glob import glob
from fsl.wrappers import fslmaths
from pathlib import Path
from rich import print
from rich.traceback import install
from concurrent.futures import ThreadPoolExecutor

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times
from unravel.voxel_stats.apply_mask import load_mask
from unravel.voxel_stats.mirror import mirror
        

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help='Pattern to match atlas space input images in the working dir. Default: *.nii.gz', default='*.nii.gz', action=SM)
    opts.add_argument('-k', '--kernel', help='Smoothing kernel radius in mm if > 0. Default: 0', default=0, type=float, action=SM)
    opts.add_argument('-ax', '--axis', help='Axis to flip the image along. Default: 2', default=2, type=int, action=SM)
    opts.add_argument('-s', '--shift', help='Number of voxels to shift content after flipping (if atlas is asym.). Default: 0', default=0, type=int, action=SM)
    opts.add_argument('-tp', '--parallel', help='Enable parallel processing with thread pools', default=False, action='store_true')
    opts.add_argument('-amas', '--atlas_mask', help='path/atlas_space_mask.nii.gz', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', default=False, action='store_true')

    return parser.parse_args()


@print_func_name_args_times()
def whole_to_LR_avg(file, kernel=0, axis=0, shift=2, atlas_mask=None):

    if kernel > 0:
        kernel_in_um = str(int(kernel * 1000))
        averaged_filename = f"{Path(file).name}".replace('.nii.gz', f'_s{kernel_in_um}_LRavg.nii.gz')
    else:
        averaged_filename = f"{Path(file).name}".replace('.nii.gz', '_LRavg.nii.gz')

    # Check if the output file already exists
    if Path(averaged_filename).exists():
        print(f"Output {averaged_filename} already exists. Skipping...")
        return

    print(f"    Processing {file}\n")
    nii = nib.load(file)

    # Smooth the image with a kernel
    if kernel > 0:
        print(f"    Smoothing image with a kernel radius of {kernel} mm")
        nii_smoothed = fslmaths(nii).s(kernel).run()
        img = np.asanyarray(nii_smoothed.dataobj, dtype=np.float32).squeeze()
    else:
        img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()

    # Mirror the image along the specified axis and shift the content by the specified number of voxels
    mirrored_img = mirror(img, axis=axis, shift=shift)

    # Average the original and mirrored images
    averaged_img = (img + mirrored_img) / 2

    # Apply the mask
    if atlas_mask is not None:
        mask_img = load_mask(atlas_mask)
        averaged_img[~mask_img] = 0  # Use logical NOT to flip True/False

    # Save the averaged image
    averaged_nii = nib.Nifti1Image(averaged_img, nii.affine, nii.header)

    nib.save(averaged_nii, averaged_filename)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    files = list(Path().cwd().glob(args.input))
    print(f'\nImages to process: {files}\n')

    if args.parallel:
        with ThreadPoolExecutor() as executor:
            executor.map(lambda file: whole_to_LR_avg(file, args.kernel, args.axis, args.shift, args.atlas_mask), files)
    else:
        for file in files:
            whole_to_LR_avg(file, args.kernel, args.axis, args.shift, args.atlas_mask)

    verbose_end_msg()


if __name__ == '__main__':
    main()
