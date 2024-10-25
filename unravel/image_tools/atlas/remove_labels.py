#!/usr/bin/env python3

"""
Use ``set_labels`` from UNRAVEL to set specified label IDs in an image to a given intensity.

Usage: 
------
    set_labels -i path/old_image.nii.gz -ids 1 2 3 [-val 0] [-o path/new_image.nii.gz] [-v]
"""

import numpy as np
import nibabel as nib
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.utils import log_command, print_func_name_args_times, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/old_image.nii.gz', required=True, action=SM)
    reqs.add_argument('-ids', '--label_IDs', help='Space-separated list of IDs to zero out or set to a specific value.', nargs='*', type=int, default=None, required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='path/image_zeroed.nii.gz', action=SM)
    opts.add_argument('-val', '--value', help='Intensity to set for specified labels (default: 0).', type=int, default=0)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@print_func_name_args_times()
def remove_labels(img, label_IDs, value=0):
    """
    Set specified label IDs in the ndarray to the given value.
    
    Parameters
    ----------
    img : ndarray
        The input image as a numpy ndarray.
    label_IDs : list of int
        The label IDs to zero out.

    Returns
    -------
    ndarray
        The modified image with the specified label IDs zeroed out.

    Notes
    -----
    - If no label IDs are provided, the function will return the original image.
    """
    img[np.isin(img, label_IDs)] = value  # Creates a boolean mask of the label IDs and sets them to the specified value
    return img


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the NIfTI image
    nii = nib.load(args.input)
    img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()

    # Modify specified label IDs
    new_img_array = remove_labels(img, args.label_IDs, args.value)

    # Convert to a NIfTI image and save
    output_path = args.output if args.output else str(args.input).replace(".nii.gz", "_zeroed.nii.gz")
    nib.save(nib.Nifti1Image(new_img_array, nii.affine, nii.header), output_path)

    verbose_end_msg()


if __name__ == '__main__':
    main()