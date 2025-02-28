#!/usr/bin/env python3


"""
Use ``vstats_mirror`` (``mirror``) from UNRAVEL to load a .nii.gz, flip it, and save the flipped image.

Note:
    - Use -ax 2 and -s 0 for the CCFv3 2020 atlas.
    - Use -ax 0 and -s 2 for the 25 um Gubra atlas.

Usage:
------
    vstats_mirror [-p '<asterisk>.nii.gz'] [-ax 2] [-s 0] [-v]
"""

import os
import numpy as np
import nibabel as nib
from pathlib import Path
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-p', '--pattern', help='Pattern to match files. Default: *.nii.gz', default='*.nii.gz', action=SM)
    opts.add_argument('-ax', '--axis', help='Axis to flip the image along. Default: 2', default=2, type=int, action=SM)
    opts.add_argument('-s', '--shift', help='Number of voxels to shift content after flipping. Default: 0', default=0, type=int, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', default=False, action='store_true')

    return parser.parse_args()


@print_func_name_args_times()
def mirror(img, axis=2, shift=0):
    """Mirror an image along the specified axis and shift the content by the specified number of voxels.
    
    Args:
        img (np.ndarray): Image data to mirror
        axis (int): Axis to flip the image along. Default: 0
        shift (int): Number of voxels to shift content after flipping. Default: 2 (useful when the atlas is not centered)"""
    # Flip the image data along the specified axis
    flipped_img = np.flip(img, axis=axis)

    if shift == 0: 
        return flipped_img
    else: 
        # Shift the image data by padding with zeros on the left and cropping on the right
        # This adds 2 voxels of zeros on the left side (beginning) and removes 2 voxels from the right side (end)
        if axis == 0: 
            mirrored_img = np.pad(flipped_img, ((shift, 0), (0, 0), (0, 0)), mode='constant', constant_values=0)[:-shift, :, :]
            return mirrored_img
        else: 
            print('[red1]Logic for shifting content in axeses other than 0 has not been added. Please request this if needed.')
    return

    
@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    files = Path().cwd().glob(args.pattern)
    for file in files:

        basename = Path(file).name
        mirrored_filename = f"mirror_{basename}"

        if not os.path.exists(mirrored_filename): 
            nii = nib.load(file)
            img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()

            mirrored_img = mirror(img, axis=args.axis, shift=args.shift)

            mirrored_nii = nib.Nifti1Image(mirrored_img, nii.affine, nii.header)
            nib.save(mirrored_nii, mirrored_filename)

    verbose_end_msg()


if __name__ == '__main__':
    main()